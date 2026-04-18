"""LLM-based parameter extraction from scenario narratives (Module 2).

Takes validated scenario narratives and model input specifications,
extracts structured parameters for each (scenario, model) pair.

Supports both single extraction and batch extraction for parallelism
across the cluster (multiple extractions in one LLM call where possible).
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda

from src.common.logging import get_logger
from src.parameters.prompts import PARAMETER_EXTRACTION_PROMPT
from src.parameters.schemas import ModelParameterExtraction

logger = get_logger(__name__)


def _format_extraction_inputs(inputs: dict) -> dict:
    """Format inputs for the parameter extraction prompt."""
    scenario = inputs["scenario"]
    model_spec = inputs["model_spec"]

    assumptions = "\n".join(
        f"- {a.variable}: {a.value} {a.unit or ''} ({a.rationale})"
        for a in scenario.quantitative_assumptions
    )

    required_params = "\n".join(
        f"- {p['name']}: {p['description']} (unit: {p.get('unit', 'varies')})"
        for p in model_spec.get("required_parameters", [])
    )

    return {
        "scenario_id": scenario.scenario_id.value,
        "scenario_label": scenario.label,
        "scenario_narrative": scenario.narrative_timeline,
        "quantitative_assumptions": assumptions or "None specified",
        "model_id": model_spec["model_id"],
        "model_description": model_spec.get("description", ""),
        "required_parameters": required_params or "None specified",
    }


def build_parameter_extractor(llm: BaseChatModel) -> Runnable:
    """Build the parameter extraction chain.

    Args:
        llm: Configured LangChain LLM instance.

    Returns:
        A Runnable that takes {scenario: ScenarioNarrative, model_spec: dict}
        and returns a ModelParameterExtraction.
    """
    structured_llm = llm.with_structured_output(ModelParameterExtraction)

    chain = (
        RunnableLambda(_format_extraction_inputs)
        | PARAMETER_EXTRACTION_PROMPT
        | structured_llm
    )

    return chain


async def extract_parameters_batch(
    llm: BaseChatModel,
    extraction_pairs: list[dict[str, Any]],
    max_concurrency: int = 8,
) -> list[ModelParameterExtraction]:
    """Extract parameters for multiple (scenario, model) pairs concurrently.

    Uses asyncio.Semaphore to bound concurrency and avoid overwhelming
    the LLM provider's rate limits. Each pair runs as an independent
    async invocation.

    Args:
        llm: Configured LangChain LLM instance.
        extraction_pairs: List of dicts with "scenario" and "model_spec" keys.
        max_concurrency: Max concurrent LLM requests.

    Returns:
        List of ModelParameterExtraction results (same order as input).
    """
    chain = build_parameter_extractor(llm)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _extract_one(pair: dict) -> ModelParameterExtraction:
        async with semaphore:
            return await chain.ainvoke(pair)

    tasks = [_extract_one(pair) for pair in extraction_pairs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    extractions: list[ModelParameterExtraction] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            pair = extraction_pairs[i]
            scenario_id = pair["scenario"].scenario_id.value
            model_id = pair["model_spec"].get("model_id", "unknown")
            logger.error(
                f"Parameter extraction failed for {scenario_id}/{model_id}: {result}"
            )
            extractions.append(ModelParameterExtraction(parameters=[]))
        else:
            extractions.append(result)

    return extractions
