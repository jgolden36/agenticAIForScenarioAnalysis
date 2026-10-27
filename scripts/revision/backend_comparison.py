#!/usr/bin/env python3
"""Backend comparison from saved weekly runs (Reviewer 2, point 5; Reviewer 1, point 5).

Walks local copies of the cluster's report and state directories, one set
per LLM backend, assesses every run with the shared
``src.synthesis.run_health.assess_run`` definition, and emits:

* ``backend_comparison.csv``: one row per (backend, run/week) with the
  denominator (cells attempted = parameter sets, or model records when the
  parameter records are absent), completed / failed / skipped counts,
  synthesis sections failed, the clean-synthesis flag, model-execution
  runtime and span, seconds per completed model run, and the principal
  failure reasons.
* ``backend_comparison.md``: per-backend summary (weeks, clean weeks,
  mean and per-week completed counts and wall-clock), a failed-backends
  table (backends with no clean week and their failure classes), and the
  clean-synthesis definition.
* ``backend_comparison.json``: everything above plus each run's full
  assessment.
* ``backend_comparison.png``: dot plots (one point per week, mean
  overlaid) of completed model runs and model-execution time per backend.

Backend identification: ``<run_id>_scenarios.json -> config.llm.model``
(the SLURM drivers bake the served vLLM model into the saved config).
When a layout stores one backend per sub-directory without state files,
pass ``--backend-map map.yaml`` with ``{"<dir name or run id>": "<backend>"}``.

Usage::

    python scripts/revision/backend_comparison.py \
        --reports-root cluster_copy/data/reports --state-root cluster_copy/data/pipeline_state \
        --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.synthesis.run_health import CLEAN_SYNTHESIS_DEFINITION, assess_run, load_run_inputs  # noqa: E402

_WEEK_RE = re.compile(r"^weekly_(\d{8})$")


def discover_runs(reports_root: Path) -> list[tuple[str, Path]]:
    """``(run_id, report_dir)`` for every run-shaped directory under reports_root (recursive)."""
    runs: list[tuple[str, Path]] = []
    if not reports_root.exists():
        return runs
    for d in sorted(reports_root.rglob("*")):
        if not d.is_dir():
            continue
        if (d / "synthesis.json").exists() or (d / "summary.json").exists() or (d / "csv").exists():
            runs.append((d.name, d))
    return runs


def _has_state(c: Path, run_id: str) -> bool:
    return (c / f"{run_id}_scenarios.json").exists() or any(c.glob(f"{run_id}_model_*.json"))


def _find_state_dir(run_id: str, state_root: Path | None, report_dir: Path, reports_root: Path | None = None) -> Path | None:
    """Locate the state directory holding ``run_id``'s files.

    The same weekly run id can exist once per backend (one ``weekly_<date>``
    per backend directory), so a state directory that mirrors the report
    directory's position under ``reports_root`` (``reports/<backend>/<run>``
    -> ``state/<backend>``) is preferred over any other directory that
    merely contains files for that run id.
    """
    if state_root is None:
        return None
    mirrored: list[Path] = []
    if reports_root is not None:
        try:
            rel = report_dir.relative_to(reports_root)
        except ValueError:
            rel = None
        if rel is not None:
            # state/<backend>/<run_id> and state/<backend> (the run dir itself, then its parent chain).
            mirrored = [state_root / rel] + [state_root / p for p in rel.parents]
    for c in mirrored:
        if c.is_dir() and _has_state(c, run_id):
            return c
    candidates = [state_root] + sorted(p for p in state_root.rglob("*") if p.is_dir())
    for c in candidates:
        if _has_state(c, run_id):
            return c
    return None


def _backend_for(run_id: str, report_dir: Path, assessment: dict[str, Any], backend_map: dict[str, str]) -> str:
    model = (assessment.get("backend") or {}).get("model")
    if model:
        return str(model)
    for key in (report_dir.name, report_dir.parent.name, run_id):
        if key in backend_map:
            return backend_map[key]
    return "unknown"


def _week_for(run_id: str) -> str:
    m = _WEEK_RE.match(run_id)
    return m.group(1) if m else run_id


def compare(reports_root: Path, state_root: Path | None, backend_map: dict[str, str] | None = None) -> dict[str, Any]:
    backend_map = backend_map or {}
    rows: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    for run_id, report_dir in discover_runs(reports_root):
        sdir = _find_state_dir(run_id, state_root, report_dir, reports_root)
        inputs = load_run_inputs(run_id, sdir if sdir else Path("/nonexistent"), report_dir)
        a = assess_run(run_id, **inputs)
        backend = _backend_for(run_id, report_dir, a, backend_map)
        a["backend_label"] = backend
        a["report_dir"] = str(report_dir)
        assessments.append(a)
        cells = a["cells"]
        attempted = cells["parameter_sets"] or cells["model_records"]
        wc = a["wall_clock"]
        rows.append({
            "backend": backend,
            "run_id": run_id,
            "week": _week_for(run_id),
            "cells_attempted": attempted,
            "denominator_basis": "parameter_sets" if cells["parameter_sets"] else "model_records",
            "grid_cells": a["denominators"]["grid"],
            "completed": cells["completed"],
            "failed": cells["failed"],
            "skipped": cells["skipped"],
            "synthesis_outcomes": a["criteria"]["synthesis_results_count"],
            "sections_failed": a["criteria"]["sections_failed"],
            "sections_total": a["criteria"]["sections_total"],
            "clean_synthesis": a["clean_synthesis"],
            "model_runtime_sum_s": wc["stages"].get("model_execution_runtime_sum_seconds"),
            "model_span_s": wc["stages"].get("model_execution_span_seconds"),
            "param_llm_s": wc["stages"].get("parameter_extraction_llm_seconds"),
            "s_per_completed_model": wc.get("seconds_per_completed_model_run"),
            "review_mode": wc.get("review_mode"),
            "failure_reasons": "; ".join(
                f"{k}: {v}" for k, v in {**a["failure_reasons"]["synthesis_section_errors"],
                                        **a["failure_reasons"]["bash_failures_by_stage"]}.items()
            ),
        })

    by_backend: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_backend[r["backend"]].append(r)
    summary = {}
    for b, rs in sorted(by_backend.items()):
        completed = [r["completed"] for r in rs]
        spans = [r["model_span_s"] for r in rs if r["model_span_s"] is not None]
        clean_weeks = [r["week"] for r in rs if r["clean_synthesis"] is True]
        summary[b] = {
            "weeks": sorted(r["week"] for r in rs),
            "n_runs": len(rs),
            "clean_weeks": sorted(clean_weeks),
            "clean_rate": round(len(clean_weeks) / len(rs), 3) if rs else None,
            "completed_per_week": completed,
            "completed_mean": round(statistics.mean(completed), 2) if completed else None,
            "completed_median": statistics.median(completed) if completed else None,
            "model_span_s_per_week": spans,
            "model_span_s_mean": round(statistics.mean(spans), 1) if spans else None,
            "attempted_per_week": [r["cells_attempted"] for r in rs],
            "principal_failure_reasons": sorted({r["failure_reasons"] for r in rs if r["failure_reasons"]}),
        }
    failed_backends = {b: s for b, s in summary.items() if not s["clean_weeks"]}
    return {
        "definition": CLEAN_SYNTHESIS_DEFINITION,
        "rows": rows,
        "summary": summary,
        "failed_backends": failed_backends,
        "assessments": assessments,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = ["# LLM backend comparison", "", f"Clean synthesis definition: {result['definition']}", "",
             "Denominator: `cells_attempted` is the number of (scenario, model) parameter sets Module 2 produced for the run "
             "(or Module 3 records when parameter records are unavailable); `grid_cells` is scenarios x model specs. "
             "Wall-clock excludes analyst review (auto-approved in batch mode).", "",
             "## Per backend", "",
             "| backend | runs | clean weeks | clean rate | completed per week | mean completed | model span s per week | mean span s |",
             "|---|---|---|---|---|---|---|---|"]
    for b, s in result["summary"].items():
        lines.append(
            f"| {b} | {s['n_runs']} | {', '.join(s['clean_weeks']) or '-'} | {s['clean_rate']} | "
            f"{', '.join(str(c) for c in s['completed_per_week'])} | {s['completed_mean']} | "
            f"{', '.join(str(x) for x in s['model_span_s_per_week']) or '-'} | {s['model_span_s_mean']} |"
        )
    lines += ["", "## Backends with no clean week", ""]
    if result["failed_backends"]:
        lines += ["| backend | runs | principal failure reasons |", "|---|---|---|"]
        for b, s in result["failed_backends"].items():
            lines.append(f"| {b} | {s['n_runs']} | {'; '.join(s['principal_failure_reasons']) or 'no synthesis state / no outcomes'} |")
    else:
        lines.append("_none_")
    lines += ["", "## Per run", "",
              "| backend | week | attempted | completed | failed | skipped | outcomes | sections failed | clean | model span s | s per completed model |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        lines.append(
            f"| {r['backend']} | {r['week']} | {r['cells_attempted']} | {r['completed']} | {r['failed']} | {r['skipped']} | "
            f"{r['synthesis_outcomes']} | {r['sections_failed']} | {r['clean_synthesis']} | {r['model_span_s']} | {r['s_per_completed_model']} |"
        )
    lines.append("")
    return "\n".join(lines)


def plot(result: dict[str, Any], out: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return None
    backends = list(result["summary"])
    if not backends:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(max(7, 1.6 * len(backends) + 3), 4.2))
    for ax, key, label in ((axes[0], "completed", "Completed model runs per week"),
                           (axes[1], "model_span_s", "Model-execution span per week (s)")):
        for i, b in enumerate(backends):
            ys = [r[key] for r in result["rows"] if r["backend"] == b and r[key] is not None]
            if not ys:
                continue
            xs = [i + (j - (len(ys) - 1) / 2) * 0.04 for j in range(len(ys))]
            ax.scatter(xs, ys, s=18, alpha=0.8, label=None)
            ax.hlines(statistics.mean(ys), i - 0.25, i + 0.25, color="black", linewidth=1.5)
        ax.set_xticks(range(len(backends)))
        ax.set_xticklabels(backends, rotation=25, ha="right", fontsize=8)
        ax.set_title(label, fontsize=9)
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("Backend comparison: one dot per weekly run, bar = mean", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reports-root", required=True)
    p.add_argument("--state-root", default=None)
    p.add_argument("--backend-map", default=None, help="YAML/JSON mapping of dir name or run id -> backend label.")
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)

    backend_map: dict[str, str] = {}
    if args.backend_map:
        text = Path(args.backend_map).read_text(encoding="utf-8")
        try:
            import yaml

            backend_map = yaml.safe_load(text) or {}
        except Exception:  # noqa: BLE001
            backend_map = json.loads(text)
    result = compare(Path(args.reports_root), Path(args.state_root) if args.state_root else None, backend_map)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "backend_comparison.csv", "w", newline="", encoding="utf-8") as f:
        if result["rows"]:
            w = csv.DictWriter(f, fieldnames=list(result["rows"][0].keys()))
            w.writeheader()
            w.writerows(result["rows"])
    (out_dir / "backend_comparison.md").write_text(render_markdown(result), encoding="utf-8")
    (out_dir / "backend_comparison.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    png = plot(result, out_dir / "backend_comparison.png")
    print(json.dumps({"runs": len(result["rows"]), "backends": list(result["summary"]), "png": str(png) if png else None}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
