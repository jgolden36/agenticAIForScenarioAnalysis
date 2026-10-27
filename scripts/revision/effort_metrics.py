#!/usr/bin/env python3
"""Integration-effort metrics from the repository and its git history (Reviewer 2, point 1).

Per adapter module: code lines (non-blank, non-comment), total lines, test
lines that reference the model id, number of commits touching the file,
first and last commit dates. Per forwarding rule: YAML lines in each
``models.<downstream>`` block of ``configs/upstream_forwarding_mapping.yaml``.
Per named change (the infrastructure-collapse scenario, the fertilizer to
food APSIM bridge): lines added and removed in the commits that introduced
the marker strings, with a ``bundled`` flag when the commit touched many
unrelated files (the early history was uploaded in bulk, so those numbers
are upper bounds, not isolated costs).

Person-hours are not derivable from the repository and the column is left
blank for the authors to fill in.

Usage::

    python scripts/revision/effort_metrics.py --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ADAPTER_DIRS = ("water", "oil", "lng", "helium", "fertilizer", "shipping", "macro", "energy")
SUPPORT_MODULES = {"macro_kernel.py", "nems_shocks.py", "simrlfab_driver.py", "__init__.py"}

NAMED_CHANGES: dict[str, dict[str, Any]] = {
    "infrastructure_collapse_scenario": {
        "marker": "infrastructure_collapse",
        "paths": ["src/common/types.py", "configs/scenario_frameworks/hormuz_2026.yaml",
                  "configs/upstream_forwarding_mapping.yaml", "src/pipeline/upstream_forwarding.py"],
        "description": "Prescribed tail-risk scenario E added outside the 2x2 matrix (enum, framework YAML, water forwarding rule).",
    },
    "apsim_fertilizer_food_bridge": {
        "marker": "price_to_demand_reduction",
        "paths": ["src/models/fertilizer/apsim.py", "configs/upstream_forwarding_mapping.yaml",
                  "src/pipeline/upstream_forwarding.py", "tests/test_pipeline/test_upstream_forwarding.py"],
        "description": "FERTILIZER to FOOD linkage: APSIM moved to COMMODITY_DOWNSTREAM and fed from world_fertilizer / cwatm.",
    },
}
BUNDLED_FILE_THRESHOLD = 15


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False).stdout
    except (OSError, FileNotFoundError):
        return ""


def count_lines(path: Path) -> tuple[int, int]:
    """(code_lines, total_lines); code lines exclude blanks, comments and docstring-only lines."""
    total = code = 0
    in_doc = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        total += 1
        s = line.strip()
        if not s:
            continue
        if in_doc:
            if '"""' in s or "'''" in s:
                in_doc = False
            continue
        if s.startswith(('"""', "'''")):
            if s.count('"""') == 2 or s.count("'''") == 2:
                continue
            in_doc = True
            continue
        if s.startswith("#"):
            continue
        code += 1
    return code, total


def git_file_history(repo: Path, path: str) -> dict[str, Any]:
    out = _git(repo, "log", "--follow", "--format=%H%x09%ad", "--date=short", "--", path)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines:
        return {"commits": 0, "first_commit": None, "last_commit": None}
    dates = [ln.split("\t")[1] for ln in lines]
    return {"commits": len(lines), "first_commit": dates[-1], "last_commit": dates[0]}


def test_lines_for(repo: Path, model_id: str) -> tuple[int, int]:
    """(test files mentioning the model id, their code lines)."""
    tests = repo / "tests"
    if not tests.exists():
        return 0, 0
    pat = re.compile(rf"\b{re.escape(model_id)}\b")
    n_files = n_lines = 0
    for path in tests.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if pat.search(text):
            n_files += 1
            n_lines += count_lines(path)[0]
    return n_files, n_lines


def adapter_rows(repo: Path) -> list[dict[str, Any]]:
    try:
        from src.models.implementation_info import IMPLEMENTATION_INFO  # noqa: WPS433
    except Exception:  # noqa: BLE001
        IMPLEMENTATION_INFO = {}
    rows: list[dict[str, Any]] = []
    for system in ADAPTER_DIRS:
        d = repo / "src" / "models" / system
        if not d.exists():
            continue
        for path in sorted(d.glob("*.py")):
            if path.name in SUPPORT_MODULES:
                continue
            model_id = path.stem
            if model_id == "weap":
                model_id = "weap_mena"
            code, total = count_lines(path)
            hist = git_file_history(repo, str(path.relative_to(repo)))
            t_files, t_lines = test_lines_for(repo, model_id)
            info = IMPLEMENTATION_INFO.get(model_id)
            rows.append({
                "model_id": model_id, "system": system, "path": str(path.relative_to(repo)),
                "status_label": getattr(info, "status_label", "") if info is not None else "",
                "code_lines": code, "total_lines": total,
                "test_files": t_files, "test_code_lines": t_lines,
                "commits": hist["commits"], "first_commit": hist["first_commit"], "last_commit": hist["last_commit"],
                "person_hours": "",
            })
    return rows


def forwarding_rule_rows(repo: Path) -> list[dict[str, Any]]:
    path = repo / "configs" / "upstream_forwarding_mapping.yaml"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []
    in_models = False
    current: str | None = None
    counts: dict[str, dict[str, int]] = {}
    for line in lines:
        if re.match(r"^models:\s*$", line):
            in_models = True
            continue
        if in_models and re.match(r"^\S", line) and not line.startswith("models"):
            in_models = False
            current = None
        if not in_models:
            continue
        m = re.match(r"^  ([a-z0-9_]+):\s*$", line)
        if m:
            current = m.group(1)
            counts[current] = {"lines": 0, "rules": 0, "sources": 0}
            continue
        if current is None:
            continue
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        counts[current]["lines"] += 1
        # A rule is a downstream parameter key at indent 4 under the model
        # block (e.g. "    helium_supply_reduction_pct:"); each
        # "- source_model:" entry is one ordered fallback source.
        if re.match(r"^    [A-Za-z0-9_.\[\]]+:\s*$", line):
            counts[current]["rules"] += 1
        if re.match(r"^- source_model:", s):
            counts[current]["sources"] += 1
    for mid, c in counts.items():
        rows.append({"downstream_model": mid, "yaml_lines": c["lines"], "rules": c["rules"], "source_entries": c["sources"]})
    return rows


def named_change_rows(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, spec in NAMED_CHANGES.items():
        out = _git(repo, "log", "--format=%H%x09%ad%x09%s", "--date=short", "--reverse", f"-S{spec['marker']}", "--", *spec["paths"])
        commits = [ln.split("\t") for ln in out.splitlines() if ln.strip()]
        if not commits:
            rows.append({"change": name, "description": spec["description"], "commit": None, "date": None, "subject": None,
                         "files_in_commit": 0, "lines_added": 0, "lines_removed": 0, "bundled": None, "person_hours": ""})
            continue
        for sha, date, subject in commits:
            numstat = _git(repo, "show", "--numstat", "--format=", sha)
            n_files = added = removed = 0
            for ln in numstat.splitlines():
                parts = ln.split("\t")
                if len(parts) < 3:
                    continue
                n_files += 1
                if parts[2] in spec["paths"]:
                    added += int(parts[0]) if parts[0].isdigit() else 0
                    removed += int(parts[1]) if parts[1].isdigit() else 0
            rows.append({
                "change": name, "description": spec["description"], "commit": sha[:7], "date": date, "subject": subject,
                "files_in_commit": n_files, "lines_added": added, "lines_removed": removed,
                "bundled": n_files > BUNDLED_FILE_THRESHOLD, "person_hours": "",
            })
    return rows


def render_markdown(adapters: list[dict[str, Any]], rules: list[dict[str, Any]], changes: list[dict[str, Any]]) -> str:
    lines = ["# Integration effort metrics", "",
             "Generated by `scripts/revision/effort_metrics.py` from the working tree and `git log`. "
             "Code lines exclude blanks, comments and docstrings. Test lines count every test module that names the model id. "
             "Person-hours are author estimates and are not derivable from the repository; the column is left blank.", "",
             "## Adapters", "",
             "| model | system | status | code lines | total lines | test files | test code lines | commits | first commit | last commit | person-hours |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in adapters:
        lines.append(f"| {r['model_id']} | {r['system']} | {r['status_label']} | {r['code_lines']} | {r['total_lines']} | "
                     f"{r['test_files']} | {r['test_code_lines']} | {r['commits']} | {r['first_commit']} | {r['last_commit']} | |")
    tot_code = sum(r["code_lines"] for r in adapters)
    tot_test = sum(r["test_code_lines"] for r in adapters)
    lines += ["", f"Totals: {len(adapters)} adapter modules, {tot_code} code lines, {tot_test} test code lines (with overlap across models).", "",
              "## Forwarding rules (YAML lines per downstream model)", "",
              "| downstream model | yaml lines | rules | source entries |", "|---|---|---|---|"]
    for r in rules:
        lines.append(f"| {r['downstream_model']} | {r['yaml_lines']} | {r['rules']} | {r['source_entries']} |")
    lines += ["", "## Named changes", "",
              "| change | commit | date | files in commit | lines added | lines removed | bundled upload | person-hours |",
              "|---|---|---|---|---|---|---|---|"]
    for r in changes:
        lines.append(f"| {r['change']} | {r['commit']} | {r['date']} | {r['files_in_commit']} | {r['lines_added']} | {r['lines_removed']} | {r['bundled']} | |")
    lines += ["", "`bundled upload = True` marks commits that touched more than "
              f"{BUNDLED_FILE_THRESHOLD} files (bulk uploads); their line counts are upper bounds for the named change.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=None)
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)
    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parents[2]
    adapters = adapter_rows(repo)
    rules = forwarding_rule_rows(repo)
    changes = named_change_rows(repo)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("effort_metrics_adapters", adapters), ("effort_metrics_forwarding_rules", rules), ("effort_metrics_named_changes", changes)):
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    (out / "effort_metrics.md").write_text(render_markdown(adapters, rules, changes), encoding="utf-8")
    (out / "effort_metrics.json").write_text(json.dumps({"adapters": adapters, "forwarding_rules": rules, "named_changes": changes}, indent=2), encoding="utf-8")
    print(json.dumps({"adapters": len(adapters), "forwarding_rules": len(rules), "named_changes": len(changes), "out_dir": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
