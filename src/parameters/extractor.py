"""LLM-based parameter extraction from scenario narratives (Module 2).

Takes validated scenario narratives and model input specifications,
extracts structured parameters for each (scenario, model) pair.

Supports both single extraction and batch extraction for parallelism
across the cluster (multiple extractions in one LLM call where possible).

The extractor wraps the structured-output chain with a small retry loop
that re-prompts the LLM with the prior validation error as a corrective
hint. This catches the common failure mode where the LLM returns ``null``
or a non-numeric string for a required numeric parameter and the strict
adapter validators reject the entire model run downstream.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import ValidationError

from src.common.logging import get_logger
from src.parameters.prompts import PARAMETER_EXTRACTION_PROMPT
from src.parameters.schemas import (
    ExtractedParameter,
    ModelParameterExtraction,
)

logger = get_logger(__name__)

DEFAULT_MAX_RETRIES = 2


def _render_extra_hints(p: dict) -> str:
    """Render value_range / valid_values / value_schema hints for the LLM.

    These optional spec annotations were added to keep the LLM from
    emitting structurally-wrong parameters (e.g. dict-of-dicts where a
    dict-of-floats is expected, or out-of-range numerics that the
    adapter then rejects). Rendering them inline in the prompt is
    enough to push compliance up substantially without needing
    schema-level enforcement.
    """
    parts: list[str] = []
    if "value_range" in p:
        lo, hi = p["value_range"][0], p["value_range"][1]
        parts.append(f"value_range: [{lo}, {hi}]")
    if "valid_values" in p:
        vals = ", ".join(repr(v) for v in p["valid_values"])
        parts.append(f"valid_values: [{vals}]")
    if "value_schema" in p:
        parts.append(f"value_schema: {p['value_schema']}")
    if not parts:
        return ""
    return "  [" + "; ".join(parts) + "]"


def _format_required_parameters(model_spec: dict) -> str:
    """Render the spec's required parameters with type hints for the LLM."""
    lines: list[str] = []
    for p in model_spec.get("required_parameters", []):
        type_hint = p.get("type", "any")
        unit = p.get("unit", "varies")
        extra = _render_extra_hints(p)
        lines.append(
            f"- {p['name']}: {p['description']} "
            f"(unit: {unit}; expected_type: {type_hint}){extra}"
        )
    return "\n".join(lines) or "None specified"


def _format_optional_parameters(model_spec: dict) -> str:
    """Render the spec's optional parameters (may be omitted entirely)."""
    lines: list[str] = []
    for p in model_spec.get("optional_parameters", []):
        type_hint = p.get("type", "any")
        unit = p.get("unit", "varies")
        extra = _render_extra_hints(p)
        lines.append(
            f"- {p['name']}: {p['description']} "
            f"(unit: {unit}; expected_type: {type_hint}){extra}"
        )
    return "\n".join(lines) or "None"


def _build_expected_type_lookup(model_spec: dict) -> dict[str, str]:
    """Map parameter name -> expected_type from the spec."""
    out: dict[str, str] = {}
    for key in ("required_parameters", "optional_parameters"):
        for p in model_spec.get(key, []) or []:
            out[p["name"]] = p.get("type", "any")
    return out


def _format_extraction_inputs(inputs: dict) -> dict:
    """Format inputs for the parameter extraction prompt."""
    scenario = inputs["scenario"]
    model_spec = inputs["model_spec"]
    correction_hint = inputs.get("correction_hint", "")

    assumptions = "\n".join(
        f"- {a.variable}: {a.value} {a.unit or ''} ({a.rationale})"
        for a in scenario.quantitative_assumptions
    )

    return {
        "scenario_id": scenario.scenario_id.value,
        "scenario_label": scenario.label,
        "scenario_narrative": scenario.narrative_timeline,
        "quantitative_assumptions": assumptions or "None specified",
        "model_id": model_spec["model_id"],
        "model_description": model_spec.get("description", ""),
        "required_parameters": _format_required_parameters(model_spec),
        "optional_parameters": _format_optional_parameters(model_spec),
        "correction_hint": correction_hint,
    }


def _attach_expected_types(
    extraction: ModelParameterExtraction,
    type_lookup: dict[str, str],
) -> ModelParameterExtraction:
    """Re-instantiate parameters with their declared expected_type.

    The LLM is not required (or trusted) to set ``expected_type``
    correctly itself; the spec is the source of truth. Re-running each
    parameter through ``ExtractedParameter`` triggers the
    ``model_validator`` and surfaces any type/coercion failures as a
    single ``ValidationError``.
    """
    rebuilt: list[ExtractedParameter] = []
    for p in extraction.parameters:
        et = type_lookup.get(p.name, "any")
        rebuilt.append(
            ExtractedParameter(
                name=p.name,
                value=p.value,
                unit=p.unit,
                confidence=p.confidence,
                directly_stated=p.directly_stated,
                extraction_note=p.extraction_note,
                expected_type=et,
            )
        )
    return ModelParameterExtraction(
        scenario_id=extraction.scenario_id,
        model_id=extraction.model_id,
        parameters=rebuilt,
        warnings=extraction.warnings,
    )


def build_parameter_extractor(
    llm: BaseChatModel,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Runnable:
    """Build the parameter extraction chain with type-aware retries.

    The returned Runnable accepts ``{scenario, model_spec}`` and returns a
    ``ModelParameterExtraction`` whose parameters have been validated
    against the ``expected_type`` declared in the spec. On validation
    failure, the chain re-prompts the LLM up to ``max_retries`` times,
    appending the prior error as a corrective hint each time.
    """
    structured_llm = llm.with_structured_output(ModelParameterExtraction)
    base_chain = (
        RunnableLambda(_format_extraction_inputs)
        | PARAMETER_EXTRACTION_PROMPT
        | structured_llm
    )

    def _extract_with_retry(inputs: dict) -> ModelParameterExtraction:
        type_lookup = _build_expected_type_lookup(inputs["model_spec"])
        last_error: Exception | None = None
        attempt_inputs = dict(inputs)

        for attempt in range(max_retries + 1):
            try:
                raw: ModelParameterExtraction = base_chain.invoke(attempt_inputs)
                return _attach_expected_types(raw, type_lookup)
            except (ValidationError, ValueError) as exc:
                last_error = exc
                hint = (
                    "Your previous response failed validation:\n"
                    f"{exc}\n\n"
                    "Re-extract the parameters. For numeric required parameters "
                    "you MUST provide a non-null best-effort numeric value (mark "
                    "confidence='low' and directly_stated=false if you had to "
                    "estimate). For percent fields, return a number in [0, 100]. "
                    "For positive_number fields, return a value strictly > 0."
                )
                attempt_inputs = {**attempt_inputs, "correction_hint": hint}
                logger.warning(
                    "Parameter extraction validation failed on attempt "
                    f"{attempt + 1}/{max_retries + 1} for "
                    f"{inputs['model_spec'].get('model_id', 'unknown')}: {exc}"
                )

        scenario_id = inputs["scenario"].scenario_id
        model_id = inputs["model_spec"].get("model_id", "unknown")
        logger.error(
            f"Parameter extraction exhausted retries for "
            f"{scenario_id.value}/{model_id}; returning empty extraction "
            f"with warning. Last error: {last_error}"
        )
        return ModelParameterExtraction(
            scenario_id=scenario_id,
            model_id=model_id,
            parameters=[],
            warnings=[
                f"Extraction failed after {max_retries + 1} attempts: "
                f"{last_error}"
            ],
        )

    return RunnableLambda(_extract_with_retry)


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
            extractions.append(ModelParameterExtraction(
                scenario_id=pair["scenario"].scenario_id,
                model_id=model_id,
                parameters=[],
            ))
        else:
            extractions.append(result)

    return extractions
