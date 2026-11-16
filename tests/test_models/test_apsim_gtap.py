"""APSIM-GTAP adapter and driver (no Julia, no torch: GTAP and the crop model are faked)."""

from __future__ import annotations

import pytest

from src.common.types import AnalyticalLevel
from src.models.fertilizer import apsim_gtap_driver as drv
from src.models.fertilizer.apsim_gtap import (
    APSIMGTAPAdapter,
    APSIMGTAPConfig,
    annualisation_factor,
    compute_shocks,
    config_from_mapping,
)
from src.models.registry import build_default_registry

PARAMS = {
    "middle_east_fertilizer_production_loss_pct": 60.0,
    "gulf_oil_supply_loss_mbd": 14.0,
    "trade_cost_multiplier": 1.5,
    "disruption_duration_months": 6.0,
}


def _cfg(tmp_path, **kw):
    return APSIMGTAPConfig(agres_root=tmp_path, **kw)


# ------------------------------------------------------------------ adapter

def test_metadata_and_tier():
    a = APSIMGTAPAdapter()
    assert a.model_id == "apsim_gtap"
    assert a.analytical_level == AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC
    assert a.resource_requirements.prefers_process_isolation


def test_validation_accepts_baseline_and_rejects_bad_values():
    a = APSIMGTAPAdapter()
    assert a.validate_inputs(PARAMS).valid
    bad = {**PARAMS, "middle_east_fertilizer_production_loss_pct": 120.0, "trade_cost_multiplier": 0.9}
    res = a.validate_inputs(bad)
    assert not res.valid and len(res.errors) == 2
    missing = {k: v for k, v in PARAMS.items() if k != "gulf_oil_supply_loss_mbd"}
    assert any("gulf_oil_supply_loss_mbd" in e for e in a.validate_inputs(missing).errors)
    assert a.validate_inputs({**PARAMS, "disruption_duration_months": 18.0}).warnings
    assert not a.validate_inputs({**PARAMS, "gulf_oil_supply_loss_mbd": True}).valid


def test_annualisation_and_shock_magnitudes(tmp_path):
    assert annualisation_factor(6) == 0.5
    assert annualisation_factor(24) == 1.0
    s = compute_shocks(PARAMS, _cfg(tmp_path))
    assert s["annualisation_factor"] == 0.5
    assert s["chm_output_loss_share"] == pytest.approx(0.30)
    assert s["extract_output_loss_share"] == pytest.approx(14.0 / 28.0 * 0.5)
    assert s["trade_wedge"] == pytest.approx(1 + 0.5 * 0.08 * 0.5)


def test_wedge_off_and_loss_cap(tmp_path):
    s = compute_shocks({**PARAMS, "gulf_oil_supply_loss_mbd": 29.0, "disruption_duration_months": 12},
                       _cfg(tmp_path, apply_trade_wedge=False))
    assert s["trade_wedge"] == 1.0
    assert s["extract_output_loss_share"] == pytest.approx(0.95)


def test_execute_without_config_is_skippable():
    a = APSIMGTAPAdapter()
    with pytest.raises(NotImplementedError):
        a.execute(a.translate_inputs({**PARAMS, "scenario_id": "swift_contained"}))


def test_translate_payload(tmp_path):
    a = APSIMGTAPAdapter(_cfg(tmp_path, calib_id="x"))
    payload = a.translate_inputs({**PARAMS, "scenario_id": "swift_contained", "coupling_elasticity": 0.5})
    assert payload["scenario_id"] == "swift_contained"
    assert payload["coupling_elasticity"] == 0.5
    assert payload["config"]["calib_id"] == "x"
    assert "gtap_parameter_edits" not in payload


def test_parse_outputs_marks_mode_and_disables_perturbation():
    out = APSIMGTAPAdapter().parse_outputs({"converged": True, "us_gdp_pct": -0.01, "zero_shock_gate_passed": True})
    assert out.metadata["mode"] == "julia"
    assert out.convergence_status == "converged"
    assert out.uncertainty is not None and out.uncertainty.method == "none"


def test_config_from_mapping_env_override(monkeypatch, tmp_path):
    assert config_from_mapping({}) is None
    monkeypatch.setenv("HORMUZ_APSIM_GTAP_ROOT", str(tmp_path))
    cfg = config_from_mapping({"wasia_baseline_oil_mbd": 30.0, "unknown_key": 1})
    assert cfg is not None and cfg.agres_root == tmp_path and cfg.wasia_baseline_oil_mbd == 30.0


def test_registry_without_config_is_unconfigured(monkeypatch):
    monkeypatch.delenv("HORMUZ_APSIM_GTAP_ROOT", raising=False)
    reg = build_default_registry(None)
    adapter = reg.get("apsim_gtap")
    assert isinstance(adapter, APSIMGTAPAdapter) and adapter.agres_config is None


# ------------------------------------------------------------------ driver

def test_shock_instructions_use_wasia_and_wedge():
    shocks = {"chm_output_loss_share": 0.3, "extract_output_loss_share": 0.25, "trade_wedge": 1.02}
    regions = ["usa", "wasia", "eu"]
    apply = drv.shock_instructions(shocks, regions)
    prod = [i for i in apply if i["variable"] == "production_shock"]
    assert {(i["indices"]["commodity"], i["indices"]["region"]) for i in prod} == {("chm", "wasia"), ("extract", "wasia")}
    assert prod[0]["value"] == pytest.approx(0.7)
    tms = [i for i in apply if i["variable"] == "tms"]
    assert len(tms) == 4  # 2 commodities x 2 non-Gulf destinations
    assert all(i["indices"]["region_from"] == "wasia" and i["indices"]["region_to"] != "wasia" for i in tms)
    assert drv.shock_instructions({**shocks, "trade_wedge": 1.0}, None) == prod
    with pytest.raises(ValueError):
        drv.shock_instructions(shocks, None)


def test_make_request_adds_grain_productivity_only_when_moved():
    assert all(i["indices"].get("commodity") != "gro" for i in drv.make_request([], 1.0)["apply"])
    req = drv.make_request([], 0.97, parameters=[{"name": "esubm"}])
    assert req["apply"][-1]["indices"] == {"commodity": "gro", "region": "usa"}
    assert req["parameters"] == [{"name": "esubm"}]


def _fake_gtap():
    """Linear fake: US chm consumption falls with the Gulf chm loss; grain
    productivity below 1 raises the grain price."""
    calls = []

    def solve(req):
        calls.append(req)
        chm_loss = 0.0
        prod = 1.0
        for i in req["apply"]:
            if i["variable"] == "production_shock" and i["indices"]["commodity"] == "chm":
                chm_loss = 1.0 - i["value"]
            if i["variable"] == "production_shock" and i["indices"]["commodity"] == "gro":
                prod = i["value"]
        return {"regions": ["usa", "wasia"], "commodities": ["gro", "chm"],
                "gdp": {"usa": -0.1 * chm_loss, "wasia": -5 * chm_loss},
                "cons_chm_usa": -10.0 * chm_loss, "gro_price": -50.0 * (prod - 1.0)}

    def extract(result, variable, region="usa", commodity="chm"):
        if variable == "gdp_change":
            return result["gdp"].get(region)
        if variable == "consumption_change" and commodity == "chm":
            return result["cons_chm_usa"] if region == "usa" else 0.0
        if variable == "price_change" and commodity == "gro":
            return result["gro_price"] if region == "usa" else 0.0
        return 0.0

    return solve, extract, calls


def test_fixed_point_converges_and_reports_open_loop_gap():
    solve, extract, calls = _fake_gtap()
    yield_at = lambda n: 0.5 + n / 380.0  # noqa: E731 — yield ratio 1 at N=190

    def to_n(chm_pct, n0, eps):
        return n0 * (1 + eps * chm_pct / 100.0)

    base = drv.shock_instructions({"chm_output_loss_share": 0.3}, ["usa", "wasia"])
    fp = drv.run_fixed_point(solve, extract, yield_at, to_n, base, 190.0)
    assert fp["converged"] and fp["iterations"] >= 2
    # N falls 3% -> yield ratio 1 - 0.015; the fixed point feeds it back as a
    # grain productivity shock, so the grain price rises only after pass 1.
    assert fp["arm_a"]["yield_change_pct"] == pytest.approx(-1.5)
    assert fp["arm_a"]["us_gro_price_pct"] == pytest.approx(0.0)
    assert fp["arm_c"]["us_gro_price_pct"] == pytest.approx(0.75)
    assert fp["open_loop_gap"]["us_gro_price_pct"] == pytest.approx(0.75)
    zero = solve(drv.make_request([], 1.0))
    out = drv.assemble_outputs(fp, zero, 190.0, extract)
    assert out["zero_shock_gate_passed"] and out["zero_shock_residual_gdp_pct"] == 0.0
    assert out["us_nitrogen_change_pct"] == pytest.approx(-3.0)
    assert set(out["gdp_change_by_region"]) == {"usa", "wasia"}


def test_fixed_point_rejects_missing_consumption():
    def solve(req):
        return {"regions": ["usa"]}

    with pytest.raises(ValueError):
        drv.run_fixed_point(solve, lambda *a, **k: None, lambda n: 1.0,
                            lambda c, n0, e: n0, [], 190.0)
