"""Cross-model consistency checking and anomaly detection (Module 4).

Implements substantive checks between models that should produce
compatible results. Flags contradictions that exceed configurable
tolerance thresholds.
"""

from __future__ import annotations

from typing import Any

from src.common.logging import get_logger
from src.common.types import Scenario
from src.pipeline.config import ConsistencyConfig
from src.pipeline.state import ConsistencyFlag, ModelExecutionResult

logger = get_logger(__name__)

# Defines which pairs of models should agree on which variables,
# and the expected relationship. Each entry specifies:
#   (model_a, model_b, variable_in_a, variable_in_b, description)
CONSISTENCY_RULES: list[dict[str, str]] = [
    {
        "model_a": "bornstein_krusell_rebelo",
        "model_b": "poles_jrc",
        "variable_a": "oil_price_usd",
        "variable_b": "oil_price_usd",
        "description": "Oil price predictions should be in the same range",
    },
    {
        "model_a": "ggm",
        "model_b": "lngst",
        "variable_a": "lng_price_usd_mmbtu",
        "variable_b": "lng_price_usd_mmbtu",
        "description": "LNG price predictions should be comparable",
    },
    {
        "model_a": "world_helium_model",
        "model_b": "argonne_abm",
        "variable_a": "helium_price_usd",
        "variable_b": "helium_price_usd",
        "description": "Helium price predictions should be in the same range",
    },
    {
        "model_a": "capri",
        "model_b": "magpie",
        "variable_a": "crop_price_index",
        "variable_b": "crop_price_index",
        "description": "Agricultural price indices should be comparable",
    },
    {
        "model_a": "opencge",
        "model_b": "pycge",
        "variable_a": "gdp_impact_pct",
        "variable_b": "gdp_impact_pct",
        "description": "CGE models should produce comparable GDP impact estimates",
    },
    {
        "model_a": "nems",
        "model_b": "nrel",
        "variable_a": "electricity_price_change_pct",
        "variable_b": "electricity_price_change_pct",
        "description": "Energy models should agree on electricity price direction",
    },
]


def _compute_deviation_pct(value_a: float, value_b: float) -> float:
    """Compute percentage deviation between two values.

    Uses the average of the two values as the denominator to avoid
    division-by-zero and to treat both values symmetrically.
    """
    if value_a == 0 and value_b == 0:
        return 0.0
    avg = (abs(value_a) + abs(value_b)) / 2
    if avg == 0:
        return 0.0
    return abs(value_a - value_b) / avg * 100


def _extract_numeric_value(outputs: dict[str, Any], variable: str) -> float | None:
    """Try to extract a numeric value from model outputs."""
    val = outputs.get(variable)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def check_consistency(
    scenario_id: Scenario,
    results: list[ModelExecutionResult],
    config: ConsistencyConfig | None = None,
) -> list[ConsistencyFlag]:
    """Run all consistency checks for a scenario's model outputs.

    Args:
        scenario_id: The scenario being checked.
        results: All execution results for this scenario.
        config: Tolerance thresholds and settings.

    Returns:
        List of flagged inconsistencies.
    """
    config = config or ConsistencyConfig()
    flags: list[ConsistencyFlag] = []

    # Index results by model_id for fast lookup
    results_by_model: dict[str, ModelExecutionResult] = {
        r.model_id: r for r in results if r.outputs
    }

    for rule in CONSISTENCY_RULES:
        model_a_id = rule["model_a"]
        model_b_id = rule["model_b"]

        result_a = results_by_model.get(model_a_id)
        result_b = results_by_model.get(model_b_id)

        # Flag if a model is missing and config says to
        if config.flag_on_missing_model:
            if result_a is None and model_a_id in {r.model_id for r in results}:
                logger.info(
                    f"Consistency check skipped: {model_a_id} has no outputs"
                )
            if result_b is None and model_b_id in {r.model_id for r in results}:
                logger.info(
                    f"Consistency check skipped: {model_b_id} has no outputs"
                )

        if result_a is None or result_b is None:
            continue

        val_a = _extract_numeric_value(result_a.outputs, rule["variable_a"])
        val_b = _extract_numeric_value(result_b.outputs, rule["variable_b"])

        if val_a is None or val_b is None:
            continue

        deviation = _compute_deviation_pct(val_a, val_b)
        tolerance = config.price_tolerance_pct

        if deviation > tolerance:
            flag = ConsistencyFlag(
                scenario_id=scenario_id,
                model_a_id=model_a_id,
                model_b_id=model_b_id,
                variable=rule["variable_a"],
                value_a=val_a,
                value_b=val_b,
                tolerance_pct=tolerance,
                deviation_pct=round(deviation, 2),
                message=(
                    f"{rule['description']}: {model_a_id}={val_a}, "
                    f"{model_b_id}={val_b} (deviation: {deviation:.1f}%, "
                    f"tolerance: {tolerance}%)"
                ),
            )
            flags.append(flag)
            logger.warning(f"Consistency flag: {flag.message}")

    return flags
