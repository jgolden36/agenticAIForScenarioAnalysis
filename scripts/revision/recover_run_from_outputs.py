#!/usr/bin/env python3
"""Rebuild a run's per-cell model records from ``data/outputs/``.

Why this exists
---------------
Before the fix in ``slurm/scripts/run_model.py`` (tier-qualified state
filenames), the three Stage 3 tiers (commodity, commodity_downstream,
macro) each restarted their array index at 0 and wrote their records to
``<run_id>_model_<task_id>.json``. Later tiers therefore overwrote earlier
tiers' records before synthesis and export ran. On run ``20260504_222710``
every macro-tier record occupies task ids 0-59 and only commodity records
with ids 60-98 survived, which is why Scenarios D and E appear to have run
"only the five anchors".

The per-model artefacts written by ``run_model._persist_per_model_outputs``
under ``data/outputs/<scenario>/<model>/{metadata,output}.json`` are keyed
by (scenario, model), carry the ``run_id``, and were not overwritten by
the collision (only by later *runs*). This script reconstructs the full
record set for one run from those artefacts, writes them as tier-qualified
state files that every downstream reader already globs
(``<run_id>_model_*.json``), and emits a recovery report so the manuscript
can state exactly which cells were recovered, which were lost to later
runs, and which never existed.

Usage
-----
    python scripts/revision/recover_run_from_outputs.py \
        --run-id 20260504_222710 \
        --outputs-root data/outputs \
        --state-dir data/pipeline_state \
        --report-dir docs/revision

Then re-run the downstream stages on the recovered record set::

    HORMUZ_RUN_ID=20260504_222710 python slurm/scripts/run_validation.py
    HORMUZ_RUN_ID=20260504_222710 python slurm/scripts/export_results.py --no-llm
    HORMUZ_RUN_ID=20260504_222710 python slurm/scripts/visualize_results.py
    HORMUZ_RUN_ID=20260504_222710 python slurm/scripts/build_coverage_ledger.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.common.types import ANALYTICAL_LEVEL_ORDER, AnalyticalLevel, Scenario  # noqa: E402
from src.models.base import resolve_implementation_mode  # noqa: E402

_COMMODITY_LEVELS = {AnalyticalLevel.COMBAT, AnalyticalLevel.COMMODITY}
_DOWNSTREAM_LEVELS = {AnalyticalLevel.COMMODITY_DOWNSTREAM}

CellClass = str  # "present" | "recovered" | "stale_other_run" | "missing"


def _tier_for_level(level: AnalyticalLevel | None) -> str:
    if level in _COMMODITY_LEVELS:
        return "commodity"
    if level in _DOWNSTREAM_LEVELS:
        return "commodity_downstream"
    if level is None:
        return "unknown"
    return "macro"


def _level_by_model() -> dict[str, AnalyticalLevel]:
    """Resolve analytical levels from the registry (best effort)."""
    try:
        from src.models.registry import build_default_registry, default_config_dir

        registry = build_default_registry(default_config_dir())
        return {a.model_id: a.analytical_level for a in registry.all_adapters()}
    except Exception:  # noqa: BLE001 — recovery must not depend on optional deps
        return {}


def _model_ids_in_grid() -> list[str]:
    try:
        from src.parameters.model_specs import ALL_MODEL_SPECS

        return list(ALL_MODEL_SPECS)
    except Exception:  # noqa: BLE001
        return []


def _load_json(path: Path) -> Any | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _existing_records(state_dir: Path, run_id: str) -> dict[tuple[str, str], Path]:
    """Map (scenario, model) -> state file for records already on disk."""
    out: dict[tuple[str, str], Path] = {}
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        rec = _load_json(path)
        if not isinstance(rec, dict):
            continue
        key = (str(rec.get("scenario_id")), str(rec.get("model_id")))
        out[key] = path
    return out


def _task_id_ranges(state_dir: Path, run_id: str, level_by_model: dict) -> dict[str, dict]:
    """Evidence of the tier collision: task-id ranges per tier in the state dir."""
    per_tier: dict[str, list[int]] = defaultdict(list)
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        rec = _load_json(path)
        if not isinstance(rec, dict):
            continue
        tier = _tier_for_level(level_by_model.get(str(rec.get("model_id"))))
        try:
            per_tier[tier].append(int(rec.get("task_id")))
        except (TypeError, ValueError):
            continue
    return {
        tier: {"count": len(ids), "min_task_id": min(ids), "max_task_id": max(ids)}
        for tier, ids in per_tier.items()
        if ids
    }


def _record_from_outputs(
    run_id: str,
    scenario_id: str,
    model_id: str,
    metadata: dict,
    outputs: dict | None,
    tier: str,
    source_path: Path,
) -> dict:
    """Shape a state record identical to what run_model.py writes."""
    status = str(metadata.get("status") or "").lower()
    rec: dict[str, Any] = {
        "scenario_id": scenario_id,
        "model_id": model_id,
        "task_id": metadata.get("task_id"),
        "manifest_name": metadata.get("manifest_name") or f"models_{tier}",
        "node": metadata.get("node"),
        "slurm_job_id": metadata.get("slurm_job_id"),
        "resource_class": metadata.get("resource_class"),
        "started_at": metadata.get("started_at"),
        "completed_at": metadata.get("completed_at"),
        "runtime_seconds": metadata.get("runtime_seconds"),
        "status": status,
        "error_message": metadata.get("error_message"),
        "metadata": metadata.get("adapter_metadata") or {},
        "recovered_from": str(source_path),
        "recovered_at": datetime.now(timezone.utc).isoformat(),
        "recovered": True,
    }
    if metadata.get("upstream_overrides"):
        rec["upstream_overrides"] = metadata["upstream_overrides"]
    if status == "completed":
        rec["outputs"] = outputs or {}
        mode = metadata.get("implementation_mode")
        if not mode:
            mode = resolve_implementation_mode(None, None, outputs=outputs or {}).value
        rec["implementation_mode"] = mode
    return rec


def recover_run(
    run_id: str,
    outputs_root: Path,
    state_dir: Path,
    report_dir: Path | None = None,
    *,
    overwrite_existing: bool = False,
    dry_run: bool = False,
    scenario_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Recover one run's model records. Returns the recovery report dict."""
    level_by_model = _level_by_model()
    scenario_ids = scenario_ids or [s.value for s in Scenario]
    model_ids = model_ids or _model_ids_in_grid()
    existing = _existing_records(state_dir, run_id)

    classes: dict[tuple[str, str], CellClass] = {}
    stale_detail: dict[tuple[str, str], str | None] = {}
    recovered: list[dict] = []
    written: list[str] = []

    for scenario_id in scenario_ids:
        for model_id in model_ids:
            key = (scenario_id, model_id)
            cell_dir = outputs_root / scenario_id / model_id
            metadata = _load_json(cell_dir / "metadata.json")
            if key in existing and not overwrite_existing:
                classes[key] = "present"
                continue
            if not isinstance(metadata, dict):
                classes[key] = "present" if key in existing else "missing"
                continue
            entry_run = metadata.get("run_id")
            if entry_run != run_id:
                classes[key] = "present" if key in existing else "stale_other_run"
                stale_detail[key] = entry_run
                continue
            outputs = _load_json(cell_dir / "output.json")
            tier = _tier_for_level(level_by_model.get(model_id))
            rec = _record_from_outputs(
                run_id,
                scenario_id,
                model_id,
                metadata,
                outputs if isinstance(outputs, dict) else None,
                tier,
                cell_dir / "metadata.json",
            )
            recovered.append(rec)
            classes[key] = "recovered"
            target = state_dir / f"{run_id}_model_recovered_{tier}_{scenario_id}_{model_id}.json"
            if not dry_run:
                state_dir.mkdir(parents=True, exist_ok=True)
                if key in existing and overwrite_existing:
                    existing[key].unlink(missing_ok=True)
                with open(target, "w") as f:
                    json.dump(rec, f, indent=2, default=str)
            written.append(str(target))

    by_scenario: dict[str, Counter] = defaultdict(Counter)
    for (scenario_id, _model_id), cls in classes.items():
        by_scenario[scenario_id][cls] += 1
    totals = Counter(classes.values())

    report: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outputs_root": str(outputs_root),
        "state_dir": str(state_dir),
        "dry_run": dry_run,
        "grid": {"scenarios": len(scenario_ids), "models": len(model_ids)},
        "totals": dict(totals),
        "by_scenario": {s: dict(c) for s, c in by_scenario.items()},
        "existing_task_id_ranges_by_tier": _task_id_ranges(state_dir, run_id, level_by_model),
        "recovered_cells": [
            {
                "scenario_id": r["scenario_id"],
                "model_id": r["model_id"],
                "status": r["status"],
                "implementation_mode": r.get("implementation_mode"),
                "task_id": r.get("task_id"),
            }
            for r in recovered
        ],
        "stale_cells": [
            {"scenario_id": s, "model_id": m, "found_run_id": stale_detail[(s, m)]}
            for (s, m), cls in classes.items()
            if cls == "stale_other_run"
        ],
        "missing_cells": [
            {"scenario_id": s, "model_id": m}
            for (s, m), cls in classes.items()
            if cls == "missing"
        ],
        "files_written": written,
    }

    if report_dir is not None and not dry_run:
        report_dir.mkdir(parents=True, exist_ok=True)
        with open(report_dir / f"recovery_{run_id}.json", "w") as f:
            json.dump(report, f, indent=2, default=str)
        with open(report_dir / f"recovery_{run_id}.md", "w") as f:
            f.write(render_report_markdown(report))
    return report


def render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Recovery report for run `{report['run_id']}`",
        "",
        f"Generated {report['generated_at']}. Outputs root: `{report['outputs_root']}`.",
        "",
        "## Cell classes",
        "",
        "| class | count |",
        "|---|---|",
    ]
    for cls in ("present", "recovered", "stale_other_run", "missing"):
        lines.append(f"| {cls} | {report['totals'].get(cls, 0)} |")
    lines += ["", "## By scenario", "", "| scenario | present | recovered | stale_other_run | missing |", "|---|---|---|---|---|"]
    for scenario_id, counts in report["by_scenario"].items():
        lines.append(
            f"| {scenario_id} | {counts.get('present', 0)} | {counts.get('recovered', 0)} | "
            f"{counts.get('stale_other_run', 0)} | {counts.get('missing', 0)} |"
        )
    ranges = report.get("existing_task_id_ranges_by_tier") or {}
    if ranges:
        lines += ["", "## Task-id ranges of records already in the state dir (collision evidence)", "", "| tier | records | min task id | max task id |", "|---|---|---|---|"]
        for tier, r in ranges.items():
            lines.append(f"| {tier} | {r['count']} | {r['min_task_id']} | {r['max_task_id']} |")
    if report["recovered_cells"]:
        lines += ["", "## Recovered cells", "", "| scenario | model | status | implementation mode |", "|---|---|---|---|"]
        for c in report["recovered_cells"]:
            lines.append(f"| {c['scenario_id']} | {c['model_id']} | {c['status']} | {c.get('implementation_mode') or ''} |")
    if report["stale_cells"]:
        lines += ["", "## Cells whose data/outputs entry belongs to another run (not recovered)", ""]
        for c in report["stale_cells"]:
            lines.append(f"- {c['scenario_id']} / {c['model_id']} (run_id on disk: {c['found_run_id']})")
    if report["missing_cells"]:
        lines += ["", "## Cells with no record anywhere", ""]
        for c in report["missing_cells"]:
            lines.append(f"- {c['scenario_id']} / {c['model_id']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--outputs-root", default="data/outputs")
    parser.add_argument("--state-dir", default="data/pipeline_state")
    parser.add_argument("--report-dir", default="docs/revision")
    parser.add_argument("--overwrite-existing", action="store_true", help="Replace records already in the state dir with the data/outputs copy.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    report = recover_run(
        args.run_id,
        Path(args.outputs_root),
        Path(args.state_dir),
        Path(args.report_dir),
        overwrite_existing=args.overwrite_existing,
        dry_run=args.dry_run,
    )
    print(json.dumps({k: report[k] for k in ("run_id", "totals", "by_scenario", "existing_task_id_ranges_by_tier")}, indent=2))
    print(f"{len(report['files_written'])} record(s) {'would be ' if args.dry_run else ''}written to {args.state_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
