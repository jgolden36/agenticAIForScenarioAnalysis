"""Templated, LLM-free synthesis (Module 4 comparator).

Produces a ``ScenarioSynthesis`` from model outputs with no language model
in the loop. Every ``SynthesizedOutcome`` is one scalar output of one
completed model, copied verbatim: the variable is the output key, the value
is ``str(value)``, the source is the model id, and the narrative is a fixed
template that states the number and its provenance without interpreting it.

The routing of models to the six ``(time_horizon, outcome_scope)`` sections
is the same ``src.synthesis.sectioning`` logic the LLM path uses, and the
regional / sectoral distributions and uncertainty bands are attached by the
same helpers, so the two paths differ only in who writes the prose and
which numbers get selected.

Used by ``slurm/scripts/run_deterministic_baseline.py`` to produce the
deterministic baseline (Reviewer 2, point 1) and by the fidelity tests as
the zero-drift reference: an audit of a templated synthesis must classify
every numeric outcome as ``exact``.
"""

from __future__ import annotations

from typing import Any

from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.state import ConsistencyFlag, ModelExecutionResult, ScenarioNarrativeState
from src.synthesis.consistency import check_consistency
from src.synthesis.schemas import ScenarioSynthesis, ScopedSynthesis, SynthesizedOutcome
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
from src.synthesis.synthesizer import (
    _attach_distributional_data,
    _attach_uncertainty_to_outcomes,
    _collect_regional_records,
    _empty_scoped_synthesis,
)

SYNTHESIS_METHOD = "templated"

# Preferred headline outputs per model, in display order. Any numeric
# scalar not listed here is appended alphabetically after these, up to
# ``max_outcomes_per_model``.
HEADLINE_KEYS: dict[str, list[str]] = {
    "poles_jrc": ["peak_price_change_pct", "peak_price_usd_per_bbl", "supply_loss_pct_of_global",
                  "rerouting_volume_mbd", "substitution_volume_mbd"],
    "bornstein_krusell_rebelo": ["oil_price_change_pct", "peak_oil_price_change_pct", "gdp_impact_pct"],
    "marketsim": ["consumer_surplus_loss_bn_usd", "net_welfare_impact_bn_usd", "oil_demand_destruction_mbd",
                  "gas_demand_destruction_bcfd", "consumer_surplus_loss_oil_bn_usd", "consumer_surplus_loss_gas_bn_usd"],
    "fed_oil": ["peak_gdp_impact_pct", "peak_cpi_impact_pp", "peak_ffr_impact_pp", "peak_unemployment_impact_pp",
                "fevd_oil_share", "oil_price_change_pct"],
    "lngst": ["ttf_price", "jkm_price", "henry_hub_price", "implied_price_impulse_pct", "global_supply_shortfall_pct",
              "supply_shortfall_bcm"],
    "energy_flux_gas_power": ["by_2030_new_gw", "by_2030_bcf_per_day_mid", "by_2035_new_gw", "total_pipeline_mw"],
    "energy_flux_lng_profits": ["total_war_profit_bn_usd", "incremental_margin_bn_usd", "peak_month_margin_usd_mmbtu"],
    "world_helium_model": ["effective_supply_gap_pct", "price_change_pct", "equilibrium_price_usd_per_mscf",
                           "inventory_drawdown_months", "demand_rationing_mmscf"],
    "argonne_abm": ["price_change_pct", "price_change_pct_mean", "price_change_pct_std", "effective_supply_gap_pct"],
    "simrlfab": ["throughput_loss_pct", "fab_utilization_crisis", "wafer_starts_change_pct"],
    "world_fertilizer": ["fertilizer_price_index_pct", "nitrogen_price_pct", "phosphate_price_pct", "potash_price_pct",
                         "price_urea_pct", "price_dap_pct", "price_mop_pct"],
    "apsim": ["mean_yield_pct_change", "crop_yield_loss_pct", "n_use_efficiency_change_pct"],
    "futures": ["initial_price_shock_pct", "forecast_horizon_months"],
    "aisdb": ["rerouting_cost_multiplier", "war_risk_insurance_premium_pct", "effective_fleet_capacity_loss_pct",
              "max_additional_transit_days"],
    "ais_project": ["rerouting_cost_multiplier", "additional_transit_days", "tanker_rate_change_pct",
                    "effective_fleet_capacity_loss_pct", "fleet_utilization_multiplier"],
    "cwatm": ["unmet_demand_pct", "mean_discharge_deviation_pct", "cumulative_water_deficit_pct_months",
              "desalination_capacity_factor"],
    "weap_mena": ["aggregate_unmet_demand_pct", "unmet_demand_pct", "effective_desalination_loss_pct",
                  "population_affected_millions", "cumulative_water_deficit_pct_weeks"],
    "pycge": ["gdp_impact_pct", "gdp_impact_pct_world_weighted", "cpi_inflation_pct", "consumption_impact_pct",
              "welfare_pct_change", "wage_impact_pct", "interest_rate_impact_pct"],
    "mpsge_jl": ["gdp_impact_pct", "gdp_impact_pct_world_weighted", "cpi_inflation_pct", "consumption_impact_pct",
                 "welfare_pct_change", "wage_impact_pct", "interest_rate_impact_pct", "trade_cost_multiplier"],
    "opencge": ["gdp_impact_pct", "cpi_inflation_pct", "consumption_impact_pct", "welfare_pct_change"],
    "nrel": ["gdp_impact_pct", "gdp_impact_pct_world_weighted", "cpi_inflation_pct", "retail_electricity_price_change_pct",
             "co2_emissions_pct_change", "coal_dispatch_gain_pp", "renewables_dispatch_gain_pp", "welfare_pct_change"],
    "mam": ["gdp_impact_pct", "cpi_inflation_pct", "unemployment_rate_pct", "real_gdp_bn_usd"],
    "nems": ["gdp_impact_pct", "cpi_inflation_pct", "oil_price_usd_per_bbl"],
    "miragrodep": ["gdp_impact_pct", "welfare_pct_change", "agricultural_output_pct_change"],
    "osemosys": ["gdp_impact_pct", "cpi_inflation_pct", "total_system_cost_change_pct", "welfare_pct_change"],
    "messageix": ["gdp_impact_pct", "cpi_inflation_pct", "total_system_cost_change_pct", "welfare_pct_change"],
    "temoa": ["gdp_impact_pct", "cpi_inflation_pct", "total_system_cost_change_pct", "welfare_pct_change"],
}

# Output keys that merely echo an input and carry no result information.
ECHO_KEY_PREFIXES = ("disruption_duration", "fed_funds_rate_baseline", "forecast_horizon", "horizon_")

_UNIT_SUFFIXES: list[tuple[str, str]] = [
    ("_pct_months", "percent-months"),
    ("_pct_weeks", "percent-weeks"),
    ("_pct_change", "percent"),
    ("_pct", "percent"),
    ("_pp", "percentage points"),
    ("_mbd", "mb/d"),
    ("_bcfd", "bcf/d"),
    ("_bn_usd", "USD bn"),
    ("_usd_per_bbl", "USD/bbl"),
    ("_usd_per_mscf", "USD/Mscf"),
    ("_usd_mmbtu", "USD/MMBtu"),
    ("_mmscf", "MMscf"),
    ("_months", "months"),
    ("_weeks", "weeks"),
    ("_days", "days"),
    ("_quarters", "quarters"),
    ("_millions", "millions"),
    ("_gw", "GW"),
    ("_mw", "MW"),
    ("_bcm_annualised", "bcm/yr"),
    ("_bcm", "bcm"),
    ("_multiplier", "x baseline"),
    ("_factor", "x baseline"),
    ("_share", "share"),
]
_PRICE_KEYS_USD_MMBTU = {"ttf_price", "jkm_price", "henry_hub_price", "lng_price_usd_mmbtu"}


def infer_unit(key: str) -> str | None:
    """Best-effort unit from the output key's suffix (None when unknown)."""
    if key in _PRICE_KEYS_USD_MMBTU:
        return "USD/MMBtu"
    for suffix, unit in _UNIT_SUFFIXES:
        if key.endswith(suffix):
            return unit
    return None


def _is_numeric_scalar(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def select_headline_outputs(
    model_id: str,
    outputs: dict[str, Any],
    *,
    max_outcomes_per_model: int = 10,
    params: dict[str, Any] | None = None,
) -> list[tuple[str, float | int]]:
    """Pick the scalar outputs to report for one model, in display order.

    Rules: top-level numeric scalars only (no lists, dicts, strings or
    booleans); keys starting with ``_`` are bookkeeping and skipped; keys
    that echo an input (same name and value in ``params``, or a known echo
    prefix) are skipped; preferred headline keys come first, the rest
    alphabetically; at most ``max_outcomes_per_model`` are kept.
    """
    params = params or {}
    candidates: dict[str, float | int] = {}
    for key, value in outputs.items():
        if not isinstance(key, str) or key.startswith("_"):
            continue
        if not _is_numeric_scalar(value):
            continue
        if key.startswith(ECHO_KEY_PREFIXES):
            continue
        if key in params and _is_numeric_scalar(params[key]) and float(params[key]) == float(value):
            continue
        candidates[key] = value
    ordered: list[str] = [k for k in HEADLINE_KEYS.get(model_id, []) if k in candidates]
    ordered += sorted(k for k in candidates if k not in ordered)
    return [(k, candidates[k]) for k in ordered[:max_outcomes_per_model]]


def format_value(value: float | int) -> str:
    """Verbatim string form of a numeric output (what the fidelity audit sees)."""
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer() and abs(value) < 1e15:
        return str(value)
    return repr(float(value))


def outcome_from_output(
    model_id: str,
    key: str,
    value: float | int,
    *,
    scenario_label: str,
    implementation_mode: str | None = None,
    n_overrides: int = 0,
) -> SynthesizedOutcome:
    """One templated outcome: value and source verbatim, prose from a fixed template."""
    unit = infer_unit(key)
    value_str = format_value(value)
    unit_str = f" {unit}" if unit else ""
    mode = implementation_mode or "unknown"
    narrative = (
        f"{model_id} reports {key} = {value_str}{unit_str} under {scenario_label}. "
        "Value copied verbatim from the model output; no interpretation applied."
    )
    reliability = f"implementation mode: {mode}"
    if n_overrides:
        reliability += f"; {n_overrides} input(s) replaced by upstream model outputs (see _upstream_overrides)"
    return SynthesizedOutcome(
        variable=key,
        value=value_str,
        unit=unit,
        source_model_id=model_id,
        fidelity_status="exact",
        narrative=narrative,
        reliability_note=reliability,
    )


def _metadata_for(results: list[ModelExecutionResult]) -> list[ModelMetadata]:
    completed = [r for r in results if r.status == ModelExecutionStatus.COMPLETED]
    by_id = lookup_model_metadata([r.model_id for r in completed])
    metas: list[ModelMetadata] = []
    for r in completed:
        meta = by_id.get(r.model_id)
        if meta is None:
            from src.common.types import AnalyticalLevel, CommoditySystem  # noqa: WPS433

            meta = ModelMetadata(
                model_id=r.model_id,
                commodity_system=CommoditySystem.MACROECONOMIC,
                analytical_level=AnalyticalLevel.SHORT_RUN_MACRO,
            )
        metas.append(meta)
    return metas


def templated_synthesis(
    scenario_id: Scenario,
    narrative: ScenarioNarrativeState,
    results: list[ModelExecutionResult],
    consistency_config: Any = None,
    routes: list[SectionRoute] | None = None,
    *,
    params_by_model: dict[str, dict[str, Any]] | None = None,
    max_outcomes_per_model: int = 10,
) -> tuple[list[ConsistencyFlag], ScenarioSynthesis, dict[SectionKey, dict[str, Any]]]:
    """LLM-free counterpart of ``synthesize_by_section`` with the same return shape.

    Returns ``(flags, scenario_synthesis, section_metrics)`` where every
    section's metrics carry ``status`` (``ok`` or ``empty``), ``model_count``,
    ``outcome_count``, ``prompt_tokens = 0`` and ``truncation_attempts = 0``.
    """
    routes = routes or load_section_routes()
    params_by_model = params_by_model or {}
    flags = list(check_consistency(scenario_id, results, consistency_config))

    section_to_ids = route_models_to_sections(_metadata_for(results), routes)
    completed = {r.model_id: r for r in results if r.status == ModelExecutionStatus.COMPLETED}
    records = _collect_regional_records(list(completed.values()))

    sections: list[ScopedSynthesis] = []
    metrics: dict[SectionKey, dict[str, Any]] = {}
    for key in all_section_keys(routes):
        ids = [m for m in section_to_ids.get(key, []) if m in completed]
        if not ids:
            sections.append(_empty_scoped_synthesis(key))
            metrics[key] = {"model_count": 0, "outcome_count": 0, "prompt_tokens": 0, "status": "empty",
                            "truncation_attempts": 0, "method": SYNTHESIS_METHOD}
            continue
        outcomes: list[SynthesizedOutcome] = []
        for mid in ids:
            r = completed[mid]
            overrides = r.outputs.get("_upstream_overrides") if isinstance(r.outputs, dict) else None
            n_over = len(overrides) if isinstance(overrides, list) else 0
            for out_key, value in select_headline_outputs(
                mid, r.outputs or {}, max_outcomes_per_model=max_outcomes_per_model,
                params=params_by_model.get(mid),
            ):
                outcomes.append(outcome_from_output(
                    mid, out_key, value, scenario_label=narrative.label,
                    implementation_mode=r.implementation_mode, n_overrides=n_over,
                ))
        sections.append(ScopedSynthesis(time_horizon=key.time_horizon, outcome_scope=key.outcome_scope, outcomes=outcomes))
        metrics[key] = {"model_count": len(ids), "outcome_count": len(outcomes), "prompt_tokens": 0, "status": "ok",
                        "truncation_attempts": 0, "method": SYNTHESIS_METHOD}

    failed = sorted({r.model_id for r in results if r.status in (ModelExecutionStatus.FAILED, ModelExecutionStatus.SKIPPED)})
    warnings = sorted({f.message for f in flags if getattr(f, "message", None)})
    synthesis = ScenarioSynthesis(
        scenario_id=scenario_id,
        scenario_label=narrative.label,
        sections=sections,
        failed_models=failed,
        consistency_warnings=warnings,
    )
    synthesis = _attach_distributional_data(synthesis, records)
    synthesis = _attach_uncertainty_to_outcomes(synthesis, list(completed.values()))
    return flags, synthesis, metrics


__all__ = [
    "CATCH_ALL_SECTION",
    "HEADLINE_KEYS",
    "SYNTHESIS_METHOD",
    "format_value",
    "infer_unit",
    "outcome_from_output",
    "select_headline_outputs",
    "templated_synthesis",
]
