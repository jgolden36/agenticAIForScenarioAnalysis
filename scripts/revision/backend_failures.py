#!/usr/bin/env python3
"""Why backends failed in a model-comparison batch (Reviewer 2, point 5).

``scripts/revision/backend_comparison.py`` walks report directories, so a run
that failed at the weekly brief, before any report existed, is invisible to
it. This script reads the batch's ``runs.json`` plus the SLURM driver logs and
gives every failed run its principal error class:

* ``json_schema_unsupported``: the provider rejects structured output for this model;
* ``temperature_deprecated``: the provider rejects the temperature parameter;
* ``json_generation_invalid``: the provider could not validate the model's JSON;
* ``brief_schema_validation``: the reply parsed but failed the ``WeeklyBrief`` schema;
* ``scenario_schema_validation``: the reply failed the ``ScenarioSet`` schema;
* ``scenario_count_short``: the reply validated but had fewer scenarios than requested.

Failures and errors are paired in log order, since runs execute one at a time.
Any count or provider mismatch is an error, not a guess. A batch rerun across
several jobs passes ``--driver-log`` once per job, oldest first: the latest error
for a (backend, week) wins, and only runs still failing in ``runs.json`` are kept.

Usage::

    python scripts/revision/backend_failures.py --batch-dir data/reports/model_comparison/20260701_020011 \
        --driver-log slurm/logs/stonybrook_ai_cluster_model_comparison-44917 \
        --out-dir docs/revision/runs/backend_comparison_20260701_020011
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_FAILED_RE = re.compile(r"\[(?P<tag>[^/\]]+)/(?P<week>\d{8})\] (?P<kind>brief build failed|brief failed again|pipeline status=failed)")
_ERROR_RE = re.compile(
    r"^(?P<cls>[\w.]+(?:BadRequestError|ValidationError|OutputParserException)|ValueError(?=: Scenario generation returned)): (?P<msg>.*)$"
)

_CLASS_RULES: tuple[tuple[str, str], ...] = (
    ("does not support response format", "json_schema_unsupported"),
    ("is deprecated for this model", "temperature_deprecated"),
    ("Failed to validate JSON", "json_generation_invalid"),
    ("Scenario generation returned", "scenario_count_short"),
    ("ScenarioSet", "scenario_schema_validation"),
    ("validation error", "brief_schema_validation"),
    ("Failed to parse WeeklyBrief", "brief_schema_validation"),
)


def classify(message: str) -> str:
    for needle, label in _CLASS_RULES:
        if needle in message:
            return label
    return "other"


def parse_failures(out_text: str) -> list[tuple[str, str, str]]:
    return [(m["tag"], m["week"], "scenarios" if m["kind"] == "pipeline status=failed" else "brief") for m in _FAILED_RE.finditer(out_text)]


def _is_chained(lines: list[str], i: int) -> bool:
    """True when the error at ``lines[i]`` is the cause of a later exception in the same chain."""
    for line in lines[i + 1:]:
        if line.startswith("Traceback"):
            return False
        if "direct cause of the following exception" in line:
            return True
    return False


def parse_errors(err_text: str) -> list[tuple[str, str]]:
    errors = []
    lines = err_text.splitlines()
    for i, line in enumerate(lines):
        m = _ERROR_RE.match(line.strip())
        if not m or _is_chained(lines, i):
            continue
        msg = m["msg"]
        # Pydantic names the offending field on the following line.
        if m["cls"].endswith("ValidationError") and i + 1 < len(lines):
            msg = f"{msg}: {lines[i + 1].strip()}"
        errors.append((m["cls"], msg))
    return errors


def pair(failures: list[tuple[str, str, str]], errors: list[tuple[str, str]]) -> list[dict[str, str]]:
    if len(failures) != len(errors):
        raise ValueError(f"{len(failures)} failed runs but {len(errors)} errors in the logs; refusing to pair them")
    rows = []
    for (tag, week, stage), (cls, msg) in zip(failures, errors):
        provider = tag.split("-", 1)[0]
        if "BadRequestError" in cls and not cls.startswith(provider):
            raise ValueError(f"log order mismatch: {tag}/{week} paired with {cls}")
        text = f"{cls}: {msg}"
        rows.append({"tag": tag, "week": week, "stage": stage, "error_class": classify(text), "error": text[:300]})
    return rows


def still_failing(runs: list[dict[str, Any]], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Latest row per (backend, week), dropping weeks that ``runs.json`` records as ok."""
    failing = {(r["tag"], str(r["week_start"]).replace("-", "")) for r in runs if r.get("status") != "ok"}
    latest = {(row["tag"], row["week"]): row for row in rows}
    return [row for key, row in latest.items() if key in failing]


def summarise(runs: list[dict[str, Any]], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    total: Counter[str] = Counter()
    ok: Counter[str] = Counter()
    model: dict[str, str] = {}
    for r in runs:
        total[r["tag"]] += 1
        ok[r["tag"]] += r.get("status") == "ok"
        model[r["tag"]] = r.get("model", "")
    classes: dict[str, Counter[str]] = defaultdict(Counter)
    stages: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        classes[row["tag"]][row["error_class"]] += 1
        stages[row["tag"]][row["stage"]] += 1
    return [{"tag": t, "model": model[t], "runs": total[t], "ok": ok[t], "failed_at_brief": stages[t]["brief"],
             "failed_at_scenarios": stages[t]["scenarios"], "error_classes": dict(classes[t])}
            for t in sorted(total, key=lambda t: (-ok[t], t))]


def render(batch: str, summary: list[dict[str, Any]], rows: list[dict[str, str]]) -> str:
    lines = [f"# Backend failures in batch `{batch}`", "",
             f"{len(rows)} runs failed at the weekly brief or at scenario generation, before any domain model ran.", "",
             "| backend | model | runs | ok | failed at brief | failed at scenarios | principal error |", "|---|---|---|---|---|---|---|"]
    for s in summary:
        errs = "; ".join(f"{k} ({v})" for k, v in sorted(s["error_classes"].items())) or "none"
        lines.append(f"| {s['tag']} | {s['model']} | {s['runs']} | {s['ok']} | {s['failed_at_brief']} | {s['failed_at_scenarios']} | {errs} |")
    lines += ["", "## Failed runs", "", "| backend | week | stage | class | error |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['tag']} | {r['week']} | {r['stage']} | {r['error_class']} | {r['error'][:160].replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--batch-dir", required=True)
    p.add_argument("--driver-log", required=True, action="append",
                   help="Log path without the .out / .err suffix. Repeat for each job, oldest first.")
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)

    batch_dir = Path(args.batch_dir)
    runs = json.loads((batch_dir / "runs.json").read_text(encoding="utf-8"))
    runs = runs if isinstance(runs, list) else runs.get("runs", [])
    rows: list[dict[str, str]] = []
    for log in args.driver_log:
        out_text = Path(log + ".out").read_text(encoding="utf-8", errors="replace")
        err_text = Path(log + ".err").read_text(encoding="utf-8", errors="replace")
        rows += pair(parse_failures(out_text), parse_errors(err_text))
    rows = still_failing(runs, rows)
    summary = summarise(runs, rows)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "backend_failures.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["tag", "week", "stage", "error_class", "error"])
        writer.writeheader()
        writer.writerows(rows)
    (out / "backend_failures.json").write_text(json.dumps({"batch": batch_dir.name, "summary": summary, "failures": rows}, indent=2), encoding="utf-8")
    (out / "backend_failures.md").write_text(render(batch_dir.name, summary, rows), encoding="utf-8")
    print(f"{len(rows)} failures classified: {dict(Counter(r['error_class'] for r in rows))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
