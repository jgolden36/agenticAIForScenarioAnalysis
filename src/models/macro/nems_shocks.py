"""Pipeline-shock → NEMS scedes translation.

This module sits between the pipeline's standardized commodity-tier
parameters (``oil_price_shock_pct``, ``lng_price_shock_pct``,
``disruption_duration_months``, ...) and NEMS's scedes scenario file
format. It produces a ``dict[scedes_key, scedes_value]`` that
``NEMSAdapter._translate_for_execution`` merges into ``scedes_overrides``
before launching ``cycle.py``.

The mapping conventions are documented in
``Models/General Equilibrium/EIA/MAM_AEO2025.pdf`` (Macro Activity Module).
The default keys below correspond to the scedes overrides required to
inject world-oil-price, natural-gas-price, and time-window perturbations
into a NEMS run.

Pipeline param                       → scedes key   (NEMS module)
-----------------------------------  ──────────────  ─────────────────
``oil_price_shock_pct``              ``OGWPRNG``     OGSM (Oil & Gas Supply)
``lng_price_shock_pct``              ``EXG``/``EXL`` NGMM/HSM (LNG & Hub)
``natural_gas_price_shock_pct``      ``EXG``         NGMM
``disruption_duration_months``       ``LASTYR``      Cycle controller
``shock_window_start_year``          ``FRSTYR``      Cycle controller
``industrial_demand_shock_pct``      ``EXI``         IDM
``electricity_demand_shock_pct``     ``EXE``         EMM

Custom overrides supplied via ``scedes_overrides`` in the pipeline
parameters always take precedence over the auto-derived ones — this
preserves the analyst's ability to tune individual scedes keys without
editing this module.
"""

from __future__ import annotations

from typing import Any

# Default sector→scedes-key mapping. Mirrors MAM/MAM_AEO2025.pdf
# Section "Pipeline Linkages — Macro to Energy".
DEFAULT_MAM_LINK_TABLE: dict[str, str] = {
    "oil_price_shock_pct": "OGWPRNG",
    "natural_gas_price_shock_pct": "EXG",
    "lng_price_shock_pct": "EXL",
    "industrial_demand_shock_pct": "EXI",
    "electricity_demand_shock_pct": "EXE",
}

# Defaults for scenario-window control keys (overridable by the analyst).
DEFAULT_FIRSTYR = 2026  # baseline first projection year for the Hormuz case
DEFAULT_LASTYR = 2050   # NEMS AEO2025 horizon


def _shock_value(value: Any) -> str | None:
    """Coerce a shock parameter into a scedes-compatible scalar string.

    NEMS scedes accepts numeric values (parsed by parse_scedes.py) and
    short string literals. Returns ``None`` if the value is missing or
    cannot be coerced.
    """
    if value is None:
        return None
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return None


def translate_pipeline_shocks_to_scedes(
    params: dict[str, Any],
    mam_link_table: dict[str, str] | None = None,
    firstyr: int = DEFAULT_FIRSTYR,
    lastyr: int = DEFAULT_LASTYR,
    enable_shock_window_clamp: bool = True,
) -> dict[str, str]:
    """Convert pipeline parameters into scedes overrides.

    Args:
        params: The pipeline-supplied parameter dict (see module docstring
            for recognized keys).
        mam_link_table: Optional override for the parameter→scedes-key map.
        firstyr: First projection year (default 2026 for the Hormuz case).
        lastyr: Last projection year (default 2050 for AEO2025).
        enable_shock_window_clamp: When True, ``disruption_duration_months``
            clamps ``LASTYR`` so the shock window covers the disruption
            plus a 5-year tail (cap at the input ``lastyr``).

    Returns:
        Dict of scedes KEY → string value. Empty dict if no recognised
        pipeline shocks are present.
    """
    if mam_link_table is None:
        mam_link_table = dict(DEFAULT_MAM_LINK_TABLE)

    overrides: dict[str, str] = {}

    # 1. Direct sector-shock translations.
    for pipeline_key, scedes_key in mam_link_table.items():
        coerced = _shock_value(params.get(pipeline_key))
        if coerced is None:
            continue
        overrides[scedes_key] = coerced

    # 2. Window control.
    start_year = params.get("shock_window_start_year") or firstyr
    try:
        start_year_int = int(start_year)
    except (TypeError, ValueError):
        start_year_int = firstyr
    overrides["FRSTYR"] = str(start_year_int)

    duration_months = params.get("disruption_duration_months")
    if duration_months and enable_shock_window_clamp:
        try:
            duration_years = max(1, int(round(float(duration_months) / 12.0)))
        except (TypeError, ValueError):
            duration_years = 1
        # Cover the disruption plus a 5-year recovery tail, capped at lastyr.
        derived_lastyr = min(lastyr, start_year_int + duration_years + 5)
        overrides["LASTYR"] = str(derived_lastyr)

    # 3. Module activation flags (when the analyst explicitly enables them).
    modules_on = params.get("modules_on") or []
    modules_off = params.get("modules_off") or []
    from src.models.macro.nems import MODULE_FLAGS  # local import to avoid cycles
    for mod in modules_on:
        flag = MODULE_FLAGS.get(str(mod).upper())
        if flag:
            overrides[flag] = "1"
    for mod in modules_off:
        flag = MODULE_FLAGS.get(str(mod).upper())
        if flag:
            overrides[flag] = "0"

    return overrides
