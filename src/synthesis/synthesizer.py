"""Cross-model synthesis (Module 4).

Collects results from all model runs, applies consistency checks, and
produces structured synthesis using LLM-generated narrative summaries.
Quantitative results pass through unmodified.

Supports parallel per-scenario synthesis for cluster deployments, and
chunked per-section synthesis (one LLM call per
``(scenario, time_horizon, outcome_scope)``) for context-budget safety
on small-context LLMs (see ``src/synthesis/sectioning.py``).
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda

from src.common.context_budget import (
    count_tokens,
    get_prompt_budget_tokens,
    truncate_to_budget,
)
from src.common.llm import is_context_length_error, with_overflow_retry
from src.common.logging import get_logger
from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.state import (
    ConsistencyFlag,
    ModelExecutionResult,
    ScenarioNarrativeState,
)
from src.synthesis.consistency import check_consistency
from src.synthesis.prompts import SECTION_SYNTHESIS_PROMPT, SYNTHESIS_PROMPT
from src.synthesis.regional import (
    RegionalRecord,
    aggregate_sectoral,
    aggregate_to_unified,
    dispersion_metrics,
    extract_regional_records,
    render_regional_breakdowns,
    render_sectoral_breakdowns,
)
from src.synthesis.schemas import (
    ScenarioSynthesis,
    ScopedSynthesis,
    SynthesizedOutcome,
)
from src.synthesis.sectioning import (
    CATCH_ALL_SECTION,
    ModelMetadata,
    SectionKey,
    SectionRoute,
    all_section_keys,
    load_section_routes,
    lookup_model_metadata,
    route_models_to_sections,
)

logger = get_logger(__name__)


def _format_model_results(results: list[ModelExecutionResult]) -> str:
    """Format model results for the synthesis prompt."""
    if not results:
        return "No model results available."

    sections = []
    for r in results:
        if r.status != ModelExecutionStatus.COMPLETED:
            continue
        lines = [f"### {r.model_id}"]
        for key, value in r.outputs.items():
            lines.append(f"  - {key}: {value}")
        if r.runtime_seconds:
            lines.append(f"  (runtime: {r.runtime_seconds:.1f}s)")
        sections.append("\n".join(lines))

    return "\n\n".join(sections) if sections else "No successful model results."


def _format_failed_models(results: list[ModelExecutionResult]) -> str:
    """Format failed/skipped models for the synthesis prompt."""
    failed = [
        r
        for r in results
        if r.status in (ModelExecutionStatus.FAILED, ModelExecutionStatus.SKIPPED)
    ]
    if not failed:
        return "None — all models completed successfully."

    lines = []
    for r in failed:
        lines.append(f"- {r.model_id}: {r.status.value} — {r.error_message or 'unknown'}")
    return "\n".join(lines)


def _format_consistency_flags(flags: list[ConsistencyFlag]) -> str:
    """Format consistency flags for the synthesis prompt."""
    if not flags:
        return "No consistency issues detected."
    return "\n".join(f"- {f.message}" for f in flags)


def _format_upstream_overrides(results: list[ModelExecutionResult]) -> str:
    """Render every macro model's ``_upstream_overrides`` audit list.

    The merge barrier (Algorithm 1, step 11) replaces LLM-extracted
    macro shocks with values computed from completed commodity-tier
    runs and records both the original LLM value and the substituted
    value on each macro result's ``outputs["_upstream_overrides"]``.
    Surface that here so the synthesis narrative can attribute macro
    findings to the upstream calculation rather than to the LLM.
    """
    sections: list[str] = []
    for r in results:
        if r.status != ModelExecutionStatus.COMPLETED:
            continue
        overrides = (r.outputs or {}).get("_upstream_overrides") or []
        if not isinstance(overrides, list) or not overrides:
            continue
        lines = [f"### {r.model_id}"]
        for rec in overrides:
            if not isinstance(rec, dict):
                continue
            target_key = rec.get("target_key")
            field_label = (
                f"{rec.get('name')}[{target_key}]" if target_key else rec.get("name")
            )
            llm_val = rec.get("llm_value")
            comp_val = rec.get("computed_value")
            source = rec.get("source_model_id")
            source_field = rec.get("source_field")
            deviation = rec.get("deviation_pct")
            deviation_str = (
                f"{float(deviation):.1f}%" if deviation is not None else "n/a"
            )
            lines.append(
                f"  - `{field_label}`: LLM={llm_val!r} → "
                f"upstream={comp_val!r} from `{source}.{source_field}` "
                f"(deviation: {deviation_str})"
            )
        sections.append("\n".join(lines))
    if not sections:
        return "No upstream-to-macro overrides applied (macro inputs unchanged from LLM extraction)."
    return "\n\n".join(sections)


def _format_distribution_dict(label: str, dist: dict[str, float] | None) -> str | None:
    if not dist:
        return None
    items = sorted(dist.items(), key=lambda kv: kv[1])
    rendered = ", ".join(f"{k}={v:g}" for k, v in items)
    return f"  - {label}: {rendered}"


def _format_outcome_bullet(outcome: SynthesizedOutcome) -> str:
    """Render a single SynthesizedOutcome as a Markdown bullet."""
    unit = f" {outcome.unit}" if outcome.unit else ""
    line = (
        f"- **{outcome.variable}**: {outcome.value}{unit} "
        f"_(source: `{outcome.source_model_id}`)_"
    )
    if outcome.narrative:
        line += f"\n  - {outcome.narrative}"
    if outcome.reliability_note:
        line += f"\n  - reliability: {outcome.reliability_note}"
    rd = _format_distribution_dict("regional distribution", outcome.regional_distribution)
    if rd:
        line += f"\n{rd}"
    sd = _format_distribution_dict("sectoral distribution", outcome.sectoral_distribution)
    if sd:
        line += f"\n{sd}"
    if outcome.distribution_note:
        line += f"\n  - distributional note: {outcome.distribution_note}"
    return line


def render_scenario_markdown(synthesis: ScenarioSynthesis) -> str:
    """Render a ``ScenarioSynthesis`` as a self-contained Markdown report.

    Sections are grouped by ``(time_horizon, outcome_scope)`` with one
    bullet per ``SynthesizedOutcome``. Failed models and consistency
    warnings are listed at the bottom so the analyst can see what was
    excluded.

    Used by both the SLURM driver (`slurm/scripts/run_synthesis.py`) and
    the imperative orchestrator to populate `data/reports/<run_id>/`.
    """
    lines: list[str] = []
    lines.append(f"# Scenario {synthesis.scenario_id.value}: {synthesis.scenario_label}")
    lines.append("")

    if synthesis.sections:
        for section in synthesis.sections:
            heading = (
                f"## {section.time_horizon.value.replace('_', ' ').title()} — "
                f"{section.outcome_scope.value.title()}"
            )
            lines.append(heading)
            lines.append("")
            if not section.outcomes:
                lines.append("_No outcomes synthesized for this section._")
                lines.append("")
                continue
            for outcome in section.outcomes:
                lines.append(_format_outcome_bullet(outcome))
            lines.append("")
    else:
        lines.append("_No synthesized sections produced for this scenario._")
        lines.append("")

    if synthesis.consistency_warnings:
        lines.append("## Cross-model consistency warnings")
        lines.append("")
        for warning in synthesis.consistency_warnings:
            lines.append(f"- {warning}")
        lines.append("")

    if synthesis.failed_models:
        lines.append("## Failed / skipped models")
        lines.append("")
        for model_id in synthesis.failed_models:
            lines.append(f"- `{model_id}`")
        lines.append("")

    return "\n".join(lines)


def _collect_regional_records(
    results: list[ModelExecutionResult],
) -> dict[str, list[RegionalRecord]]:
    """Walk every completed result through the distributional spec and
    return ``{model_id: [RegionalRecord, ...]}``. Always safe to call
    — returns an empty dict when no spec/crosswalk YAML is present.
    """
    out: dict[str, list[RegionalRecord]] = {}
    for r in results:
        if r.status != ModelExecutionStatus.COMPLETED:
            continue
        recs = extract_regional_records(r.model_id, r.outputs or {})
        if recs:
            out[r.model_id] = recs
    return out


def _attach_distributional_data(
    synthesis: ScenarioSynthesis,
    records_by_model: dict[str, list[RegionalRecord]],
) -> ScenarioSynthesis:
    """Pre-populate each ``SynthesizedOutcome`` with the regional /
    sectoral distribution that came from its source model, *replacing*
    any LLM-generated values for those fields.

    The LLM keeps authorship of ``distribution_note`` (a 1–2 sentence
    qualitative call-out) but never of the numeric distribution dicts —
    that satisfies the "LLM must not fabricate quantitative results"
    constraint from the project spec.
    """
    if not records_by_model:
        return synthesis
    unified = aggregate_to_unified(
        [rec for recs in records_by_model.values() for rec in recs]
    )
    sectoral = aggregate_sectoral(
        [rec for recs in records_by_model.values() for rec in recs]
    )
    for section in synthesis.sections:
        for outcome in section.outcomes:
            src = outcome.source_model_id or ""
            recs = records_by_model.get(src) or records_by_model.get(src.lower())
            if not recs:
                continue
            best_regional: dict[str, float] | None = None
            best_size = 0
            for (model_id, _output_key, _value_label), region_vals in unified.items():
                if model_id != src:
                    continue
                if len(region_vals) > best_size:
                    best_size = len(region_vals)
                    best_regional = dict(region_vals)
            if best_regional:
                outcome.regional_distribution = best_regional
            best_sectoral: dict[str, float] | None = None
            best_size = 0
            for (model_id, _output_key, _value_label), sec_vals in sectoral.items():
                if model_id != src:
                    continue
                if len(sec_vals) > best_size:
                    best_size = len(sec_vals)
                    best_sectoral = dict(sec_vals)
            if best_sectoral:
                outcome.sectoral_distribution = best_sectoral
            outcome.native_regional_records = [
                {
                    "model_id": rec.model_id,
                    "output_key": rec.output_key,
                    "native_region": rec.native_region,
                    "unified_region": rec.unified_region,
                    "sector": rec.sector,
                    "value_label": rec.value_label,
                    "value": rec.value,
                }
                for rec in recs
            ]
    return synthesis


def _format_synthesis_inputs(inputs: dict) -> dict:
    """Format all inputs for the synthesis prompt."""
    narrative: ScenarioNarrativeState = inputs["narrative"]
    results: list[ModelExecutionResult] = inputs["results"]
    flags: list[ConsistencyFlag] = inputs["consistency_flags"]

    records_by_model = _collect_regional_records(results)

    return {
        "scenario_id": narrative.scenario_id.value,
        "scenario_label": narrative.label,
        "scenario_description": narrative.narrative,
        "model_results": _format_model_results(results),
        "upstream_overrides": _format_upstream_overrides(results),
        "consistency_flags": _format_consistency_flags(flags),
        "failed_models": _format_failed_models(results),
        "regional_breakdowns": render_regional_breakdowns(records_by_model),
        "sectoral_breakdowns": render_sectoral_breakdowns(records_by_model),
    }


def build_synthesizer(llm: BaseChatModel) -> Runnable:
    """Build the synthesis chain.

    Args:
        llm: Configured LangChain LLM instance.

    Returns:
        A Runnable that takes {narrative, results, consistency_flags}
        and returns a ScenarioSynthesis.
    """
    structured_llm = llm.with_structured_output(ScenarioSynthesis)

    chain = (
        RunnableLambda(_format_synthesis_inputs)
        | SYNTHESIS_PROMPT
        | structured_llm
    )

    return chain


def run_consistency_and_synthesize(
    llm: BaseChatModel,
    scenario_id: Scenario,
    narrative: ScenarioNarrativeState,
    results: list[ModelExecutionResult],
    consistency_config=None,
) -> tuple[list[ConsistencyFlag], ScenarioSynthesis]:
    """Run consistency checks and then synthesize for a scenario.

    Args:
        llm: Configured LLM.
        scenario_id: The scenario.
        narrative: The scenario narrative.
        results: All execution results for this scenario.
        consistency_config: Optional consistency thresholds.

    Returns:
        Tuple of (consistency_flags, synthesis).
    """
    flags = check_consistency(scenario_id, results, consistency_config)

    chain = build_synthesizer(llm)
    synthesis = chain.invoke({
        "narrative": narrative,
        "results": results,
        "consistency_flags": flags,
    })

    records_by_model = _collect_regional_records(results)
    synthesis = _attach_distributional_data(synthesis, records_by_model)

    return flags, synthesis


async def synthesize_all_scenarios(
    llm: BaseChatModel,
    scenario_data: list[dict[str, Any]],
    consistency_config: Any = None,
    max_concurrency: int = 4,
) -> list[tuple[list[ConsistencyFlag], ScenarioSynthesis]]:
    """Synthesize all scenarios in parallel.

    Each scenario's consistency check + LLM synthesis runs as an
    independent async task, bounded by max_concurrency.

    Args:
        llm: Configured LLM.
        scenario_data: List of dicts with keys:
            - "scenario_id": Scenario enum
            - "narrative": ScenarioNarrativeState
            - "results": list[ModelExecutionResult]
        consistency_config: Optional consistency thresholds.
        max_concurrency: Max concurrent synthesis tasks.

    Returns:
        List of (flags, synthesis) tuples in same order as input.
    """
    chain = build_synthesizer(llm)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _synthesize_one(
        data: dict,
    ) -> tuple[list[ConsistencyFlag], ScenarioSynthesis]:
        async with semaphore:
            scenario_id = data["scenario_id"]
            narrative = data["narrative"]
            results = data["results"]

            flags = check_consistency(scenario_id, results, consistency_config)

            synthesis = await chain.ainvoke({
                "narrative": narrative,
                "results": results,
                "consistency_flags": flags,
            })

            records_by_model = _collect_regional_records(results)
            synthesis = _attach_distributional_data(synthesis, records_by_model)

            return flags, synthesis

    tasks = [_synthesize_one(d) for d in scenario_data]
    return await asyncio.gather(*tasks)


# ====================================================================
# Section-aware (chunked) synthesis path
# ====================================================================
#
# The legacy build_synthesizer / run_consistency_and_synthesize path
# packs every completed model's outputs into one LLM call per scenario.
# That works for cloud LLMs with 128K+ contexts but blows the 8K
# default vLLM ceiling on the SBU AI Cluster. The functions below
# split that single call into one per (scenario, time_horizon,
# outcome_scope) using the routing rules in
# ``src/synthesis/sectioning.py``.
#
# Information preservation: every completed model's outputs end up in
# at least one section's prompt, so no data is lost. Each per-section
# prompt is also truncated to ``get_prompt_budget_tokens()`` and
# wrapped with ``with_overflow_retry`` so vLLM HTTP 400 ("maximum
# context length") errors trigger a halved-prompt retry instead of
# crashing the synthesis stage.


# Fraction of the prompt budget reserved for the formatted model_results
# block in a section call. The remaining ~25% is reserved for the
# scenario narrative, consistency flags, override audit, regional /
# sectoral tables, the system + human template overhead, and the
# structured-output schema descriptions.
_SECTION_RESULTS_BUDGET_FRACTION = 0.55


def _filter_results_for_section(
    all_results: list[ModelExecutionResult],
    model_ids: set[str],
) -> list[ModelExecutionResult]:
    """Return only the ``ModelExecutionResult`` entries whose model_id is in ``model_ids``."""
    if not model_ids:
        return []
    return [r for r in all_results if r.model_id in model_ids]


def _filter_consistency_flags_for_section(
    all_flags: list[ConsistencyFlag],
    model_ids: set[str],
) -> list[ConsistencyFlag]:
    """Keep only consistency flags whose involved models overlap the section.

    ``ConsistencyFlag`` carries ``model_a_id`` and ``model_b_id`` (one
    pair per flag); a flag is included in a section if either side is
    a model the section actually owns.
    """
    if not model_ids:
        return []
    out: list[ConsistencyFlag] = []
    for f in all_flags:
        involved = {
            getattr(f, "model_a_id", None),
            getattr(f, "model_b_id", None),
        } - {None}
        if not involved:
            # Cross-cutting flags (no specific model attribution) are
            # kept on every section so the LLM always sees them.
            out.append(f)
        elif involved & model_ids:
            out.append(f)
    return out


def _format_section_inputs(
    scenario_id: Scenario,
    scenario_label: str,
    scenario_description: str,
    section_key: SectionKey,
    section_results: list[ModelExecutionResult],
    consistency_flags: list[ConsistencyFlag],
    records_by_model: dict[str, list[RegionalRecord]],
    prompt_budget_tokens: int | None = None,
) -> dict[str, Any]:
    """Build the LangChain prompt input dict for a single section.

    Mirrors ``_format_synthesis_inputs`` but operates on the section's
    pre-filtered slice of results / flags / regional records, and
    truncates the heaviest text blocks to a per-call token budget.
    """
    if prompt_budget_tokens is None:
        prompt_budget_tokens = get_prompt_budget_tokens()

    # Per-block sub-budgets. The model_results block dominates (it
    # contains every completed adapter's full output dict), so it gets
    # the lion's share. Regional / sectoral / override-audit blocks
    # share the rest equally.
    results_budget = max(512, int(prompt_budget_tokens * _SECTION_RESULTS_BUDGET_FRACTION))
    aux_budget = max(256, int(prompt_budget_tokens * 0.10))

    model_results = truncate_to_budget(
        _format_model_results(section_results),
        results_budget,
    )
    upstream_overrides = truncate_to_budget(
        _format_upstream_overrides(section_results),
        aux_budget,
    )
    failed_models = truncate_to_budget(
        _format_failed_models(section_results),
        aux_budget,
    )
    consistency_text = truncate_to_budget(
        _format_consistency_flags(consistency_flags),
        aux_budget,
    )
    regional_text = truncate_to_budget(
        render_regional_breakdowns(records_by_model),
        aux_budget,
    )
    sectoral_text = truncate_to_budget(
        render_sectoral_breakdowns(records_by_model),
        aux_budget,
    )

    # Cap the scenario narrative the same way ``export_results.py``
    # does — it is the same descriptive text used across every section
    # call for this scenario, so there is no point spending more than
    # ~1000 tokens on it.
    scenario_text = truncate_to_budget(scenario_description or "", 1024)

    return {
        "scenario_id": scenario_id.value,
        "scenario_label": scenario_label,
        "section_time_horizon": section_key.time_horizon.value,
        "section_outcome_scope": section_key.outcome_scope.value,
        "scenario_description": scenario_text,
        "model_results": model_results,
        "upstream_overrides": upstream_overrides,
        "consistency_flags": consistency_text,
        "failed_models": failed_models,
        "regional_breakdowns": regional_text,
        "sectoral_breakdowns": sectoral_text,
    }


def _halve_section_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Halve every text-heavy field of a section prompt input dict.

    Used as the ``truncate_input`` callback for ``with_overflow_retry``
    so a context-length error on the first attempt re-invokes the
    chain with prompt content halved. Returns a new dict — callers
    must not depend on the input dict being mutated.
    """
    halved: dict[str, Any] = dict(inputs)
    for field in (
        "model_results",
        "upstream_overrides",
        "consistency_flags",
        "failed_models",
        "regional_breakdowns",
        "sectoral_breakdowns",
        "scenario_description",
    ):
        text = inputs.get(field)
        if not isinstance(text, str) or not text:
            continue
        current_tokens = count_tokens(text)
        if current_tokens <= 1:
            continue
        halved[field] = truncate_to_budget(text, max(64, current_tokens // 2))
    return halved


def build_section_synthesizer(
    llm: BaseChatModel,
    on_truncation: Callable[[SectionKey, int], None] | None = None,
    section_key: SectionKey | None = None,
) -> Runnable:
    """Build a synthesis chain that emits a single ``ScopedSynthesis``.

    The returned Runnable accepts the dict shape produced by
    ``_format_section_inputs`` and returns one ``ScopedSynthesis``
    object. Wrapped with ``with_overflow_retry`` so a context-length
    error halves the prompt and retries once before surfacing.

    Args:
        llm: Configured LangChain chat model.
        on_truncation: Optional callback invoked with
            ``(section_key, attempt_number)`` whenever the overflow
            retry kicks in. Used by the run_synthesis driver to record
            truncation events into the W&B run config.
        section_key: The section this chain is for; passed to
            ``on_truncation`` so the callback can attribute the event
            to the right section. Optional only because some unit
            tests construct a chain without one.
    """
    structured_llm = llm.with_structured_output(ScopedSynthesis)

    inner_chain: Runnable = SECTION_SYNTHESIS_PROMPT | structured_llm

    callback = None
    if on_truncation is not None and section_key is not None:
        def callback(attempt: int) -> None:  # noqa: E306
            on_truncation(section_key, attempt)

    return with_overflow_retry(
        inner_chain,
        truncate_input=_halve_section_inputs,
        on_truncation=callback,
    )


def _empty_scoped_synthesis(section_key: SectionKey) -> ScopedSynthesis:
    """Return an empty ``ScopedSynthesis`` for a section with no models."""
    return ScopedSynthesis(
        time_horizon=section_key.time_horizon,
        outcome_scope=section_key.outcome_scope,
        outcomes=[],
    )


def _aggregate_sections_into_scenario(
    scenario_id: Scenario,
    scenario_label: str,
    section_outputs: list[ScopedSynthesis],
    flagged_models: list[str],
    consistency_warnings: list[str],
) -> ScenarioSynthesis:
    """Combine per-section ``ScopedSynthesis`` objects into one ``ScenarioSynthesis``.

    Sections with no outcomes are still listed (as empty sections) so
    downstream consumers can see the full 6-section grid; this matches
    the legacy synthesizer's behaviour when the LLM returned an empty
    section.
    """
    return ScenarioSynthesis(
        scenario_id=scenario_id,
        scenario_label=scenario_label,
        sections=section_outputs,
        failed_models=flagged_models,
        consistency_warnings=consistency_warnings,
    )


def synthesize_by_section(
    llm: BaseChatModel,
    scenario_id: Scenario,
    narrative: ScenarioNarrativeState,
    results: list[ModelExecutionResult],
    consistency_config=None,
    routes: list[SectionRoute] | None = None,
    on_truncation: Callable[[SectionKey, int], None] | None = None,
) -> tuple[list[ConsistencyFlag], ScenarioSynthesis, dict[SectionKey, dict[str, Any]]]:
    """Run consistency checks then synthesize one LLM call per section.

    Args:
        llm: Configured LLM.
        scenario_id: The scenario being synthesized.
        narrative: Validated scenario narrative state.
        results: All execution results for this scenario.
        consistency_config: Optional consistency thresholds.
        routes: Section routing rules; defaults to
            ``load_section_routes()``.
        on_truncation: Optional callback ``(section_key, attempt) -> None``
            invoked when ``with_overflow_retry`` halves the prompt.

    Returns:
        A 3-tuple ``(flags, scenario_synthesis, section_metrics)``:
        - ``flags``: cross-model consistency flags for the scenario.
        - ``scenario_synthesis``: aggregated ``ScenarioSynthesis``.
        - ``section_metrics``: per-section dict with ``model_count``,
          ``prompt_tokens``, ``status`` (``"ok"|"empty"|"failed"``),
          and ``truncation_attempts``. Used by the SLURM driver to
          surface budget telemetry into the W&B summary.
    """
    routes = routes or load_section_routes()
    flags = check_consistency(scenario_id, results, consistency_config)

    # Build section -> [model_id] routing once for the whole scenario.
    completed_results = [
        r for r in results if r.status == ModelExecutionStatus.COMPLETED
    ]
    model_ids = [r.model_id for r in completed_results]
    metadata_by_id = lookup_model_metadata(model_ids)
    metadata_list: list[ModelMetadata] = []
    for r in completed_results:
        meta = metadata_by_id.get(r.model_id)
        if meta is None:
            # Unknown adapter — route to the catch-all section so its
            # output still appears somewhere in the synthesis.
            logger.warning(
                f"No metadata for model {r.model_id!r}; routing to catch-all section "
                f"({CATCH_ALL_SECTION.label()})."
            )
            from src.common.types import AnalyticalLevel, CommoditySystem  # noqa: WPS433
            meta = ModelMetadata(
                model_id=r.model_id,
                commodity_system=CommoditySystem.MACROECONOMIC,
                analytical_level=AnalyticalLevel.SHORT_RUN_MACRO,
            )
        metadata_list.append(meta)

    section_to_ids: dict[SectionKey, list[str]] = route_models_to_sections(
        metadata_list, routes
    )

    # Pre-extract regional records once (used per-section by filtering).
    all_records = _collect_regional_records(completed_results)

    # Truncation event tracker — we re-emit a callback that records the
    # event by section even though build_section_synthesizer will only
    # see one section at a time.
    truncation_events: dict[SectionKey, int] = {key: 0 for key in section_to_ids}

    def _record(key: SectionKey, attempt: int) -> None:
        truncation_events[key] = max(truncation_events[key], attempt)
        if on_truncation is not None:
            on_truncation(key, attempt)

    section_outputs: list[ScopedSynthesis] = []
    section_metrics: dict[SectionKey, dict[str, Any]] = {}
    flagged_models: set[str] = set()
    consistency_warnings: set[str] = set()

    for section_key in all_section_keys(routes):
        ids = set(section_to_ids.get(section_key, []))
        section_results = _filter_results_for_section(results, ids)
        section_flags = _filter_consistency_flags_for_section(flags, ids)
        section_records = {
            mid: recs for mid, recs in all_records.items() if mid in ids
        }

        if not section_results:
            # No models routed here — emit an empty ScopedSynthesis so
            # the 6-section grid stays uniform.
            empty = _empty_scoped_synthesis(section_key)
            section_outputs.append(empty)
            section_metrics[section_key] = {
                "model_count": 0,
                "prompt_tokens": 0,
                "status": "empty",
                "truncation_attempts": 0,
            }
            continue

        prompt_inputs = _format_section_inputs(
            scenario_id=scenario_id,
            scenario_label=narrative.label,
            scenario_description=narrative.narrative,
            section_key=section_key,
            section_results=section_results,
            consistency_flags=section_flags,
            records_by_model=section_records,
        )

        prompt_tokens_estimate = sum(
            count_tokens(v) for v in prompt_inputs.values() if isinstance(v, str)
        )

        chain = build_section_synthesizer(
            llm,
            on_truncation=_record,
            section_key=section_key,
        )

        try:
            scoped = chain.invoke(prompt_inputs)
        except Exception as exc:
            # Defensive fallback: surface an empty section + a
            # consistency-warning record. The synthesis stage stays
            # alive and the missing section is auditable.
            kind = (
                "context-length"
                if is_context_length_error(exc)
                else type(exc).__name__
            )
            logger.error(
                f"Section synthesis failed for scenario={scenario_id.value} "
                f"section={section_key.label()} ({kind}): {exc}"
            )
            consistency_warnings.add(
                f"Section {section_key.label()} synthesis failed: {kind}"
            )
            scoped = _empty_scoped_synthesis(section_key)
            section_metrics[section_key] = {
                "model_count": len(section_results),
                "prompt_tokens": prompt_tokens_estimate,
                "status": "failed",
                "truncation_attempts": truncation_events.get(section_key, 0),
                "error": kind,
            }
            section_outputs.append(scoped)
            continue

        section_outputs.append(scoped)
        section_metrics[section_key] = {
            "model_count": len(section_results),
            "prompt_tokens": prompt_tokens_estimate,
            "status": "ok",
            "truncation_attempts": truncation_events.get(section_key, 0),
        }

    # Failed/skipped models from the scenario as a whole (not just this
    # section). ScopedSynthesis itself has no failed_models /
    # consistency_warnings fields — those are aggregated at the
    # ScenarioSynthesis level only.
    for r in results:
        if r.status in (ModelExecutionStatus.FAILED, ModelExecutionStatus.SKIPPED):
            flagged_models.add(r.model_id)
    for f in flags:
        # Surface every consistency flag's message at the scenario
        # level so render_scenario_markdown can print them, exactly
        # like the legacy code path did.
        msg = getattr(f, "message", None)
        if msg:
            consistency_warnings.add(msg)

    aggregated = _aggregate_sections_into_scenario(
        scenario_id=scenario_id,
        scenario_label=narrative.label,
        section_outputs=section_outputs,
        flagged_models=sorted(flagged_models),
        consistency_warnings=sorted(consistency_warnings),
    )

    # Re-attach numeric distributional data exactly as the legacy
    # path does. The LLM never authors these dicts; they come from the
    # upstream model outputs.
    aggregated = _attach_distributional_data(aggregated, all_records)

    return flags, aggregated, section_metrics
