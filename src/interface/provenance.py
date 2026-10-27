"""Provenance tracking (Module 5).

Traces any synthesized result back through the full chain:
synthesis -> model output -> model input (incl. upstream-forwarding
overrides) -> extracted parameter -> scenario narrative sentence.

The :class:`ProvenanceRecord` is the machine-readable artefact the
manuscript's worked example (Reviewer 1, point 3) is built from;
:func:`render_chain_markdown` renders it as the five-row table
(narrative sentence, extracted parameter, adapter input, model output,
synthesis sentence) plus the override record with the LLM-extracted
value, the upstream value, the deviation and its flag status.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import Scenario
from src.pipeline.state import PipelineState

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")
_GENERIC_WORDS = {
    "pct", "percent", "months", "month", "weeks", "week", "days", "usd", "per", "of", "the",
    "change", "level", "rate", "baseline", "index", "flag", "status", "spec", "path", "multiplier",
    "increase", "reduction", "loss", "shock", "disruption", "duration",
}


class OverrideLink(BaseModel):
    """One upstream-forwarding override that replaced an LLM-extracted input."""

    name: str
    target_key: str | None = None
    llm_value: Any = None
    computed_value: Any = None
    source_model_id: str = ""
    source_field: str | None = None
    transform: str | None = None
    deviation_pct: float | None = None
    flagged: bool = False
    threshold_pct: float | None = None
    source_ran_in_run: bool | None = None


class ProvenanceRecord(BaseModel):
    """Full provenance chain for a single synthesized result."""

    run_id: str = ""
    scenario_id: Scenario
    outcome_variable: str
    source_model_id: str

    # From synthesis
    synthesized_value: Any = None
    narrative_summary: str = ""
    synthesis_outcomes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Every synthesis result citing this (model, variable), as stored in the run state.",
    )

    # From model execution
    model_status: str | None = None
    implementation_mode: str | None = None
    model_outputs: dict[str, Any] = Field(default_factory=dict)
    model_runtime_seconds: float | None = None
    upstream_overrides: list[OverrideLink] = Field(default_factory=list)

    # From parameter extraction
    model_inputs: dict[str, Any] = Field(default_factory=dict)
    parameter_confidence: dict[str, str] = Field(default_factory=dict)
    parameter_units: dict[str, str | None] = Field(default_factory=dict)
    parameter_notes: dict[str, str | None] = Field(default_factory=dict)
    parameter_validation_status: str | None = None

    # From scenario narrative
    scenario_label: str = ""
    scenario_narrative_excerpt: str = ""
    relevant_assumptions: dict[str, Any] = Field(default_factory=dict)
    narrative_sentences: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Parameter name -> narrative sentences that state its value or name it.",
    )

    # Which links of the chain were found in the run state.
    chain_links: dict[str, bool] = Field(default_factory=dict)

    @property
    def chain_complete(self) -> bool:
        return all(self.chain_links.get(k, False) for k in ("narrative", "parameters", "model_run", "synthesis"))


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _number_forms(value: Any) -> list[str]:
    """Textual forms a numeric parameter value may take in prose."""
    forms: list[str] = []
    try:
        f = float(value)
    except (TypeError, ValueError):
        return forms
    if f.is_integer():
        forms.append(str(int(f)))
        forms.append(f"{int(f):,}")
    forms.append(f"{f:g}")
    forms.append(f"{f:.1f}".rstrip("0").rstrip("."))
    forms.append(f"{f:.2f}".rstrip("0").rstrip("."))
    return list(dict.fromkeys(x for x in forms if x))


def find_narrative_sentences(narrative: str, name: str, value: Any, limit: int = 3) -> list[str]:
    """Sentences that state ``value`` (as a number) or mention the parameter's keywords."""
    sentences = split_sentences(narrative)
    if not sentences:
        return []
    hits: list[str] = []
    forms = _number_forms(value)
    try:
        if float(value) == 0.0:
            forms = []  # a bare zero matches too much prose incidentally
    except (TypeError, ValueError):
        pass
    for s in sentences:
        if forms and any(re.search(rf"(?<![\d.]){re.escape(f)}(?![\d])", s) for f in forms):
            hits.append(s)
    if not hits:
        keywords = [w for w in re.split(r"[_\W]+", str(name).lower()) if len(w) > 2 and w not in _GENERIC_WORDS]
        if keywords:
            needed = min(2, len(keywords))
            for s in sentences:
                low = s.lower()
                matched = [k for k in keywords if k in low]
                # Two generic keywords, or one specific (long) term, is enough.
                if len(matched) >= needed or any(len(k) >= 8 for k in matched):
                    hits.append(s)
    return hits[:limit]


class ProvenanceTracker:
    """Builds provenance records by tracing through the pipeline state."""

    def __init__(self, state: PipelineState, flag_threshold_pct: float = 50.0) -> None:
        self.state = state
        self.flag_threshold_pct = flag_threshold_pct

    def trace(
        self,
        scenario_id: Scenario,
        model_id: str,
        outcome_variable: str,
    ) -> ProvenanceRecord:
        """Trace a single result back through the full pipeline.

        Args:
            scenario_id: Which scenario.
            model_id: Which model produced the result.
            outcome_variable: Which output variable to trace.

        Returns:
            A ProvenanceRecord with all available chain links populated.
        """
        record = ProvenanceRecord(
            run_id=self.state.run_id,
            scenario_id=scenario_id,
            outcome_variable=outcome_variable,
            source_model_id=model_id,
        )
        links = {"narrative": False, "parameters": False, "model_run": False, "synthesis": False}

        # Trace to model execution
        exec_result = self.state.get_execution_result(scenario_id, model_id)
        completed_models = {
            r.model_id for r in self.state.get_results_for_scenario(scenario_id)
            if getattr(r.status, "value", r.status) == "completed"
        }
        if exec_result:
            record.model_outputs = exec_result.outputs
            record.model_runtime_seconds = exec_result.runtime_seconds
            record.model_status = getattr(exec_result.status, "value", str(exec_result.status))
            record.implementation_mode = exec_result.implementation_mode
            if outcome_variable in exec_result.outputs:
                record.synthesized_value = exec_result.outputs[outcome_variable]
                links["model_run"] = record.model_status == "completed"
            for rec in exec_result.outputs.get("_upstream_overrides") or []:
                if not isinstance(rec, dict):
                    continue
                dev = rec.get("deviation_pct")
                try:
                    dev_f = float(dev) if dev is not None else None
                except (TypeError, ValueError):
                    dev_f = None
                src = str(rec.get("source_model_id") or "")
                record.upstream_overrides.append(OverrideLink(
                    name=str(rec.get("name") or ""),
                    target_key=rec.get("target_key"),
                    llm_value=rec.get("llm_value"),
                    computed_value=rec.get("computed_value"),
                    source_model_id=src,
                    source_field=rec.get("source_field"),
                    transform=rec.get("transform"),
                    deviation_pct=dev_f,
                    flagged=bool(dev_f is not None and dev_f > self.flag_threshold_pct),
                    threshold_pct=self.flag_threshold_pct,
                    source_ran_in_run=(src in completed_models) if src else None,
                ))

        # Trace to parameter extraction
        params = self.state.get_parameters(scenario_id, model_id)
        if params:
            record.model_inputs = {p.name: p.value for p in params.parameters}
            record.parameter_confidence = {
                p.name: getattr(p.confidence, "value", str(p.confidence)) for p in params.parameters
            }
            record.parameter_units = {p.name: p.unit for p in params.parameters}
            record.parameter_notes = {p.name: p.extraction_note for p in params.parameters}
            record.parameter_validation_status = getattr(
                params.validation_status, "value", str(params.validation_status)
            )
            links["parameters"] = bool(params.parameters)

        # Trace to scenario narrative
        narrative = self.state.get_narrative(scenario_id)
        if narrative:
            record.scenario_label = narrative.label
            record.scenario_narrative_excerpt = narrative.narrative[:500]
            record.relevant_assumptions = narrative.quantitative_assumptions
            links["narrative"] = bool(narrative.narrative)
            for name, value in record.model_inputs.items():
                # Prefer the LLM-extracted value (what the narrative stated)
                # over an upstream-forwarded replacement.
                llm_value = value
                for o in record.upstream_overrides:
                    if o.name == name and o.target_key is None and o.llm_value is not None:
                        llm_value = o.llm_value
                sentences = find_narrative_sentences(narrative.narrative, name, llm_value)
                if sentences:
                    record.narrative_sentences[name] = sentences

        # Trace forward to synthesis
        for s in self.state.synthesis_results:
            if s.scenario_id != scenario_id or s.outcome_variable != outcome_variable:
                continue
            cited = [c.strip() for c in str(s.source_model_id).split(",")]
            if model_id not in cited:
                continue
            record.synthesis_outcomes.append({
                "time_horizon": s.time_horizon,
                "outcome_scope": s.outcome_scope,
                "value": s.value,
                "source_model_id": s.source_model_id,
                "narrative_summary": s.narrative_summary,
            })
        if record.synthesis_outcomes:
            links["synthesis"] = True
            if not record.narrative_summary:
                record.narrative_summary = record.synthesis_outcomes[0].get("narrative_summary") or ""

        record.chain_links = links
        return record

    def trace_all_for_scenario(
        self, scenario_id: Scenario
    ) -> list[ProvenanceRecord]:
        """Build provenance records for all results in a scenario."""
        records = []
        results = self.state.get_results_for_scenario(scenario_id)
        for result in results:
            for variable in result.outputs:
                records.append(
                    self.trace(scenario_id, result.model_id, variable)
                )
        return records


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, dict)):
        s = str(v)
        return s if len(s) <= 120 else s[:117] + "..."
    return str(v)


def render_chain_markdown(record: ProvenanceRecord) -> str:
    """Five-row provenance table plus the override record, as Markdown."""
    sid = getattr(record.scenario_id, "value", str(record.scenario_id))
    lines = [
        f"# Provenance chain: `{record.outcome_variable}` from `{record.source_model_id}` (scenario {sid})",
        "",
        f"Run `{record.run_id or '?'}`; chain links found: "
        + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in record.chain_links.items())
        + (" (complete)" if record.chain_complete else " (incomplete)"),
        "",
        "| step | content |",
        "|---|---|",
    ]
    # 1. narrative
    if record.narrative_sentences:
        sent = "<br>".join(
            f"**{name}**: " + " ".join(f"\"{s}\"" for s in ss) for name, ss in record.narrative_sentences.items()
        )
    elif record.scenario_narrative_excerpt:
        sent = f"(no sentence matched a parameter value) excerpt: \"{record.scenario_narrative_excerpt[:300]}...\""
    else:
        sent = "_narrative not available in this evidence set_"
    lines.append(f"| 1. Scenario narrative ({record.scenario_label or sid}) | {sent} |")
    # 2. extracted parameters
    if record.model_inputs:
        parts = []
        for name, value in record.model_inputs.items():
            unit = record.parameter_units.get(name) or ""
            conf = record.parameter_confidence.get(name, "")
            parts.append(f"`{name}` = {_fmt(value)} {unit} (confidence {conf})".strip())
        status = record.parameter_validation_status or "unknown"
        lines.append(f"| 2. Extracted parameters (analyst validation: {status}) | " + "<br>".join(parts) + " |")
    else:
        lines.append("| 2. Extracted parameters | _parameter records not available_ |")
    # 3. adapter inputs after forwarding
    if record.upstream_overrides:
        parts = []
        for o in record.upstream_overrides:
            key = f"`{o.name}`" + (f"[{o.target_key}]" if o.target_key else "")
            ran = "" if o.source_ran_in_run is None else (" (source completed in this run)" if o.source_ran_in_run else " (**source did not complete in this run**)")
            source = f"`{o.source_model_id}.{o.source_field}`" if o.source_field else f"`{o.source_model_id}` (field not recorded in this evidence set)"
            via = f" via {o.transform}" if o.transform else ""
            parts.append(
                f"{key}: LLM-extracted {_fmt(o.llm_value)} -> upstream {_fmt(o.computed_value)} "
                f"from {source}{via}; deviation "
                f"{_fmt(o.deviation_pct)}% ({'flagged' if o.flagged else 'not flagged'} at {_fmt(o.threshold_pct)}%){ran}"
            )
        lines.append("| 3. Adapter inputs (upstream forwarding overrides) | " + "<br>".join(parts) + " |")
    else:
        lines.append("| 3. Adapter inputs | LLM-extracted parameters used as-is (no upstream override recorded) |")
    # 4. model output
    mode = f"; implementation mode: {record.implementation_mode}" if record.implementation_mode else ""
    rt = f"; runtime {record.model_runtime_seconds:.3g}s" if record.model_runtime_seconds is not None else ""
    lines.append(
        f"| 4. Model output | `{record.source_model_id}.{record.outcome_variable}` = {_fmt(record.synthesized_value)}"
        f" (status {record.model_status or 'unknown'}{mode}{rt}) |"
    )
    # 5. synthesis
    if record.synthesis_outcomes:
        parts = [
            f"[{o['time_horizon']}/{o['outcome_scope']}] value {_fmt(o['value'])}: \"{o['narrative_summary']}\""
            for o in record.synthesis_outcomes
        ]
        lines.append("| 5. Synthesis | " + "<br>".join(parts) + " |")
    else:
        lines.append("| 5. Synthesis | _no synthesis outcome cites this (model, variable)_ |")
    lines.append("")
    return "\n".join(lines)
