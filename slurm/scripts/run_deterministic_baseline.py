#!/usr/bin/env python3
"""Deterministic (LLM-free) baseline run of Modules 2-4 (Reviewer 2, point 1).

Replaces the two LLM stages with an analyst-authored baseline file
(``configs/baselines/hormuz_2026_analyst.yaml``): scenario labels and
narratives come from the file, every (scenario, model) parameter set is
read from it, Module 3 runs the registered adapters through the same
``ModelExecutor`` the imperative orchestrator uses (upstream forwarding
on by default), Module 4 runs the same consistency checks, and the
synthesis is produced by ``src.synthesis.templated`` (fixed prose, numbers
copied verbatim). No language model is constructed at any point.

The state and report files have the same names and shapes as a SLURM run
(``<run_id>_scenarios.json``, ``<run_id>_params_<n>.json``,
``<run_id>_model_baseline_<n>.json``, ``<run_id>_synthesis.json`` under
``data/pipeline_state``; ``synthesis.json``, ``summary.json``, per-scenario
Markdown under ``data/reports/<run_id>``), so ``export_results.py``,
``build_coverage_ledger.py``, ``run_fidelity_audit.py`` and
``scripts/revision/compare_runs.py`` run on it unchanged. Wall-clock per
stage is recorded in ``run_health.wall_clock.stages`` and in
``data/reports/<run_id>/baseline_run.json``.

Usage::

    python slurm/scripts/run_deterministic_baseline.py \
        --baseline configs/baselines/hormuz_2026_analyst.yaml --run-id baseline_analyst
    # subset, forwarding off, custom location:
    python slurm/scripts/run_deterministic_baseline.py --baseline ... --run-id b1 \
        --scenarios swift_contained --models poles_jrc,fed_oil,pycge --no-forwarding \
        --output-root /tmp/baseline_out
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BASELINE_MANIFEST_NAME = "models_baseline"
SYNTHESIS_METHOD = "templated"


# ---------------------------------------------------------------------------
# Baseline file
# ---------------------------------------------------------------------------


def load_baseline(path: Path | str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "scenarios" not in data or "models" not in data:
        raise ValueError(f"{path}: baseline file needs 'scenarios' and 'models' sections")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def baseline_parameter_sets(
    baseline: dict[str, Any],
    scenario_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
) -> list[tuple[str, str, dict[str, Any]]]:
    """``(scenario_id, model_id, params)`` for every cell the baseline defines.

    ``default`` is merged with ``by_scenario.<scenario_id>``; a model with no
    entry for a scenario is still emitted with its defaults when it has a
    ``default`` block, and skipped otherwise. ``scenario_id`` is injected
    the way ``dispatch_models._build_entry`` does for the LLM path.
    """
    wanted_scenarios = [s["scenario_id"] for s in baseline["scenarios"]]
    if scenario_ids:
        wanted_scenarios = [s for s in wanted_scenarios if s in set(scenario_ids)]
    models = baseline["models"] or {}
    wanted_models = list(models)
    if model_ids:
        wanted_models = [m for m in wanted_models if m in set(model_ids)]
    cells: list[tuple[str, str, dict[str, Any]]] = []
    for sid in wanted_scenarios:
        for mid in wanted_models:
            block = models.get(mid) or {}
            default = block.get("default")
            per = (block.get("by_scenario") or {}).get(sid)
            if default is None and per is None:
                continue
            params = _deep_merge(default or {}, per or {})
            params.setdefault("scenario_id", sid)
            cells.append((sid, mid, params))
    return cells


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def _result_record(result: Any, task_id: int, started_at: str, completed_at: str) -> dict[str, Any]:
    """``ModelExecutionResult`` -> the dict shape ``run_model.py`` saves."""
    status = result.status.value if hasattr(result.status, "value") else str(result.status)
    rec: dict[str, Any] = {
        "scenario_id": result.scenario_id.value if hasattr(result.scenario_id, "value") else str(result.scenario_id),
        "model_id": result.model_id,
        "task_id": task_id,
        "manifest_name": BASELINE_MANIFEST_NAME,
        "node": "local",
        "slurm_job_id": "local",
        "resource_class": "cpu",
        "status": status,
        "started_at": (result.started_at.isoformat() if result.started_at else started_at),
        "completed_at": (result.completed_at.isoformat() if result.completed_at else completed_at),
        "runtime_seconds": result.runtime_seconds,
        "error_message": result.error_message,
    }
    if status == "completed":
        rec["outputs"] = result.outputs
        rec["metadata"] = dict(result.metadata or {})
        rec["implementation_mode"] = result.implementation_mode
        overrides = (result.outputs or {}).get("_upstream_overrides")
        if overrides:
            rec["upstream_overrides"] = overrides
        if result.uncertainty is not None:
            rec["uncertainty"] = result.uncertainty
    return rec


def run_baseline(
    baseline_path: Path,
    run_id: str,
    *,
    output_root: Path,
    scenario_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
    apply_forwarding: bool = True,
    max_parallel: int = 4,
    max_outcomes_per_model: int = 10,
    export: bool = True,
) -> dict[str, Any]:
    """Run the deterministic baseline end to end; returns the run summary."""
    from src.common.types import Scenario
    from src.models.executor import ModelExecutor
    from src.models.registry import build_default_registry, default_config_dir
    from src.pipeline.config import ExecutionConfig, PipelineConfig
    from src.pipeline.state import ModelExecutionResult, ScenarioNarrativeState
    from src.synthesis.fidelity import audit_run
    from src.synthesis.run_health import assess_run
    from src.synthesis.synthesizer import render_scenario_markdown
    from src.synthesis.templated import templated_synthesis

    output_root = Path(output_root)
    state_dir = output_root / "data" / "pipeline_state"
    report_dir = output_root / "data" / "reports" / run_id
    state_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    stage_seconds: dict[str, float] = {}
    baseline = load_baseline(baseline_path)

    # ---- Module 1 substitute: analyst-authored scenarios ----------------
    t0 = time.monotonic()
    narratives = []
    for s in baseline["scenarios"]:
        if scenario_ids and s["scenario_id"] not in set(scenario_ids):
            continue
        Scenario(s["scenario_id"])  # validate id
        narratives.append({
            "scenario_id": s["scenario_id"],
            "label": s.get("label", s["scenario_id"]),
            "narrative": str(s.get("narrative", "")).strip(),
            "quantitative_assumptions": dict(s.get("quantitative_assumptions") or {}),
            "consistency_notes": str(s.get("consistency_notes", "")),
            "validation_status": "approved",
        })
    config = PipelineConfig()
    config.llm.provider = "none"
    config.llm.model = "none (deterministic analyst baseline)"
    config.execution.max_parallel_models = max_parallel
    scenarios_state = {
        "run_id": run_id,
        "config": config.model_dump(mode="json"),
        "crisis_description": str((baseline.get("provenance") or {}).get("crisis_description", "")),
        "framework": {"source": str((baseline.get("provenance") or {}).get("framework", ""))},
        "scenario_narratives": narratives,
        "scenarios_validated": True,
        "validation_mode": "analyst_authored_baseline",
        "baseline": {
            "path": str(baseline_path),
            "baseline_id": baseline.get("baseline_id"),
            "version": baseline.get("version"),
            "authored": baseline.get("authored"),
        },
        "generated_at": _now(),
    }
    _write_json(state_dir / f"{run_id}_scenarios.json", scenarios_state)
    stage_seconds["scenario_generation_seconds"] = round(time.monotonic() - t0, 4)

    # ---- Module 2 substitute: parameter sets from the file --------------
    t0 = time.monotonic()
    cells = baseline_parameter_sets(baseline, [n["scenario_id"] for n in narratives], model_ids)
    param_records: list[dict[str, Any]] = []
    for i, (sid, mid, params) in enumerate(cells):
        plist = [
            {"name": k, "value": v, "unit": None, "confidence": "high",
             "extraction_note": "analyst-authored baseline value (no LLM extraction)"}
            for k, v in params.items()
        ]
        rec = {
            "scenario_id": sid, "model_id": mid, "status": "completed", "error_message": None,
            "warnings": [], "runtime_seconds": 0.0, "parameters": plist, "validation_status": "approved",
            "source": "analyst_baseline",
        }
        param_records.append(rec)
        _write_json(state_dir / f"{run_id}_params_{i}.json", rec)
    stage_seconds["parameter_extraction_seconds"] = round(time.monotonic() - t0, 4)

    # ---- Module 3: execution with the shared executor -------------------
    t0 = time.monotonic()
    registry = build_default_registry(default_config_dir())
    executor = ModelExecutor(registry, ExecutionConfig(max_parallel_models=max_parallel))
    model_records: list[dict[str, Any]] = []
    results_by_scenario: dict[str, list[ModelExecutionResult]] = {}
    params_by_scenario: dict[str, dict[str, dict[str, Any]]] = {}
    task_id = 0

    async def _run_all_scenarios() -> None:
        # One event loop for every scenario: the executor's semaphore binds
        # to the loop that first uses it, so a fresh asyncio.run() per
        # scenario would drop every model after the first scenario.
        nonlocal task_id
        for n in narratives:
            sid = n["scenario_id"]
            param_dict = {mid: dict(p) for s, mid, p in cells if s == sid and registry.get(mid) is not None}
            missing = sorted({mid for s, mid, _ in cells if s == sid and registry.get(mid) is None})
            params_by_scenario[sid] = param_dict
            if not param_dict:
                results_by_scenario[sid] = []
                continue
            started = _now()
            results = await executor.execute_all(Scenario(sid), param_dict, apply_upstream_forwarding=apply_forwarding)
            completed = _now()
            results_by_scenario[sid] = results
            seen: set[str] = set()
            for r in results:
                seen.add(r.model_id)
                rec = _result_record(r, task_id, started, completed)
                model_records.append(rec)
                _write_json(state_dir / f"{run_id}_model_baseline_{task_id}.json", rec)
                task_id += 1
            # A cell the executor dropped (it logs and skips unexpected
            # exceptions) or whose adapter is not registered still gets an
            # explicit failed record so the coverage ledger can see it.
            for mid, reason in [(m, f"Model {m} not found in registry") for m in missing] + [
                (m, "Executor returned no result for this cell (unexpected error; see log)")
                for m in sorted(set(param_dict) - seen)
            ]:
                rec = {
                    "scenario_id": sid, "model_id": mid, "task_id": task_id, "manifest_name": BASELINE_MANIFEST_NAME,
                    "status": "failed", "error_message": reason,
                    "started_at": started, "completed_at": completed, "runtime_seconds": None,
                }
                model_records.append(rec)
                _write_json(state_dir / f"{run_id}_model_baseline_{task_id}.json", rec)
                task_id += 1

    try:
        asyncio.run(_run_all_scenarios())
    finally:
        executor.shutdown()
    stage_seconds["model_execution_seconds"] = round(time.monotonic() - t0, 4)

    # ---- Module 4: consistency + templated synthesis --------------------
    t0 = time.monotonic()
    all_flags: list[dict[str, Any]] = []
    all_synthesis: list[dict[str, Any]] = []
    per_scenario: list[dict[str, Any]] = []
    section_events: list[dict[str, Any]] = []
    for n in narratives:
        sid = n["scenario_id"]
        results = results_by_scenario.get(sid) or []
        if not results:
            continue
        narrative_state = ScenarioNarrativeState(
            scenario_id=Scenario(sid), label=n["label"], narrative=n["narrative"],
            quantitative_assumptions=n["quantitative_assumptions"], consistency_notes=n["consistency_notes"],
        )
        flags, synthesis, metrics = templated_synthesis(
            Scenario(sid), narrative_state, results, config.consistency,
            params_by_model=params_by_scenario.get(sid), max_outcomes_per_model=max_outcomes_per_model,
        )
        all_flags.extend(f.model_dump(mode="json") for f in flags)
        for key, m in metrics.items():
            section_events.append({"scenario_id": sid, "time_horizon": key.time_horizon.value,
                                   "outcome_scope": key.outcome_scope.value, **m})
        n_out = 0
        for section in synthesis.sections:
            for o in section.outcomes:
                n_out += 1
                all_synthesis.append({
                    "scenario_id": sid, "time_horizon": section.time_horizon.value,
                    "outcome_scope": section.outcome_scope.value, "outcome_variable": o.variable,
                    "value": o.value, "unit": o.unit, "source_model_id": o.source_model_id,
                    "source_model_id_raw": o.source_model_id_raw, "fidelity_status": o.fidelity_status,
                    "narrative_summary": o.narrative, "reliability_note": o.reliability_note,
                    "distribution_note": o.distribution_note, "uncertainty_note": o.uncertainty_note,
                })
        statuses = [r.status.value for r in results]
        mode_by_model = {r.model_id: r.implementation_mode for r in results}
        per_scenario.append({
            "scenario_id": sid, "label": n["label"],
            "markdown": render_scenario_markdown(synthesis, mode_by_model),
            "outcome_count": n_out, "consistency_flag_count": len(flags),
            "completed_models": statuses.count("completed"), "skipped_models": statuses.count("skipped"),
            "failed_models": statuses.count("failed"),
        })

    # Fidelity audit of the templated synthesis (should be 100 pct exact).
    outputs_by_scenario: dict[str, dict[str, dict[str, Any] | None]] = {}
    for rec in model_records:
        outputs_by_scenario.setdefault(rec["scenario_id"], {})[rec["model_id"]] = (
            rec.get("outputs") if rec.get("status") == "completed" else None
        )
    report = audit_run(run_id, all_synthesis, outputs_by_scenario, list(registry.all_model_ids()))
    fidelity_summary = {
        "validator": {"enabled": True, "on_mismatch": "n/a (templated synthesis)", "reprompt_once": False},
        "method": SYNTHESIS_METHOD,
        "sections_audited": sum(1 for ev in section_events if ev.get("status") == "ok"),
        "outcomes_audited": report.summary.get("outcomes"),
        "outcomes_mismatched": (
            report.summary["numeric_outcomes"] - report.summary["strict_matched"]
            if isinstance(report.summary.get("numeric_outcomes"), int)
            and isinstance(report.summary.get("strict_matched"), int) else None
        ),
        "outcomes_dropped": 0,
        "sources_canonicalized": report.summary.get("source_ids_canonicalized"),
        "audit_summary": report.summary,
    }

    completed = sum(1 for r in model_records if r["status"] == "completed")
    skipped = sum(1 for r in model_records if r["status"] == "skipped")
    failed = sum(1 for r in model_records if r["status"] == "failed")
    synthesis_state: dict[str, Any] = {
        "run_id": run_id,
        "synthesis_method": SYNTHESIS_METHOD,
        "model_results_count": len(model_records),
        "completed": completed, "skipped": skipped, "failed": failed,
        "bash_failures_count": 0, "bash_failures_by_stage": {}, "bash_failures": [],
        "consistency_flags": all_flags,
        "synthesis_results": all_synthesis,
        "synthesis_validated": True,
        "validation_mode": "analyst_authored_baseline",
        "context_budget": {"context_window": None, "prompt_budget_tokens": 0, "completion_budget_tokens": 0,
                           "tiktoken_available": False, "note": "no LLM call in the templated synthesis"},
        "context_budget_events": section_events,
        "context_budget_summary": {
            "section_calls": len(section_events),
            "sections_failed": sum(1 for ev in section_events if ev.get("status") == "failed"),
            "sections_truncated": 0, "truncation_attempts_total": 0,
        },
        "fidelity_summary": fidelity_summary,
        "upstream_forwarding": apply_forwarding,
    }
    stage_seconds["synthesis_seconds"] = round(time.monotonic() - t0, 4)
    synthesis_state["run_health"] = assess_run(
        run_id, synthesis_state=synthesis_state, model_results=model_records, param_results=param_records,
        bash_failures=[], scenarios_state=scenarios_state, stage_seconds=stage_seconds,
    )
    _write_json(state_dir / f"{run_id}_synthesis.json", synthesis_state)

    # Report artefacts in the same layout as run_synthesis.py. The stage
    # helpers resolve data/ under SLURM_SUBMIT_DIR, so point it at the
    # output root for the duration of the write and restore it after.
    previous_root = os.environ.get("SLURM_SUBMIT_DIR")
    os.environ["SLURM_SUBMIT_DIR"] = str(output_root)
    export_rc: int | None = None
    try:
        from slurm.scripts.run_synthesis import write_synthesis_artifacts  # noqa: WPS433

        write_synthesis_artifacts(run_id, synthesis_state, per_scenario)
        (report_dir / "fidelity.json").write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")

        if export:
            t0 = time.monotonic()
            from slurm.scripts.export_results import main as export_main  # noqa: WPS433

            export_rc = export_main(["--run-id", run_id, "--no-llm", "--no-exec-summary"])
            stage_seconds["export_seconds"] = round(time.monotonic() - t0, 4)
    finally:
        if previous_root is None:
            os.environ.pop("SLURM_SUBMIT_DIR", None)
        else:
            os.environ["SLURM_SUBMIT_DIR"] = previous_root

    summary = {
        "run_id": run_id,
        "baseline": scenarios_state["baseline"],
        "synthesis_method": SYNTHESIS_METHOD,
        "upstream_forwarding": apply_forwarding,
        "llm_calls": 0,
        "scenarios": [n["scenario_id"] for n in narratives],
        "cells": {"parameter_sets": len(param_records), "model_records": len(model_records),
                  "completed": completed, "skipped": skipped, "failed": failed},
        "outcomes": len(all_synthesis),
        "consistency_flags": len(all_flags),
        "clean_synthesis": synthesis_state["run_health"].get("clean_synthesis"),
        "fidelity_strict_match_rate": report.summary.get("strict_match_rate"),
        "stage_seconds": stage_seconds,
        "export_return_code": export_rc,
        "state_dir": str(state_dir),
        "report_dir": str(report_dir),
    }
    _write_json(report_dir / "baseline_run.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--baseline", default="configs/baselines/hormuz_2026_analyst.yaml")
    p.add_argument("--run-id", default=None, help="Default: baseline_<UTC timestamp>.")
    p.add_argument("--output-root", default=None,
                   help="Directory holding data/pipeline_state and data/reports (default: repository root).")
    p.add_argument("--scenarios", default=None, help="Comma-separated scenario ids (default: all in the file).")
    p.add_argument("--models", default=None, help="Comma-separated model ids (default: all in the file).")
    p.add_argument("--no-forwarding", action="store_true", help="Disable the upstream forwarding barrier.")
    p.add_argument("--max-parallel", type=int, default=4)
    p.add_argument("--max-outcomes-per-model", type=int, default=10)
    p.add_argument("--no-export", action="store_true", help="Skip the Stage 5 CSV export.")
    args = p.parse_args(argv)

    run_id = args.run_id or datetime.now(timezone.utc).strftime("baseline_%Y%m%d_%H%M%S")
    output_root = Path(args.output_root) if args.output_root else Path(__file__).resolve().parents[2]
    summary = run_baseline(
        Path(args.baseline), run_id, output_root=output_root,
        scenario_ids=[s.strip() for s in args.scenarios.split(",")] if args.scenarios else None,
        model_ids=[m.strip() for m in args.models.split(",")] if args.models else None,
        apply_forwarding=not args.no_forwarding, max_parallel=args.max_parallel,
        max_outcomes_per_model=args.max_outcomes_per_model, export=not args.no_export,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "baseline"}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
