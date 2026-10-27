#!/usr/bin/env python3
"""Software and runtime versions behind the reported runs (code availability).

Merges four sources into ``docs/revision/software_versions.{md,json}``:

* the local Python environment (interpreter, git commit, versions of the
  packages the pipeline imports, via ``importlib.metadata``);
* the per-stage runtime inventories the SLURM jobs write
  (``slurm/logs/runtime-<stage>-<job>-<task>.json`` and
  ``data/pipeline_state/<run_id>_runtime.jsonl``: python, conda, GAMS,
  Julia, R, Java, CUDA banners per node);
* a ``pip freeze`` listing captured on the cluster (``--pip-freeze``);
* the LLM backend recorded in each run's ``<run_id>_scenarios.json``
  (``config.llm``), one row per ``--run-id``.

Usage::

    python scripts/revision/software_versions.py --run-id 20260504_222710 \
        [--state-dir data/pipeline_state] [--runtime-dir slurm/logs] \
        [--pip-freeze cluster_pip_freeze.txt] --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PACKAGES = [
    "langchain", "langchain-core", "langgraph", "pydantic", "pyyaml", "numpy", "pandas", "openpyxl",
    "matplotlib", "requests", "wandb", "tiktoken", "juliacall", "gamsapi", "ogcore", "ogusa", "cge-modeling",
    "otoole", "message-ix", "ixmp", "pyomo", "xlwings", "rpy2", "netCDF4", "xarray", "pytest",
]
RUNTIME_KEYS = ["python", "conda", "gams", "julia", "R", "java", "cuda"]


def local_environment(repo: Path) -> dict[str, Any]:
    def _git(*args: str) -> str | None:
        try:
            r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
            return r.stdout.strip() or None if r.returncode == 0 else None
        except OSError:
            return None

    versions: dict[str, str | None] = {}
    for pkg in PACKAGES:
        try:
            versions[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            versions[pkg] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_describe": _git("describe", "--tags", "--always"),
        "packages": versions,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_pip_freeze(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        for sep in ("==", " @ ", "==="):
            if sep in s:
                name, _, ver = s.partition(sep)
                out[name.strip().lower()] = ver.strip()
                break
    return out


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def runtime_inventories(runtime_dir: Path | None, state_dir: Path | None, run_ids: list[str]) -> list[dict[str, Any]]:
    """Distinct (hostname, runtimes) records from sidecars and run-wide jsonl files."""
    records: list[dict[str, Any]] = []
    if runtime_dir and runtime_dir.exists():
        for p in sorted(runtime_dir.glob("runtime-*.json")):
            rec = _load_json(p)
            if isinstance(rec, dict):
                rec["_source"] = str(p)
                records.append(rec)
    if state_dir and state_dir.exists():
        for rid in run_ids or ["*"]:
            for p in sorted(state_dir.glob(f"{rid}_runtime.jsonl")):
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(rec, dict):
                        rec.setdefault("run_id", p.name[: -len("_runtime.jsonl")])
                        rec["_source"] = str(p)
                        records.append(rec)
    seen: set[tuple] = set()
    distinct: list[dict[str, Any]] = []
    for rec in records:
        rt = rec.get("runtimes") or {}
        key = (rec.get("hostname"), tuple((k, rt.get(k)) for k in RUNTIME_KEYS))
        if key in seen:
            continue
        seen.add(key)
        distinct.append({
            "run_id": rec.get("run_id"), "stage": rec.get("stage"), "hostname": rec.get("hostname"),
            "timestamp": rec.get("timestamp"), "gpu": rec.get("gpu_visible", rec.get("gpu")),
            "conda_env": rec.get("conda_env_active"),
            **{k: (rt.get(k) or None) for k in RUNTIME_KEYS},
        })
    return distinct


def llm_backends(state_dir: Path | None, run_ids: list[str]) -> list[dict[str, Any]]:
    rows = []
    for rid in run_ids:
        if state_dir is None:
            break
        st = _load_json(state_dir / f"{rid}_scenarios.json")
        llm = ((st or {}).get("config") or {}).get("llm") or {}
        rows.append({"run_id": rid, "provider": llm.get("provider"), "model": llm.get("model"),
                     "base_url": llm.get("base_url"), "temperature": llm.get("temperature"),
                     "generated_at": (st or {}).get("generated_at"), "state_available": st is not None})
    return rows


def build(repo: Path, *, run_ids: list[str], state_dir: Path | None, runtime_dir: Path | None, pip_freeze: Path | None) -> dict[str, Any]:
    local = local_environment(repo)
    cluster = parse_pip_freeze(pip_freeze) if pip_freeze and pip_freeze.exists() else {}
    packages = []
    for pkg in PACKAGES:
        packages.append({"package": pkg, "local": local["packages"].get(pkg), "cluster": cluster.get(pkg.lower()) or None})
    return {
        "local_environment": {k: v for k, v in local.items() if k != "packages"},
        "packages": packages,
        "cluster_pip_freeze": str(pip_freeze) if pip_freeze else None,
        "runtime_inventories": runtime_inventories(runtime_dir, state_dir, run_ids),
        "llm_backends": llm_backends(state_dir, run_ids),
    }


def render_markdown(d: dict[str, Any]) -> str:
    le = d["local_environment"]
    lines = ["# Software versions", "",
             f"Collected {le['collected_at']} at commit `{le['git_commit']}` (branch `{le['git_branch']}`, describe `{le['git_describe']}`) "
             f"on Python {le['python']} ({le['platform']}).", "",
             "## Python packages", "", "| package | this environment | cluster pip freeze |", "|---|---|---|"]
    for p in d["packages"]:
        lines.append(f"| {p['package']} | {p['local'] or '-'} | {p['cluster'] or '-'} |")
    if not d["cluster_pip_freeze"]:
        lines.append("")
        lines.append("_No cluster `pip freeze` supplied (`--pip-freeze`); the cluster column is empty._")
    lines += ["", "## Runtime inventories (per node, from the SLURM sidecars)", ""]
    if d["runtime_inventories"]:
        lines += ["| run | stage | host | gpu | conda env | python | gams | julia | R | java | cuda |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in d["runtime_inventories"]:
            lines.append(f"| {r['run_id'] or ''} | {r['stage'] or ''} | {r['hostname'] or ''} | {r['gpu'] or ''} | {r['conda_env'] or ''} | "
                         f"{r['python'] or '-'} | {r['gams'] or '-'} | {r['julia'] or '-'} | {r['R'] or '-'} | {r['java'] or '-'} | {r['cuda'] or '-'} |")
    else:
        lines.append("_No runtime sidecars found (`slurm/logs/runtime-*.json`, `<run_id>_runtime.jsonl`)._")
    lines += ["", "## LLM backends per run", "", "| run | provider | model | base url | temperature | state file |", "|---|---|---|---|---|---|"]
    for r in d["llm_backends"]:
        lines.append(f"| {r['run_id']} | {r['provider'] or '-'} | {r['model'] or '-'} | {r['base_url'] or '-'} | {r['temperature'] if r['temperature'] is not None else '-'} | "
                     f"{'found' if r['state_available'] else 'not available locally'} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", action="append", default=[])
    p.add_argument("--state-dir", default="data/pipeline_state")
    p.add_argument("--runtime-dir", default="slurm/logs")
    p.add_argument("--pip-freeze", default=None)
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    d = build(repo, run_ids=args.run_id, state_dir=Path(args.state_dir) if args.state_dir else None,
              runtime_dir=Path(args.runtime_dir) if args.runtime_dir else None,
              pip_freeze=Path(args.pip_freeze) if args.pip_freeze else None)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "software_versions.json").write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
    (out / "software_versions.md").write_text(render_markdown(d), encoding="utf-8")
    print(f"wrote {out / 'software_versions.md'} ({len(d['runtime_inventories'])} runtime record(s), {len(d['llm_backends'])} run(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
