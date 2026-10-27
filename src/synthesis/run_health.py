"""Run-level health assessment: the operational definition of "clean synthesis".

Reviewers asked what "clean synthesis" and "runs" mean in the backend
comparison, what the denominator is, whether wall-clock time includes
human review, and how the three analyst checkpoints behaved in batch
mode. :func:`assess_run` answers all four from the run's saved state so
the same definition serves the main run, the weekly reruns, and the
backend comparison.

The definition (also exported as :data:`CLEAN_SYNTHESIS_DEFINITION`):

    A run has a *clean synthesis* when (1) the Module 4 synthesis state
    was written, (2) every (scenario, section) LLM call completed
    without an unrecoverable error (``context_budget_summary.
    sections_failed == 0``), (3) no bash-layer failure was recorded for
    the synthesis stage, and (4) every scenario in the run has at least
    one completed model and at least one synthesized outcome.

Counts use explicit denominators: ``grid`` (scenarios x model specs),
``parameter_sets`` (cells that reached Module 2), ``model_records`` (cells
that reached Module 3). Wall-clock is split into model execution (sum of
per-cell runtimes and the span of the model stage), LLM stages where
recorded, and analyst review, which is reported as zero with
``review_mode = auto_approved`` whenever the checkpoints were
auto-approved rather than silently omitted.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

CLEAN_SYNTHESIS_DEFINITION = (
    "A run has a clean synthesis when (1) the Module 4 synthesis state was written, "
    "(2) every (scenario, section) LLM call completed without an unrecoverable error "
    "(context_budget_summary.sections_failed == 0), (3) no bash-layer failure was recorded "
    "for the synthesis stage, and (4) every scenario in the run has at least one completed "
    "model and at least one synthesized outcome."
)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _float(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _status(rec: dict[str, Any]) -> str:
    return str(rec.get("status") or "").lower()


def stage_span_seconds(records: list[dict[str, Any]]) -> float | None:
    """Elapsed seconds between the earliest start and latest completion of the records."""
    starts = [t for t in (_parse_ts(r.get("started_at")) for r in records) if t]
    ends = [t for t in (_parse_ts(r.get("completed_at")) for r in records) if t]
    if not starts or not ends:
        return None
    return round((max(ends) - min(starts)).total_seconds(), 3)


def assess_run(
    run_id: str,
    *,
    synthesis_state: dict[str, Any] | None,
    model_results: list[dict[str, Any]],
    param_results: list[dict[str, Any]] | None = None,
    bash_failures: list[dict[str, Any]] | None = None,
    scenarios_state: dict[str, Any] | None = None,
    n_model_specs: int | None = None,
    stage_seconds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Assess one run. Every input is the JSON-decoded content of the saved state.

    Args:
        synthesis_state: ``<run_id>_synthesis.json`` (or ``synthesis.json``), or None.
        model_results: ``<run_id>_model_*.json`` records (or model_status rows).
        param_results: ``<run_id>_params_*.json`` records.
        bash_failures: bash-layer failure records.
        scenarios_state: ``<run_id>_scenarios.json`` (for the scenario list,
            checkpoint flags and the LLM backend).
        n_model_specs: number of model specs in the grid (defaults to the
            registry's ALL_MODEL_SPECS size when importable).
        stage_seconds: optional externally measured stage durations
            (e.g. from job logs), merged into ``wall_clock.stages``.
    """
    param_results = param_results or []
    bash_failures = bash_failures or []
    synthesis_state = synthesis_state or {}
    scenarios_state = scenarios_state or {}

    if n_model_specs is None:
        try:
            from src.parameters.model_specs import ALL_MODEL_SPECS  # noqa: WPS433

            n_model_specs = len(ALL_MODEL_SPECS)
        except Exception:  # noqa: BLE001
            n_model_specs = None

    narratives = scenarios_state.get("scenario_narratives") or []
    scenario_ids = [str(n.get("scenario_id")) for n in narratives if isinstance(n, dict)]
    if not scenario_ids:
        scenario_ids = sorted({str(r.get("scenario_id")) for r in model_results if r.get("scenario_id")})

    # ---- cells -------------------------------------------------------
    status_counts = Counter(_status(r) for r in model_results)
    completed_by_scenario: Counter = Counter()
    for r in model_results:
        if _status(r) == "completed":
            completed_by_scenario[str(r.get("scenario_id"))] += 1
    synthesis_results = synthesis_state.get("synthesis_results") or []
    outcomes_by_scenario = Counter(str(o.get("scenario_id")) for o in synthesis_results if isinstance(o, dict))

    # ---- clean synthesis criteria -----------------------------------
    cbs = synthesis_state.get("context_budget_summary") or {}
    sections_failed = cbs.get("sections_failed")
    sections_total = cbs.get("section_calls")
    synthesis_bash_failures = [f for f in bash_failures if "synth" in str(f.get("stage", "")).lower()]
    scenarios_covered = [s for s in scenario_ids if completed_by_scenario.get(s, 0) > 0 and outcomes_by_scenario.get(s, 0) > 0]
    criteria = {
        "synthesis_state_present": bool(synthesis_state),
        "sections_failed": sections_failed,
        "sections_total": sections_total,
        "bash_failures_in_synthesis_stage": len(synthesis_bash_failures),
        "scenarios_total": len(scenario_ids),
        "scenarios_with_completed_model_and_outcome": len(scenarios_covered),
        "synthesis_results_count": len(synthesis_results),
    }
    if not synthesis_state or not synthesis_results:
        clean: bool | None = False
    elif sections_failed is None:
        clean = None  # section telemetry missing: undetermined, never claimed
    else:
        clean = (
            int(sections_failed) == 0
            and not synthesis_bash_failures
            and len(scenarios_covered) == len(scenario_ids) > 0
        )

    # ---- wall clock --------------------------------------------------
    completed_or_failed = [r for r in model_results if _status(r) in ("completed", "failed")]
    model_runtime_sum = round(sum(_float(r.get("runtime_seconds")) or 0.0 for r in completed_or_failed), 3)
    tiers: dict[str, list[dict[str, Any]]] = {}
    for r in model_results:
        tiers.setdefault(str(r.get("manifest_name") or "models"), []).append(r)
    tier_spans = {t: stage_span_seconds(recs) for t, recs in tiers.items()}
    param_runtime = [(_float(p.get("runtime_seconds")) or 0.0) for p in param_results if p.get("runtime_seconds") is not None]
    stages: dict[str, float | None] = {
        "parameter_extraction_llm_seconds": round(sum(param_runtime), 3) if param_runtime else None,
        "model_execution_runtime_sum_seconds": model_runtime_sum,
        "model_execution_span_seconds": stage_span_seconds(model_results),
    }
    for t, s in tier_spans.items():
        stages[f"model_tier_span_seconds[{t}]"] = s
    if stage_seconds:
        for k, v in stage_seconds.items():
            stages[k] = v
    auto_approve = bool(scenarios_state.get("scenarios_validated")) if scenarios_state else None
    n_completed = status_counts.get("completed", 0)
    wall_clock = {
        "stages": stages,
        "analyst_review_seconds": 0.0 if auto_approve else None,
        "review_mode": "auto_approved" if auto_approve else ("interactive_or_unknown" if auto_approve is None else "interactive"),
        "seconds_per_completed_model_run": round(model_runtime_sum / n_completed, 4) if n_completed else None,
        "note": (
            "Model-execution time is the sum of per-cell adapter runtimes; spans are wall-clock between "
            "the first start and last completion of the stage. Human review time is zero when the "
            "checkpoints were auto-approved (batch mode) and is not included in any figure."
        ),
    }

    # ---- checkpoints -------------------------------------------------
    param_validation = Counter(str(p.get("validation_status") or "unknown") for p in param_results)
    checkpoints = {
        "auto_approve": auto_approve,
        "scenarios_validated": scenarios_state.get("scenarios_validated") if scenarios_state else None,
        "parameters_validation_status": dict(param_validation),
        "synthesis_validated": synthesis_state.get("synthesis_validated") if synthesis_state else None,
        "note": (
            "In SLURM batch mode HORMUZ_AUTO_APPROVE=1 marks all three checkpoints approved without "
            "analyst input; the manuscript's 'never run unattended' claim applies to interactive use."
        ),
    }

    config = scenarios_state.get("config") or {}
    llm = config.get("llm") or {}
    backend = {"provider": llm.get("provider"), "model": llm.get("model"), "base_url": llm.get("base_url")}

    # ---- failure reasons --------------------------------------------
    section_errors = Counter(
        str(ev.get("error") or "unknown") for ev in (synthesis_state.get("context_budget_events") or []) if ev.get("status") == "failed"
    )
    bash_stage_failures = Counter(str(f.get("stage") or "unknown") for f in bash_failures)
    model_error_classes = Counter()
    try:
        from src.interface.coverage import classify_execution  # noqa: WPS433

        for r in model_results:
            if _status(r) in ("failed", "skipped"):
                model_error_classes[classify_execution(_status(r), r.get("error_message"))] += 1
    except Exception:  # noqa: BLE001
        pass

    return {
        "run_id": run_id,
        "backend": backend,
        "clean_synthesis": clean,
        "clean_synthesis_definition": CLEAN_SYNTHESIS_DEFINITION,
        "criteria": criteria,
        "cells": {
            "parameter_sets": len(param_results),
            "parameter_sets_failed": sum(1 for p in param_results if str(p.get("status") or "").lower() == "failed"),
            "model_records": len(model_results),
            "completed": n_completed,
            "failed": status_counts.get("failed", 0),
            "skipped": status_counts.get("skipped", 0),
        },
        "denominators": {
            "grid": (len(scenario_ids) * n_model_specs) if (scenario_ids and n_model_specs) else None,
            "scenarios": len(scenario_ids),
            "model_specs": n_model_specs,
            "parameter_sets": len(param_results) or None,
            "model_records": len(model_results) or None,
        },
        "wall_clock": wall_clock,
        "checkpoints": checkpoints,
        "failure_reasons": {
            "synthesis_section_errors": dict(section_errors),
            "bash_failures_by_stage": dict(bash_stage_failures),
            "model_skip_classes": dict(model_error_classes),
        },
    }


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def load_run_inputs(run_id: str, state_dir: Path, report_dir: Path | None = None) -> dict[str, Any]:
    """Collect the inputs of :func:`assess_run` for one run from disk.

    State files are preferred; a report directory (``synthesis.json``,
    ``csv/model_status.csv``) fills in whatever the state dir lacks.
    """
    model_results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        rec = _load_json(path)
        if isinstance(rec, dict):
            key = (str(rec.get("scenario_id")), str(rec.get("model_id")))
            if key in seen and not rec.get("recovered"):
                continue
            seen.add(key)
            model_results.append(rec)
    param_results = [r for r in (_load_json(p) for p in sorted(state_dir.glob(f"{run_id}_params_*.json"))) if isinstance(r, dict)]
    bash_failures = [r for r in (_load_json(p) for p in sorted(state_dir.glob(f"{run_id}_*_bash_failure_*.json"))) if isinstance(r, dict)]
    synthesis_state = _load_json(state_dir / f"{run_id}_synthesis.json")
    scenarios_state = _load_json(state_dir / f"{run_id}_scenarios.json")
    if report_dir is not None:
        if not isinstance(synthesis_state, dict):
            synthesis_state = _load_json(report_dir / "synthesis.json")
        if not model_results:
            import csv  # noqa: WPS433

            p = report_dir / "csv" / "model_status.csv"
            if p.exists():
                with open(p, newline="", encoding="utf-8") as f:
                    model_results = list(csv.DictReader(f))
        if not bash_failures and isinstance(synthesis_state, dict):
            bash_failures = [b for b in synthesis_state.get("bash_failures") or [] if isinstance(b, dict)]
    return {
        "synthesis_state": synthesis_state if isinstance(synthesis_state, dict) else None,
        "model_results": model_results,
        "param_results": param_results,
        "bash_failures": bash_failures,
        "scenarios_state": scenarios_state if isinstance(scenarios_state, dict) else None,
    }


def render_checkpoint_markdown(assessments: list[dict[str, Any]]) -> str:
    """Markdown record of how the three analyst checkpoints operated per run."""
    lines = [
        "# Analyst checkpoints in batch runs",
        "",
        "Algorithm 1 has three mandatory analyst checkpoints (after scenario generation, after parameter "
        "extraction, after synthesis). The SLURM drivers export `HORMUZ_AUTO_APPROVE=1` because a batch job "
        "cannot prompt, so each checkpoint is recorded as approved without analyst input and the review happens "
        "post hoc on the saved state. The table is generated from the run state files by "
        "`scripts/revision/checkpoint_report.py`.",
        "",
        "| run | backend | auto-approve | scenarios validated | parameter sets by validation status | synthesis validated | analyst review seconds |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in assessments:
        cp = a["checkpoints"]
        pv = ", ".join(f"{k}: {v}" for k, v in sorted(cp["parameters_validation_status"].items())) or "-"
        lines.append(
            f"| `{a['run_id']}` | {a['backend'].get('model') or '?'} | {cp['auto_approve']} | {cp['scenarios_validated']} | "
            f"{pv} | {cp['synthesis_validated']} | {a['wall_clock']['analyst_review_seconds']} |"
        )
    lines += [
        "",
        "`?` or `None` means the corresponding state file (`<run_id>_scenarios.json`, `<run_id>_params_*.json`) "
        "was not available in the state directory given to the script, so the field could not be read; the "
        "synthesis column comes from the report copy of `synthesis.json` in that case.",
        "",
    ]
    return "\n".join(lines)
