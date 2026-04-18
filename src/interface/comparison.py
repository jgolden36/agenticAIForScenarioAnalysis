"""Cross-scenario comparison utilities (Module 5).

Highlights which outcomes are robust across scenarios vs. scenario-dependent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.common.types import Scenario
from src.pipeline.state import PipelineState, ModelExecutionResult


class OutcomeComparison(BaseModel):
    """Comparison of a single outcome variable across scenarios."""

    variable: str
    model_id: str
    values_by_scenario: dict[str, Any] = Field(default_factory=dict)
    is_robust: bool = False
    variation_pct: float | None = None
    note: str = ""


def compare_across_scenarios(
    state: PipelineState,
    variable: str,
    model_id: str,
    robustness_threshold_pct: float = 20.0,
) -> OutcomeComparison:
    """Compare a single outcome variable across all scenarios.

    Args:
        state: Pipeline state with execution results.
        variable: The output variable name to compare.
        model_id: Which model's output to use.
        robustness_threshold_pct: Max variation to consider "robust".

    Returns:
        OutcomeComparison with values and robustness assessment.
    """
    comparison = OutcomeComparison(variable=variable, model_id=model_id)

    values: list[float] = []
    for scenario in Scenario:
        result = state.get_execution_result(scenario, model_id)
        if result and variable in result.outputs:
            val = result.outputs[variable]
            comparison.values_by_scenario[scenario.value] = val
            try:
                values.append(float(val))
            except (TypeError, ValueError):
                pass

    if len(values) >= 2:
        avg = sum(values) / len(values)
        if avg != 0:
            variation = (max(values) - min(values)) / abs(avg) * 100
            comparison.variation_pct = round(variation, 2)
            comparison.is_robust = variation <= robustness_threshold_pct
            if comparison.is_robust:
                comparison.note = (
                    f"Robust: variation {variation:.1f}% is within "
                    f"{robustness_threshold_pct}% threshold"
                )
            else:
                comparison.note = (
                    f"Scenario-dependent: variation {variation:.1f}% exceeds "
                    f"{robustness_threshold_pct}% threshold"
                )

    return comparison


def find_robust_outcomes(
    state: PipelineState,
    robustness_threshold_pct: float = 20.0,
) -> tuple[list[OutcomeComparison], list[OutcomeComparison]]:
    """Identify which outcomes are robust vs. scenario-dependent.

    Args:
        state: Pipeline state with results.
        robustness_threshold_pct: Max variation threshold.

    Returns:
        Tuple of (robust_outcomes, scenario_dependent_outcomes).
    """
    # Collect all (model_id, variable) pairs from results
    all_pairs: set[tuple[str, str]] = set()
    for result in state.get_successful_results():
        for variable in result.outputs:
            all_pairs.add((result.model_id, variable))

    robust = []
    dependent = []

    for model_id, variable in sorted(all_pairs):
        comparison = compare_across_scenarios(
            state, variable, model_id, robustness_threshold_pct
        )
        if comparison.variation_pct is not None:
            if comparison.is_robust:
                robust.append(comparison)
            else:
                dependent.append(comparison)

    return robust, dependent
