#!/usr/bin/env python3
"""Trace one synthesized number back to the scenario narrative (Reviewer 1, point 3).

Rebuilds a ``PipelineState`` from a run's saved files and emits the
provenance chain for one (scenario, model, variable):

    narrative sentence -> extracted parameter (with analyst validation
    status) -> adapter input (with the upstream-forwarding override
    record: LLM value, upstream value, source model/field/transform,
    deviation and flag status) -> model output -> synthesis sentence.

Evidence sources:

* ``--state-dir`` (default ``data/pipeline_state``): ``<run_id>_scenarios.json``,
  ``<run_id>_params_*.json``, ``<run_id>_model_*.json``, ``<run_id>_synthesis.json``.
  This is the full chain.
* ``--from-report-dir data/reports/<run_id>``: ``synthesis.json`` + Stage 5 CSVs.
  Narrative and parameter links are unavailable; override records are
  reconstructed from the flagged consistency rows only.

Example (the manuscript's worked example)::

    python slurm/scripts/trace_provenance.py --run-id 20260504_222710 \
        --scenario swift_escalated --model fed_oil --variable oil_price_change_pct \
        --out-dir docs/revision

Writes ``provenance_<run>_<scenario>_<model>_<variable>.{json,md}``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import get_run_id, logger, state_dir  # noqa: E402
from src.common.types import ConfidenceLevel, ModelExecutionStatus, Scenario, ValidationStatus  # noqa: E402
from src.interface.provenance import ProvenanceTracker, render_chain_markdown  # noqa: E402
from src.pipeline.state import (  # noqa: E402
    ModelExecutionResult,
    ModelParameterSet,
    ParameterValue,
    PipelineState,
    ScenarioNarrativeState,
    SynthesisResult,
)


def _load_json(path: Path) -> Any | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _enum(cls, value, default):
    try:
        return cls(value)
    except (ValueError, TypeError):
        return default


def _synthesis_results(synthesis: dict | None) -> list[SynthesisResult]:
    out = []
    for r in (synthesis or {}).get("synthesis_results") or []:
        sid = _enum(Scenario, r.get("scenario_id"), None)
        if sid is None:
            continue
        out.append(SynthesisResult(
            scenario_id=sid,
            time_horizon=str(r.get("time_horizon") or ""),
            outcome_scope=str(r.get("outcome_scope") or ""),
            outcome_variable=str(r.get("outcome_variable") or ""),
            value=r.get("value"),
            unit=r.get("unit"),
            source_model_id=str(r.get("source_model_id") or ""),
            narrative_summary=str(r.get("narrative_summary") or ""),
        ))
    return out


def build_state_from_state_dir(run_id: str, sdir: Path) -> PipelineState:
    """Rebuild the PipelineState the SLURM stages persisted piecewise."""
    state = PipelineState(run_id=run_id)
    scenarios = _load_json(sdir / f"{run_id}_scenarios.json") or {}
    state.crisis_description = str(scenarios.get("crisis_description") or "")
    for n in scenarios.get("scenario_narratives") or []:
        sid = _enum(Scenario, n.get("scenario_id"), None)
        if sid is None:
            continue
        state.scenario_narratives.append(ScenarioNarrativeState(
            scenario_id=sid,
            label=str(n.get("label") or ""),
            narrative=str(n.get("narrative") or ""),
            quantitative_assumptions=n.get("quantitative_assumptions") or {},
            consistency_notes=str(n.get("consistency_notes") or ""),
            validation_status=_enum(ValidationStatus, n.get("validation_status"), ValidationStatus.PENDING),
        ))
    for path in sorted(sdir.glob(f"{run_id}_params_*.json")):
        rec = _load_json(path)
        if not isinstance(rec, dict):
            continue
        sid = _enum(Scenario, rec.get("scenario_id"), None)
        if sid is None:
            continue
        params = [
            ParameterValue(
                name=str(p.get("name")),
                value=p.get("value"),
                unit=p.get("unit"),
                confidence=_enum(ConfidenceLevel, p.get("confidence"), ConfidenceLevel.MEDIUM),
                extraction_note=p.get("extraction_note"),
            )
            for p in rec.get("parameters") or []
            if isinstance(p, dict) and p.get("name")
        ]
        state.parameter_sets.append(ModelParameterSet(
            scenario_id=sid,
            model_id=str(rec.get("model_id")),
            parameters=params,
            validation_status=_enum(ValidationStatus, rec.get("validation_status"), ValidationStatus.PENDING),
        ))
    seen: set[tuple[str, str]] = set()
    for path in sorted(sdir.glob(f"{run_id}_model_*.json")):
        rec = _load_json(path)
        if not isinstance(rec, dict):
            continue
        sid = _enum(Scenario, rec.get("scenario_id"), None)
        if sid is None:
            continue
        key = (sid.value, str(rec.get("model_id")))
        if key in seen and not rec.get("recovered"):
            continue
        seen.add(key)
        state.execution_results = [
            r for r in state.execution_results if (r.scenario_id.value, r.model_id) != key
        ]
        state.execution_results.append(ModelExecutionResult(
            scenario_id=sid,
            model_id=str(rec.get("model_id")),
            status=_enum(ModelExecutionStatus, rec.get("status"), ModelExecutionStatus.FAILED),
            outputs=rec.get("outputs") or {},
            runtime_seconds=rec.get("runtime_seconds"),
            error_message=rec.get("error_message"),
            metadata=rec.get("metadata") or {},
            implementation_mode=rec.get("implementation_mode"),
        ))
    state.synthesis_results = _synthesis_results(_load_json(sdir / f"{run_id}_synthesis.json"))
    return state


def build_state_from_report_dir(run_id: str, report_dir: Path) -> PipelineState:
    """Partial state from Stage 5 CSVs + synthesis.json (no narrative / parameters)."""
    from src.synthesis.fidelity import model_outputs_from_report_csv  # noqa: WPS433

    state = PipelineState(run_id=run_id)
    synthesis = _load_json(report_dir / "synthesis.json") or {}
    outputs = model_outputs_from_report_csv(report_dir / "csv")
    status_rows: list[dict[str, str]] = []
    p = report_dir / "csv" / "model_status.csv"
    if p.exists():
        with open(p, newline="", encoding="utf-8") as f:
            status_rows = list(csv.DictReader(f))
    # Override records are only visible through flagged rows.
    overrides: dict[tuple[str, str], list[dict]] = {}
    for fl in synthesis.get("consistency_flags") or []:
        msg = str(fl.get("message") or "")
        if "upstream-computed" not in msg:
            continue
        key = (str(fl.get("scenario_id")), str(fl.get("model_a_id")))
        var = str(fl.get("variable") or "")
        name, _, tk = var.partition("[")
        overrides.setdefault(key, []).append({
            "name": name,
            "target_key": tk.rstrip("]") or None,
            "llm_value": fl.get("value_a"),
            "computed_value": fl.get("value_b"),
            "source_model_id": fl.get("model_b_id"),
            "source_field": None,
            "transform": None,
            "deviation_pct": fl.get("deviation_pct"),
        })
    for r in status_rows:
        sid = _enum(Scenario, r.get("scenario_id"), None)
        if sid is None:
            continue
        mid = str(r.get("model_id"))
        outs = outputs.get(sid.value, {}).get(mid) or {}
        outs = dict(outs)
        if (sid.value, mid) in overrides:
            outs["_upstream_overrides"] = overrides[(sid.value, mid)]
        state.execution_results.append(ModelExecutionResult(
            scenario_id=sid,
            model_id=mid,
            status=_enum(ModelExecutionStatus, r.get("status"), ModelExecutionStatus.FAILED),
            outputs=outs,
            runtime_seconds=float(r["runtime_seconds"]) if r.get("runtime_seconds") else None,
            error_message=r.get("error_message") or None,
            implementation_mode=r.get("implementation_mode") or None,
        ))
    state.synthesis_results = _synthesis_results(synthesis)
    return state


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", default=None)
    p.add_argument("--scenario", required=True, help="Scenario id, e.g. swift_escalated")
    p.add_argument("--model", required=True)
    p.add_argument("--variable", required=True)
    p.add_argument("--state-dir", default=None)
    p.add_argument("--from-report-dir", default=None)
    p.add_argument("--out-dir", default="docs/revision")
    p.add_argument("--flag-threshold-pct", type=float, default=50.0)
    args = p.parse_args(argv)

    run_id = args.run_id or get_run_id()
    if args.from_report_dir:
        state = build_state_from_report_dir(run_id, Path(args.from_report_dir))
    else:
        state = build_state_from_state_dir(run_id, Path(args.state_dir) if args.state_dir else state_dir())
    scenario = Scenario(args.scenario)
    record = ProvenanceTracker(state, flag_threshold_pct=args.flag_threshold_pct).trace(
        scenario, args.model, args.variable
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"provenance_{run_id}_{scenario.value}_{args.model}_{args.variable}"
    base.with_suffix(".json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    base.with_suffix(".md").write_text(render_chain_markdown(record), encoding="utf-8")
    logger.info(
        f"provenance chain for {scenario.value}/{args.model}/{args.variable}: links "
        f"{record.chain_links} ({'complete' if record.chain_complete else 'incomplete'}); wrote {base}.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
