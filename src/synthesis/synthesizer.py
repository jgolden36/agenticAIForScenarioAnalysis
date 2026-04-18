"""Cross-model synthesis (Module 4).

Collects results from all model runs, applies consistency checks, and
produces structured synthesis using LLM-generated narrative summaries.
Quantitative results pass through unmodified.

Supports parallel per-scenario synthesis for cluster deployments.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda

from src.common.logging import get_logger
from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.state import (
    ConsistencyFlag,
    ModelExecutionResult,
    ScenarioNarrativeState,
)
from src.synthesis.consistency import check_consistency
from src.synthesis.prompts import SYNTHESIS_PROMPT
from src.synthesis.schemas import ScenarioSynthesis

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


def _format_synthesis_inputs(inputs: dict) -> dict:
    """Format all inputs for the synthesis prompt."""
    narrative: ScenarioNarrativeState = inputs["narrative"]
    results: list[ModelExecutionResult] = inputs["results"]
    flags: list[ConsistencyFlag] = inputs["consistency_flags"]

    return {
        "scenario_id": narrative.scenario_id.value,
        "scenario_label": narrative.label,
        "scenario_description": narrative.narrative,
        "model_results": _format_model_results(results),
        "consistency_flags": _format_consistency_flags(flags),
        "failed_models": _format_failed_models(results),
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

            return flags, synthesis

    tasks = [_synthesize_one(d) for d in scenario_data]
    return await asyncio.gather(*tasks)
