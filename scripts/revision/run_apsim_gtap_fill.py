#!/usr/bin/env python3
"""Run the APSIM-GTAP model on an existing run's scenarios, with no LLM.

APSIM-GTAP was added to the fleet after run 20260504_222710 (May) and run
rev_20261102_llama8b_r2 (Run A). This script adds its cells to those runs
without re-extracting anything: each input is taken from the same run's
already-saved records, so the new cells see exactly the scenario that the
other models saw.

Per scenario:

* ``middle_east_fertilizer_production_loss_pct``: the run's validated
  ``world_fertilizer.middle_east_production_loss_pct`` parameter;
* ``gulf_oil_supply_loss_mbd``: the run's ``poles_jrc.supply_loss_mbd``
  parameter (fallback ``bornstein_krusell_rebelo.supply_loss_mbd``);
* ``disruption_duration_months``: ``poles_jrc`` then ``world_fertilizer``;
* ``trade_cost_multiplier``: forwarded from the run's completed ``aisdb``
  output through ``configs/upstream_forwarding_mapping.yaml``
  (``combine: first``), exactly as the macro barrier would.

A value the run does not have falls back to
``configs/baselines/hormuz_2026_analyst.yaml`` and is flagged
``analyst_baseline_fallback`` in ``apsim_gtap_fill_inputs.json``.

Records are written as ``<fill_run_id>_model_fill_<scenario>_apsim_gtap.json``
(the shape ``run_model.py`` saves) to ``--fill-state-dir``. With
``--merge-out-state-dir`` they are then merged into a copy of the source
state with ``merge_refilled_cells.merge`` (the source directory is never
modified).

    python scripts/revision/run_apsim_gtap_fill.py \
        --source-run-id 20260504_222710 --state-dir data/pipeline_state_may_filled \
        --fill-run-id fill_apsimgtap_20260504_222710 \
        --fill-state-dir data/pipeline_state_apsimgtap_fills \
        --merge-out-state-dir data/pipeline_state_may_apsimgtap \
        --report-dir docs/revision/runs/20260504_222710_apsimgtap

``--dry-run`` resolves and writes the inputs without executing the model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slurm" / "scripts"))

MODEL_ID = "apsim_gtap"
DEFAULT_BASELINE = ROOT / "configs" / "baselines" / "hormuz_2026_analyst.yaml"

# target parameter -> ordered (source model, source parameter) candidates
PARAM_SOURCES: dict[str, list[tuple[str, str]]] = {
    "middle_east_fertilizer_production_loss_pct": [("world_fertilizer", "middle_east_production_loss_pct")],
    "gulf_oil_supply_loss_mbd": [("poles_jrc", "supply_loss_mbd"), ("bornstein_krusell_rebelo", "supply_loss_mbd")],
    "disruption_duration_months": [("poles_jrc", "disruption_duration_months"),
                                   ("world_fertilizer", "disruption_duration_months")],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_param_records(state_dir: Path, run_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    """``(scenario, model) -> {name: value}`` from ``<run_id>_params_*.json``; failed records skipped."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(state_dir.glob(f"{run_id}_params_*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if str(rec.get("status") or "completed").lower() != "completed":
            continue
        sid, mid = rec.get("scenario_id"), rec.get("model_id")
        if not sid or not mid:
            continue
        params = rec.get("parameters") or []
        if isinstance(params, dict):
            values = dict(params)
        else:
            values = {p["name"]: p.get("value") for p in params if isinstance(p, dict) and "name" in p}
        out[(sid, mid)] = values
    return out


def load_model_records(state_dir: Path, run_id: str) -> dict[str, list[dict[str, Any]]]:
    """Completed and failed model records by scenario (input to the forwarding merge)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("scenario_id") and rec.get("model_id"):
            out.setdefault(rec["scenario_id"], []).append(rec)
    return out


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def resolve_inputs(
    scenario_id: str,
    params: dict[tuple[str, str], dict[str, Any]],
    model_records: list[dict[str, Any]],
    baseline_params: dict[str, Any],
    mapping: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Inputs for one scenario plus a provenance row per input and the override records."""
    from src.pipeline.upstream_forwarding import compute_downstream_inputs, merge_into_params

    resolved: dict[str, Any] = {"scenario_id": scenario_id}
    provenance: list[dict[str, Any]] = []
    for target, candidates in PARAM_SOURCES.items():
        for model, name in candidates:
            value = params.get((scenario_id, model), {}).get(name)
            if _is_number(value):
                resolved[target] = float(value)
                provenance.append({"scenario_id": scenario_id, "input": target, "value": float(value),
                                   "source": f"{model}.{name}", "kind": "run_parameter"})
                break
        else:
            value = baseline_params.get(target)
            resolved[target] = value
            provenance.append({"scenario_id": scenario_id, "input": target, "value": value,
                               "source": "configs/baselines/hormuz_2026_analyst.yaml", "kind": "analyst_baseline_fallback"})

    # trade_cost_multiplier: the forwarding rule, starting from the baseline value.
    seed = {"trade_cost_multiplier": baseline_params.get("trade_cost_multiplier")}
    computed = compute_downstream_inputs(scenario_id, model_records, mapping, target_models={MODEL_ID})
    merged, records = merge_into_params(MODEL_ID, seed, computed.get(MODEL_ID, []))
    record_dicts = [r.to_dict() for r in records]
    resolved["trade_cost_multiplier"] = merged.get("trade_cost_multiplier")
    if record_dicts:
        rec = record_dicts[0]
        provenance.append({"scenario_id": scenario_id, "input": "trade_cost_multiplier",
                           "value": resolved["trade_cost_multiplier"],
                           "source": f"{rec.get('source_model_id')}.{rec.get('source_field')}",
                           "kind": "forwarded_model_output"})
    else:
        provenance.append({"scenario_id": scenario_id, "input": "trade_cost_multiplier",
                           "value": resolved["trade_cost_multiplier"],
                           "source": "configs/baselines/hormuz_2026_analyst.yaml", "kind": "analyst_baseline_fallback"})
    resolved["coupling_elasticity"] = float(baseline_params.get("coupling_elasticity", 1.0))
    return resolved, provenance, record_dicts


def execute_cell(adapter: Any, params: dict[str, Any], fill_run_id: str, overrides: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate -> translate -> execute, returning a ``run_model.py``-shaped record."""
    from src.models.base import resolve_implementation_mode

    rec: dict[str, Any] = {
        "scenario_id": params["scenario_id"], "model_id": MODEL_ID, "task_id": None,
        "manifest_name": f"{fill_run_id}_apsim_gtap_fill", "node": "fill", "slurm_job_id": "fill",
        "resource_class": "cpu", "started_at": _now(), "parameters": params,
    }
    if overrides:
        rec["upstream_overrides"] = overrides
    t0 = time.monotonic()
    validation = adapter.validate_inputs(params)
    if not validation.valid:
        rec.update(status="failed", error_message="Validation failed: " + "; ".join(validation.errors),
                   completed_at=_now())
        return rec
    try:
        output = adapter.execute(adapter.translate_inputs(params))
    except NotImplementedError as e:
        rec.update(status="skipped", error_message=f"Not yet implemented: {e}", completed_at=_now())
        return rec
    except Exception as e:  # noqa: BLE001 — record, never crash the fill
        rec.update(status="failed", error_message=f"{type(e).__name__}: {e}",
                   runtime_seconds=time.monotonic() - t0, completed_at=_now())
        return rec
    outputs = dict(output.outputs)
    if overrides:
        outputs["_upstream_overrides"] = overrides
    rec.update(status="completed", outputs=outputs, metadata=dict(output.metadata or {}),
               implementation_mode=resolve_implementation_mode(output, adapter).value,
               runtime_seconds=time.monotonic() - t0, completed_at=_now())
    if output.uncertainty is not None:
        rec["uncertainty"] = output.uncertainty.model_dump()
    return rec


def run_fill(
    source_run_id: str,
    state_dir: Path,
    fill_run_id: str,
    fill_state_dir: Path,
    report_dir: Path,
    baseline_path: Path = DEFAULT_BASELINE,
    scenarios: list[str] | None = None,
    dry_run: bool = False,
    adapter: Any = None,
) -> dict[str, Any]:
    from run_deterministic_baseline import baseline_parameter_sets, load_baseline  # type: ignore
    from src.pipeline.upstream_forwarding import load_mapping

    params = load_param_records(state_dir, source_run_id)
    model_records = load_model_records(state_dir, source_run_id)
    if not params:
        raise SystemExit(f"no {source_run_id}_params_*.json records in {state_dir}")
    scenario_ids = sorted({sid for sid, _ in params})
    if scenarios:
        scenario_ids = [s for s in scenario_ids if s in set(scenarios)]
    baseline = load_baseline(baseline_path)
    base_by_scenario = {sid: p for sid, mid, p in baseline_parameter_sets(baseline, model_ids=[MODEL_ID])}
    mapping = load_mapping()

    if adapter is None and not dry_run:
        from src.models.registry import build_default_registry, default_config_dir
        adapter = build_default_registry(default_config_dir()).get(MODEL_ID)

    fill_state_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    provenance: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    for sid in scenario_ids:
        inputs, prov, overrides = resolve_inputs(sid, params, model_records.get(sid, []),
                                                 base_by_scenario.get(sid, {}), mapping)
        provenance.extend(prov)
        if dry_run:
            cells.append({"scenario_id": sid, "status": "dry_run", "inputs": inputs})
            continue
        rec = execute_cell(adapter, inputs, fill_run_id, overrides)
        path = fill_state_dir / f"{fill_run_id}_model_fill_{sid}_{MODEL_ID}.json"
        path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
        out = rec.get("outputs") or {}
        cells.append({"scenario_id": sid, "status": rec["status"], "inputs": inputs,
                      "error_message": rec.get("error_message"),
                      "us_gdp_pct": out.get("us_gdp_pct"), "gulf_gdp_pct": out.get("gulf_gdp_pct"),
                      "us_maize_yield_change_pct": out.get("us_maize_yield_change_pct"),
                      "converged": out.get("converged"),
                      "zero_shock_residual_gdp_pct": out.get("zero_shock_residual_gdp_pct"),
                      "runtime_seconds": rec.get("runtime_seconds")})
        print(f"[apsim_gtap fill] {sid}: {rec['status']}"
              + (f" ({rec.get('error_message')})" if rec.get("error_message") else ""))

    summary = {"source_run_id": source_run_id, "fill_run_id": fill_run_id, "state_dir": str(state_dir),
               "generated_at": _now(), "dry_run": dry_run, "cells": cells, "inputs_provenance": provenance,
               "fallbacks": [p for p in provenance if p["kind"] == "analyst_baseline_fallback"]}
    (report_dir / "apsim_gtap_fill_inputs.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (report_dir / "apsim_gtap_fill.md").write_text(render(summary), encoding="utf-8")
    return summary


def render(summary: dict[str, Any]) -> str:
    lines = [f"# APSIM-GTAP cells for run `{summary['source_run_id']}`", "",
             f"Executed under `{summary['fill_run_id']}` with no LLM call. Inputs come from the run's own "
             "parameter records and model outputs; the original synthesis saw none of these cells.", "",
             "## Inputs", "", "| scenario | input | value | source | kind |", "|---|---|---|---|---|"]
    lines += [f"| {p['scenario_id']} | {p['input']} | {p['value']} | {p['source']} | {p['kind']} |"
              for p in summary["inputs_provenance"]]
    lines += ["", f"Analyst-baseline fallbacks: {len(summary['fallbacks'])}", "", "## Results", "",
              "| scenario | status | US GDP % | Gulf GDP % | US maize yield % | converged | zero-shock residual | runtime s |",
              "|---|---|---|---|---|---|---|---|"]
    for c in summary["cells"]:
        lines.append(f"| {c['scenario_id']} | {c['status']} | {c.get('us_gdp_pct')} | {c.get('gulf_gdp_pct')} | "
                     f"{c.get('us_maize_yield_change_pct')} | {c.get('converged')} | "
                     f"{c.get('zero_shock_residual_gdp_pct')} | {c.get('runtime_seconds')} |")
    errors = [c for c in summary["cells"] if c.get("error_message")]
    if errors:
        lines += ["", "## Errors", ""] + [f"- {c['scenario_id']}: {c['error_message']}" for c in errors]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-run-id", required=True)
    p.add_argument("--state-dir", required=True, help="state dir holding the source run's records (read only)")
    p.add_argument("--fill-run-id", required=True)
    p.add_argument("--fill-state-dir", default="data/pipeline_state_apsimgtap_fills")
    p.add_argument("--report-dir", required=True)
    p.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    p.add_argument("--scenarios", nargs="*", default=None)
    p.add_argument("--merge-out-state-dir", default=None,
                   help="copy the source run's state here and add the new cells (merge_refilled_cells.merge)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    summary = run_fill(args.source_run_id, Path(args.state_dir), args.fill_run_id, Path(args.fill_state_dir),
                       Path(args.report_dir), Path(args.baseline), args.scenarios, args.dry_run)
    if args.merge_out_state_dir and not args.dry_run:
        sys.path.insert(0, str(ROOT / "scripts" / "revision"))
        from merge_refilled_cells import merge, render as render_merge  # type: ignore

        result = merge(args.source_run_id, args.fill_run_id, Path(args.state_dir), Path(args.merge_out_state_dir),
                       fill_state_dir=Path(args.fill_state_dir),
                       note=(f"APSIM-GTAP added after {args.source_run_id}; executed from the run's own "
                             "parameter records and model outputs with no LLM call."))
        report = Path(args.report_dir)
        (report / "refilled_cells.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        (report / "refilled_cells.md").write_text(render_merge(result), encoding="utf-8")
        print(f"merged: added {len(result['added'])} cells {result['added_by_status']}")
    statuses = [c["status"] for c in summary["cells"]]
    return 0 if all(s in ("completed", "dry_run") for s in statuses) else 1


if __name__ == "__main__":
    sys.exit(main())
