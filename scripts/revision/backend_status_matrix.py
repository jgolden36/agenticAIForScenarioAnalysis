#!/usr/bin/env python3
"""What each backend did in each week, before and after the reruns (Reviewer 2, point 5).

``runs.json`` overstates success: a July run that generated zero scenarios was
recorded as ``ok``. This script counts a run as having done model work only when
it completed at least one domain model. Original, rerun and added batches stay in
separate columns, because reruns used later code and settings and are not
like-for-like with the original batch.

Usage::

    python scripts/revision/backend_status_matrix.py --source-batch 20260701_020011 \
        --rerun-batch fill_20261102 --added-batch alt_20261102 \
        --comparison-csv docs/revision/runs/backend_comparison_20260701_020011/backend_comparison.csv \
        --comparison-csv docs/revision/runs/backend_comparison_fill_20261102/backend_comparison.csv \
        --comparison-csv docs/revision/runs/backend_comparison_alt_20261102/backend_comparison.csv \
        --retired groq-llama-3.3-70b,groq-llama-3.1-8b,groq-qwen3-32b,groq-llama4-scout \
        --out-dir docs/revision/runs/backend_status_20261102
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


def read_runs(root: Path, batch: str | None) -> list[dict[str, Any]]:
    if not batch:
        return []
    data = json.loads((root / batch / "runs.json").read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("runs", [])


def read_comparison(paths: list[Path]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rows[row["run_id"]] = row
    return rows


def outcome(run: dict[str, Any] | None, comparison: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """One run's result: recorded status, completed models and clean-synthesis flag."""
    if run is None:
        return None
    row = comparison.get(run["run_id"]) or {}
    completed = int(row.get("completed") or 0)
    return {
        "run_id": run["run_id"],
        "recorded_status": run.get("status"),
        "completed_models": completed,
        "did_model_work": completed > 0,
        "clean_synthesis": row.get("clean_synthesis") == "True",
        "sections_failed": int(row.get("sections_failed") or 0),
        "sections_total": int(row.get("sections_total") or 0),
    }


def build_matrix(source: list[dict[str, Any]], reruns: list[dict[str, Any]], added: list[dict[str, Any]],
                 comparison: dict[str, dict[str, Any]], retired: set[str]) -> dict[str, Any]:
    cell = lambda runs: {(r["tag"], r["week_start"]): r for r in runs}  # noqa: E731
    source_cells, rerun_cells, added_cells = cell(source), cell(reruns), cell(added)
    weeks = sorted({w for _, w in (*source_cells, *added_cells)})
    source_tags = sorted({t for t, _ in source_cells})
    added_tags = sorted({t for t, _ in added_cells})

    rows = []
    for tag in (*source_tags, *added_tags):
        for week in weeks:
            original = outcome(source_cells.get((tag, week)), comparison)
            rerun = outcome(rerun_cells.get((tag, week)), comparison)
            add = outcome(added_cells.get((tag, week)), comparison)
            current = add or rerun or original
            rows.append({"backend": tag, "week": week, "group": "added" if tag in added_tags else "original",
                         "retired": tag in retired, "original": original, "rerun": rerun, "added": add, "current": current})

    summary = []
    for tag in (*source_tags, *added_tags):
        mine = [r for r in rows if r["backend"] == tag]
        first = [r["original"] or r["added"] for r in mine]
        current = [r["current"] for r in mine]
        worked = [c for c in current if c and c["did_model_work"]]
        summary.append({
            "backend": tag,
            "group": mine[0]["group"],
            "retired": tag in retired,
            "weeks": len(mine),
            "first_batch_recorded_ok": sum(1 for c in first if c and c["recorded_status"] == "ok"),
            "first_batch_did_model_work": sum(1 for c in first if c and c["did_model_work"]),
            "first_batch_clean": sum(1 for c in first if c and c["clean_synthesis"]),
            "weeks_rerun": sum(1 for r in mine if r["rerun"]),
            "current_did_model_work": len(worked),
            "current_clean": sum(1 for c in current if c and c["clean_synthesis"]),
            "completed_models_per_working_week": sorted({c["completed_models"] for c in worked}),
        })
    return {"weeks": weeks, "rows": rows, "summary": summary}


def render(result: dict[str, Any]) -> str:
    lines = ["# Backend status by week, before and after the reruns", "",
             "A week counts as model work only when at least one domain model completed. "
             "`recorded ok` is what `runs.json` says, which overstates success for the zero-scenario runs. "
             "Reruns and added backends used later code and settings, so they are not like-for-like with the original batch. "
             "Retired models could not be rerun because the provider no longer serves them.", "",
             "| backend | group | first batch: recorded ok | first batch: model work | first batch: clean | weeks rerun | now: model work | now: clean | models completed per working week |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in result["summary"]:
        name = f"{s['backend']} (retired)" if s["retired"] else s["backend"]
        spread = ", ".join(str(c) for c in s["completed_models_per_working_week"]) or "-"
        lines.append(f"| {name} | {s['group']} | {s['first_batch_recorded_ok']}/{s['weeks']} | {s['first_batch_did_model_work']}/{s['weeks']} | "
                     f"{s['first_batch_clean']}/{s['weeks']} | {s['weeks_rerun']} | {s['current_did_model_work']}/{s['weeks']} | "
                     f"{s['current_clean']}/{s['weeks']} | {spread} |")
    lines += ["", "## Current result per week", "", "`W` model work and clean synthesis, `w` model work with failed synthesis sections, `-` no model work.", "",
              "| backend | " + " | ".join(result["weeks"]) + " |", "|---|" + "---|" * len(result["weeks"])]
    backends = list(dict.fromkeys(r["backend"] for r in result["rows"]))
    for backend in backends:
        marks = []
        for week in result["weeks"]:
            current = next(r["current"] for r in result["rows"] if r["backend"] == backend and r["week"] == week)
            marks.append("-" if not current or not current["did_model_work"] else ("W" if current["clean_synthesis"] else "w"))
        lines.append(f"| {backend} | " + " | ".join(marks) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--batches-root", type=Path, default=Path("data/reports/model_comparison"))
    p.add_argument("--source-batch", required=True)
    p.add_argument("--rerun-batch", default=None)
    p.add_argument("--added-batch", default=None)
    p.add_argument("--comparison-csv", type=Path, action="append", default=[])
    p.add_argument("--retired", default="", help="Comma-separated backend tags the provider no longer serves.")
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args(argv)

    result = build_matrix(read_runs(args.batches_root, args.source_batch), read_runs(args.batches_root, args.rerun_batch),
                          read_runs(args.batches_root, args.added_batch), read_comparison(args.comparison_csv),
                          {t.strip() for t in args.retired.split(",") if t.strip()})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "backend_status_matrix.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (args.out_dir / "backend_status_matrix.md").write_text(render(result), encoding="utf-8")
    with (args.out_dir / "backend_status_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result["summary"][0]))
        writer.writeheader()
        writer.writerows(result["summary"])
    print(f"{len(result['summary'])} backends, {len(result['rows'])} backend-weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
