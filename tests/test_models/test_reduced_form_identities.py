"""Document the reduced-form identities reviewers asked about."""

from __future__ import annotations

import math

from src.models.macro.macro_kernel import (
    AGGREGATE_DEFINITION,
    WORLD_GDP_SHARES_PPP,
    compute_macro_outcomes,
    world_weighted_aggregate,
)
from src.models.oil.fed_oil import FedOilAdapter


def _fed_oil_outputs(oil_pct: float = 58.25, shock_type: str = "supply") -> dict:
    adapter = FedOilAdapter()
    params = {
        "oil_price_change_pct": oil_pct,
        "shock_type": shock_type,
        "disruption_duration_quarters": 2.0,
        "fed_funds_rate_baseline": 4.5,
    }
    assert adapter.validate_inputs(params).valid
    return adapter.execute(adapter.translate_inputs(params)).outputs


def test_fed_oil_peak_cpi_is_twice_peak_ffr_by_construction():
    out = _fed_oil_outputs()
    assert math.isclose(out["peak_cpi_impact_pp"], 2.0 * out["peak_ffr_impact_pp"], rel_tol=1e-3)


def test_fed_oil_peak_unemployment_is_half_peak_gdp_loss_by_construction():
    out = _fed_oil_outputs()
    assert math.isclose(out["peak_unemployment_impact_pp"], 0.5 * abs(out["peak_gdp_impact_pct"]), rel_tol=1e-3)


def test_fed_oil_outputs_state_the_identities():
    out = _fed_oil_outputs()
    eqs = out["_reduced_form_equations"]
    assert any("peak_cpi_impact_pp = 2" in e for e in eqs)
    assert any("peak_unemployment_impact_pp = 0.5" in e for e in eqs)
    assert "not run" in out["_implementation_note"]
    assert "Federal Reserve" in FedOilAdapter().description


def test_world_weighted_aggregate_and_definition():
    assert math.isclose(sum(WORLD_GDP_SHARES_PPP.values()), 100.0, abs_tol=0.5)
    # Only oil/LNG shocks: headline equals the ROW row (multiplier 1.0 on both).
    out = compute_macro_outcomes({"oil": 54.79, "lng": 25.0}, 4.0)
    row = {r["region"]: r for r in out["regional_vars"]}["ROW"]
    assert math.isclose(out["gdp_impact_pct"], row["gdp_impact_pct"], abs_tol=1e-4)
    assert out["_aggregate_definition"] == AGGREGATE_DEFINITION
    ww = out["gdp_impact_pct_world_weighted"]
    assert ww is not None and ww != out["gdp_impact_pct"]
    assert ww == world_weighted_aggregate(out["regional_vars"], "gdp_impact_pct")
    # A helium shock breaks the headline == ROW coincidence (ROW multiplier 0.5).
    out2 = compute_macro_outcomes({"oil": 54.79, "helium": 30.0}, 4.0)
    row2 = {r["region"]: r for r in out2["regional_vars"]}["ROW"]
    assert not math.isclose(out2["gdp_impact_pct"], row2["gdp_impact_pct"], abs_tol=1e-6)


def test_world_weighted_aggregate_handles_partial_tables():
    rows = [{"region": "US", "gdp_impact_pct": -1.0}, {"region": "CHN", "gdp_impact_pct": -2.0}]
    ww = world_weighted_aggregate(rows, "gdp_impact_pct")
    expected = (-1.0 * 15.0 + -2.0 * 18.7) / (15.0 + 18.7)
    assert math.isclose(ww, expected, abs_tol=1e-4)
    assert world_weighted_aggregate([], "gdp_impact_pct") is None
