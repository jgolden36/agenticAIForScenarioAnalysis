"""Cross-model consistency checking and anomaly detection (Module 4).

Implements substantive checks between models that should produce
compatible results. Flags contradictions that exceed configurable
tolerance thresholds.

Rules can be defined in two ways:
1. Declarative YAML config (configs/consistency_rules.yaml) — preferred
2. Hardcoded DEFAULT_RULES below — fallback when no YAML is available
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.common.logging import get_logger
from src.common.types import Scenario
from src.pipeline.config import ConsistencyConfig
from src.pipeline.state import ConsistencyFlag, ModelExecutionResult
from src.pipeline.upstream_to_macro import load_mapping

logger = get_logger(__name__)

# Default rules (used when no YAML config is available).
# Prefer loading from configs/consistency_rules.yaml via load_rules_from_yaml().
DEFAULT_RULES: list[dict[str, Any]] = [
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
        "description": "OpenCGE and PyCGE should agree on GDP impact direction (CGE cross-validation)",
        "tolerance_pct": 200.0,
    },
    {
        "model_a": "opencge",
        "model_b": "pycge",
        "variable_a": "welfare_pct_change",
        "variable_b": "welfare_pct_change",
        "description": "OpenCGE and PyCGE welfare changes should have the same sign and similar magnitude",
        "tolerance_pct": 200.0,
    },
    {
        "model_a": "opencge",
        "model_b": "miragrodep",
        "variable_a": "gdp_impact_pct",
        "variable_b": "gdp_impact_pct",
        "description": "OpenCGE (US OLG) and MIRAGRODEP (multi-region) should produce GDP impacts of the same sign over the disruption window",
        "tolerance_pct": 300.0,
    },
    {
        "model_a": "pycge",
        "model_b": "miragrodep",
        "variable_a": "welfare_pct_change",
        "variable_b": "welfare_pct_change",
        "description": "PyCGE and MIRAGRODEP welfare changes should agree in sign",
        "tolerance_pct": 300.0,
    },
    {
        "model_a": "nems",
        "model_b": "mam",
        "variable_a": "gdp_growth_pct",
        "variable_b": "gdp_growth_pct_year1",
        "description": "NEMS and MAM short-run GDP growth should agree within ±0.5pp at year 1",
        "tolerance_pct": 50.0,
    },
    {
        "model_a": "nems",
        "model_b": "mam",
        "variable_a": "cpi_inflation_pct",
        "variable_b": "cpi_inflation_pct_year1",
        "description": "NEMS and MAM CPI inflation should agree at year 1 (MAM derived from NEMS macro module)",
        "tolerance_pct": 50.0,
    },
    {
        "model_a": "nems",
        "model_b": "nrel",
        "variable_a": "electricity_price_change_pct",
        "variable_b": "electricity_price_change_pct",
        "description": "Energy models should agree on electricity price direction",
    },
    # ----------------------------------------------------------------
    # Energy-systems consistency: cross-checks between OSeMOSYS,
    # MESSAGEix, TEMOA, and the commodity-level oil model. Tolerances
    # are deliberately wide (long-run capacity-expansion models cover
    # decades and are sensitive to baseline calibration).
    # ----------------------------------------------------------------
    {
        "model_a": "bornstein_krusell_rebelo",
        "model_b": "messageix",
        "variable_a": "oil_price_usd",
        "variable_b": "oil_price_usd",
        "description": (
            "BKR (commodity-level GE oil price) and MESSAGEix "
            "(long-run integrated assessment) should agree on oil-price "
            "direction during the disruption window"
        ),
        "tolerance_pct": 200.0,
    },
    {
        "model_a": "osemosys",
        "model_b": "messageix",
        "variable_a": "total_system_cost_usd",
        "variable_b": "total_system_cost_usd",
        "description": (
            "OSeMOSYS and MESSAGEix should agree on the sign of the "
            "long-run total-system-cost shift"
        ),
        "tolerance_pct": 300.0,
    },
    {
        "model_a": "temoa",
        "model_b": "osemosys",
        "variable_a": "total_system_cost_usd",
        "variable_b": "total_system_cost_usd",
        "description": (
            "TEMOA and OSeMOSYS — both least-cost capacity-expansion "
            "models — should produce same-sign total-system-cost changes"
        ),
        "tolerance_pct": 200.0,
    },
    {
        "model_a": "osemosys",
        "model_b": "nems",
        "variable_a": "gas_consumption_bcfd",
        "variable_b": "gas_consumption_bcfd",
        "description": (
            "OSeMOSYS (when configured for US scope) and NEMS should "
            "agree on US gas-consumption direction"
        ),
        "tolerance_pct": 200.0,
    },
]

# Module-level cache for loaded rules
_loaded_rules: list[dict[str, Any]] | None = None


def load_rules_from_yaml(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load consistency rules from a YAML configuration file.

    The YAML file should contain a top-level 'rules' key with a list of
    rule dicts, each containing: model_a, model_b, variable_a, variable_b,
    tolerance_pct, and description.

    Args:
        path: Path to the YAML file. If None, looks for
              configs/consistency_rules.yaml relative to project root.

    Returns:
        List of rule dicts. Falls back to DEFAULT_RULES if file not found.
    """
    global _loaded_rules

    if path is None:
        # Try to find the config relative to this file
        project_root = Path(__file__).parent.parent.parent
        path = project_root / "configs" / "consistency_rules.yaml"

    path = Path(path)
    if not path.exists():
        logger.info(f"No consistency rules YAML at {path}; using default rules")
        return DEFAULT_RULES

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    rules = data.get("rules", [])
    if not rules:
        logger.warning(f"Consistency rules YAML at {path} has no rules; using defaults")
        return DEFAULT_RULES

    logger.info(f"Loaded {len(rules)} consistency rules from {path}")
    _loaded_rules = rules
    return rules


def get_consistency_rules(yaml_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Get consistency rules, loading from YAML if available.

    Uses cached rules if already loaded.
    """
    global _loaded_rules
    if _loaded_rules is not None:
        return _loaded_rules
    return load_rules_from_yaml(yaml_path)


# Keep backward-compatible alias
CONSISTENCY_RULES = DEFAULT_RULES


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


def check_upstream_overrides(
    scenario_id: Scenario,
    results: list[ModelExecutionResult],
    threshold_pct: float | None = None,
) -> list[ConsistencyFlag]:
    """Flag macro models whose LLM-extracted shocks disagreed with the
    upstream-computed values that replaced them.

    Walks each macro execution result's
    ``outputs["_upstream_overrides"]`` (populated by
    :func:`src.pipeline.upstream_to_macro.merge_into_params` via either
    the local LangGraph orchestrator or the SLURM macro dispatcher)
    and emits a :class:`ConsistencyFlag` whenever the recorded
    ``deviation_pct`` exceeds ``threshold_pct``. Records with no
    LLM value (``llm_value`` was ``None``) are skipped because
    no comparison is possible.

    Args:
        scenario_id: The scenario being checked.
        results: All execution results for this scenario.
        threshold_pct: Override the default deviation threshold from
            ``configs/upstream_to_macro_mapping.yaml`` (defaults to 50%
            when neither argument nor YAML supplies a value).
    """
    flags: list[ConsistencyFlag] = []
    if threshold_pct is None:
        threshold_pct = load_mapping().warn_threshold_pct

    for r in results:
        outputs = r.outputs or {}
        overrides = outputs.get("_upstream_overrides") or []
        if not isinstance(overrides, list):
            continue
        for rec in overrides:
            if not isinstance(rec, dict):
                continue
            deviation = rec.get("deviation_pct")
            if deviation is None:
                continue
            try:
                deviation_f = float(deviation)
            except (TypeError, ValueError):
                continue
            if deviation_f <= threshold_pct:
                continue
            target_key = rec.get("target_key")
            field_label = (
                f"{rec.get('name')}[{target_key}]" if target_key else rec.get("name")
            )
            source_model_id = str(rec.get("source_model_id") or "unknown")
            flag = ConsistencyFlag(
                scenario_id=scenario_id,
                model_a_id=str(r.model_id),
                model_b_id=source_model_id,
                variable=str(field_label),
                value_a=rec.get("llm_value"),
                value_b=rec.get("computed_value"),
                tolerance_pct=threshold_pct,
                deviation_pct=round(deviation_f, 2),
                message=(
                    f"LLM-extracted vs upstream-computed disagreement on "
                    f"{r.model_id} input {field_label}: "
                    f"LLM={rec.get('llm_value')}, "
                    f"{source_model_id}={rec.get('computed_value')} "
                    f"(deviation: {deviation_f:.1f}%, threshold: {threshold_pct}%)"
                ),
            )
            flags.append(flag)
            logger.warning(f"Upstream-override consistency flag: {flag.message}")

    return flags


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

    # Surface every "the LLM said X, the upstream model said Y" mismatch
    # the merge barrier recorded. These are macro-input disagreements,
    # not model-vs-model output disagreements, so they live alongside
    # rather than inside the rule loop below.
    flags.extend(check_upstream_overrides(scenario_id, results))

    rules = get_consistency_rules()

    for rule in rules:
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
        # Per-rule tolerance from YAML, falling back to config default
        tolerance = rule.get("tolerance_pct", config.price_tolerance_pct)

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
