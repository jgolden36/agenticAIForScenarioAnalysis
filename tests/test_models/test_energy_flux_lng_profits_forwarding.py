"""Energy Flux LNG War Profits: hub prices forwarded from LNGST.

On runs 20260504_222710 and rev_20261102_llama8b_r2 the extractor supplied
no TTF / JKM / Henry Hub prices and the model failed validation in every
scenario. The adapter now sits at COMMODITY_DOWNSTREAM and the shipped
forwarding mapping fills the three prices from LNGST's outputs.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.common.types import AnalyticalLevel, ModelExecutionStatus, Scenario
from src.models.lng.energy_flux_lng_profits import EnergyFluxLNGProfitsAdapter
from src.pipeline.state import ModelExecutionResult
from src.pipeline.upstream_forwarding import (
    clear_mapping_cache,
    compute_downstream_inputs,
    load_mapping,
    merge_into_params,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_mapping_cache()
    yield
    clear_mapping_cache()


def _lngst(scenario: str, ttf: float, jkm: float, hh: float) -> ModelExecutionResult:
    now = datetime.now(timezone.utc)
    return ModelExecutionResult(
        scenario_id=Scenario(scenario),
        model_id="lngst",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"ttf_price": ttf, "jkm_price": jkm, "henry_hub_price": hh},
        started_at=now,
        completed_at=now,
    )


def test_adapter_is_downstream_of_lngst():
    assert EnergyFluxLNGProfitsAdapter().analytical_level == AnalyticalLevel.COMMODITY_DOWNSTREAM


def test_shipped_mapping_fills_peak_prices_and_validation_passes():
    mapping = load_mapping()
    # May values for swift_contained (compare_may_..._cells.csv).
    upstream = [_lngst("swift_contained", 24.903, 28.438, 5.188)]
    computed = compute_downstream_inputs(
        "swift_contained", upstream, mapping, target_models={"energy_flux_lng_profits"}
    )
    shocks = computed["energy_flux_lng_profits"]
    assert {s.target_param for s in shocks} == {"ttf_peak_price", "jkm_peak_price", "hh_crisis_price"}

    llm_params = {"disruption_duration_months": 6}  # what the extractor gave: no prices
    adapter = EnergyFluxLNGProfitsAdapter()
    assert not adapter.validate_inputs(llm_params).valid

    merged, records = merge_into_params("energy_flux_lng_profits", llm_params, shocks)
    assert merged["ttf_peak_price"] == 24.903
    assert all(r.llm_value is None for r in records)
    assert adapter.validate_inputs(merged).valid

    out = adapter.execute(adapter.translate_inputs(merged))
    assert out.outputs["total_windfall_usd"] != 0
    assert out.outputs["_input_peak_prices"]["hh_crisis_price"] == 5.188


def test_duration_is_not_forwarded():
    mapping = load_mapping()
    rules = mapping.by_model["energy_flux_lng_profits"]
    assert "disruption_duration_months" not in {r.target_param for r in rules}


def test_peak_below_spot_start_is_clamped_and_recorded():
    adapter = EnergyFluxLNGProfitsAdapter()
    # Run A swift_contained: LNGST TTF 16.602 < workbook spot 16.98.
    params = {"ttf_peak_price": 16.602, "jkm_peak_price": 25.0, "hh_crisis_price": 4.0,
              "disruption_duration_months": 4}
    t = adapter.translate_inputs(params)
    assert t["_schedule_start_clamped"] == {"ttf": {"start": 16.98, "peak": 16.602}}
    ttf = [row.ttf for row in t["price_schedule"]]
    assert ttf[0] == 16.6 and all(abs(p - 16.6) < 0.01 for p in ttf)
    out = adapter.execute(t)
    assert "_schedule_start_clamped" in out.outputs


def test_long_disruption_is_capped_to_workbook_horizon():
    adapter = EnergyFluxLNGProfitsAdapter()
    params = {"ttf_peak_price": 40.0, "jkm_peak_price": 45.0, "hh_crisis_price": 6.0,
              "disruption_duration_months": 18}
    v = adapter.validate_inputs(params)
    assert v.valid and v.warnings
    t = adapter.translate_inputs(params)
    assert t["disruption_duration_months"] == 12
    assert t["_duration_capped_from_months"] == 18


# --- November 2026: netback is not a price; windfall net of a flat path ---


def _profits(ttf, jkm, hh, months=4, **extra):
    adapter = EnergyFluxLNGProfitsAdapter()
    params = {"ttf_peak_price": ttf, "jkm_peak_price": jkm, "hh_crisis_price": hh,
              "disruption_duration_months": months, **extra}
    return adapter.execute(adapter.translate_inputs(params)).outputs


def test_flat_path_windfall_is_reported_and_price_rise_nets_it_out():
    # Run 1, scenario B: LNGST peaks from the workbook's spot start.
    out = _profits(24.9, 28.44, 5.188)
    assert out["total_windfall_usd"] == pytest.approx(14.27e9, rel=1e-3)
    # Prices held at the workbook's March 2026 spot already beat the
    # workbook's pre-crisis cargo profit, so most of the total is not
    # the scenario's doing.
    assert out["windfall_at_flat_start_prices_usd"] > 0.5 * out["total_windfall_usd"]
    assert out["windfall_from_price_rise_usd"] == pytest.approx(
        out["total_windfall_usd"] - out["windfall_at_flat_start_prices_usd"]
    )
    assert out["windfall_from_price_rise_usd"] > 0


def test_flat_hub_prices_leave_only_the_freight_rise():
    start = {"baseline_ttf": 10.42, "baseline_jkm": 11.32, "baseline_hh": 4.25}
    out = _profits(10.42, 11.32, 4.25, **start)
    # Freight still ramps (EU 1.30 -> 2.80, Asia 1.40 -> 3.20 by month 7):
    # over 4 months sum(w) = 10/7, times 3.74m MMBtu per cargo, times
    # 75.76 EU and 56.06 Asia cargoes a month.
    freight = (1.5 * 75.7576 + 1.8 * 56.0606) * (10 / 7) * 3.74e6
    assert out["windfall_from_price_rise_usd"] == pytest.approx(-freight, rel=5e-3)
    # The raw total is far more negative: observed pre-crisis prices sit
    # below the workbook's reference margin.
    assert out["total_windfall_usd"] < -5e9


def test_price_rise_windfall_does_not_depend_on_the_reference_margin():
    a = _profits(24.9, 28.44, 5.188)
    b = _profits(24.9, 28.44, 5.188, baseline_eu_cargo_profit=0.0, baseline_asia_cargo_profit=0.0)
    assert a["total_windfall_usd"] != b["total_windfall_usd"]
    assert a["windfall_from_price_rise_usd"] == pytest.approx(b["windfall_from_price_rise_usd"])


def test_no_forwarding_rule_reads_a_netback():
    mapping = load_mapping()
    for model_id, rules in mapping.by_model.items():
        for rule in rules:
            for src in rule.sources:
                assert "netback" not in src.source_field, (model_id, rule.target_param)


def test_macro_lng_shock_is_lngst_ttf_change():
    from src.models.lng.lngst import LNGSTAdapter

    lng = LNGSTAdapter()
    params = {"qatar_export_reduction_pct": 80.0, "uae_export_reduction_pct": 50.0,
              "disruption_duration_months": 4, "spot_price_multiplier": 1.0}
    try:
        raw = lng.execute(lng.translate_inputs(params)).outputs
    except Exception as exc:  # pragma: no cover - schema drift
        pytest.skip(f"lngst inputs changed: {exc}")
    assert raw["ttf_price_change_pct"] == pytest.approx(
        (raw["ttf_price"] / raw["hub_baseline_prices"]["ttf"] - 1) * 100, abs=1e-2
    )
    now = datetime.now(timezone.utc)
    upstream = [ModelExecutionResult(
        scenario_id=Scenario("prolonged_contained"), model_id="lngst",
        status=ModelExecutionStatus.COMPLETED, outputs=raw, started_at=now, completed_at=now,
    )]
    computed = compute_downstream_inputs(
        "prolonged_contained", upstream, load_mapping(), target_models={"opencge", "pycge", "mpsge_jl"}
    )
    for model_id in ("opencge", "pycge", "mpsge_jl"):
        lng_shock = [s for s in computed[model_id] if s.target_key == "lng"]
        assert len(lng_shock) == 1
        assert lng_shock[0].value == pytest.approx(raw["ttf_price_change_pct"])
