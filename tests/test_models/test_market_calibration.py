"""Observed-market calibration (src/models/market_calibration.py).

Default runs must be unchanged (calibration off); with calibration on the
closed-form adapters take observed pre-crisis baselines and estimated
half-lives, and record where they came from.
"""

from __future__ import annotations

import json
import math
import random

import pytest

from src.models import market_calibration as mc
from src.models.fertilizer.futures import FuturesAdapter
from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter
from src.models.lng.energy_flux_lng_profits import EnergyFluxLNGProfitsAdapter
from src.models.lng.lngst import LNGSTAdapter
from src.models.oil.poles_jrc import POLESJRCAdapter


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    for k in ("HORMUZ_MARKET_CALIBRATION", "HORMUZ_MARKET_CALIBRATION_FILE",
              "HORMUZ_MARKET_CALIBRATION_HALF_LIVES"):
        monkeypatch.delenv(k, raising=False)
    mc.clear_cache()
    yield
    mc.clear_cache()


def _months(start_year: int, n: int) -> list[str]:
    return [f"{start_year + i // 12:04d}-{i % 12 + 1:02d}" for i in range(n)]


def _calibration_file(tmp_path, monkeypatch):
    doc = {
        "retrieved_at": "2026-11-08T00:00:00+00:00",
        "source": "test",
        "pre_crisis_window": ["2025-11", "2026-01"],
        "half_life_window": ["2000-01", "2025-12"],
        "baselines": {
            "brent": {"value": 64.0}, "henry_hub": {"value": 5.0}, "ttf": {"value": 10.0},
            "lng_japan": {"value": 11.0}, "urea": {"value": 400.0}, "dap": {"value": 650.0},
            "potash": {"value": 360.0},
        },
        "half_lives": {
            "wheat": {"half_life_months": 20.0, "half_life_se_months": 3.0},
            "urea": {"half_life_months": 10.0, "half_life_se_months": 2.0},
            "dap": {"half_life_months": 22.0, "half_life_se_months": 4.0},
            "potash": {"half_life_months": 24.0, "half_life_se_months": 5.0},
        },
    }
    p = tmp_path / "calibration.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION_FILE", str(p))
    return p


POLES = {"supply_loss_mbd": 10.0, "disruption_duration_months": 3, "rerouting_cost_multiplier": 1.2,
         "insurance_premium_increase_pct": 50.0, "substitute_energy_availability": 0.2}
LNGST = {"qatar_export_reduction_pct": 80.0, "uae_export_reduction_pct": 50.0,
         "spot_price_multiplier": 1.5, "disruption_duration_months": 3}
FUT = {"initial_price_shock_pct": 40.0, "commodities": ["wheat", "palm_oil"], "forecast_horizon_months": 12}
FERT = {"natural_gas_price_change_pct": 60.0, "middle_east_production_loss_pct": 30.0,
        "disruption_duration_months": 6}


def _run(adapter, params):
    return adapter.execute(adapter.translate_inputs(params)).outputs


def test_off_by_default_outputs_unchanged():
    assert mc.active_calibration() is None
    out = _run(POLESJRCAdapter(), POLES)
    assert out["baseline_price_usd_per_bbl"] == 80.0 and "_calibration" not in out
    assert _run(LNGSTAdapter(), LNGST)["hub_baseline_prices"]["ttf"] == 11.0
    assert "_calibration" not in _run(FuturesAdapter(), FUT)
    assert "baseline_price_usd_per_t" not in _run(WorldFertilizerAdapter(), FERT)


def test_enabled_without_file_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION", "1")
    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION_FILE", str(tmp_path / "missing.json"))
    with pytest.raises(FileNotFoundError):
        mc.active_calibration()


def test_enabled_applies_observed_baselines(tmp_path, monkeypatch):
    _calibration_file(tmp_path, monkeypatch)
    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION", "1")
    poles = _run(POLESJRCAdapter(), POLES)
    assert poles["baseline_price_usd_per_bbl"] == 64.0
    assert poles["brent_price_path_usd_per_bbl"][-1] == 64.0
    assert poles["_calibration"]["source"] == "market_data@2026-11-08"

    lng = _run(LNGSTAdapter(), LNGST)
    assert lng["hub_baseline_prices"] == {"henry_hub": 5.0, "ttf": 10.0, "jkm": 11.0}

    ef = EnergyFluxLNGProfitsAdapter()
    t = ef.translate_inputs({"ttf_peak_price": lng["ttf_price"], "jkm_peak_price": lng["jkm_price"],
                             "hh_crisis_price": lng["henry_hub_price"], "disruption_duration_months": 3})
    # Same starting prices as LNGST, so no schedule inversion.
    assert "_schedule_start_clamped" not in t
    assert ef.execute(t).outputs["_calibration"]["values_used"]["schedule_start"]["ttf"] == 10.0

    fert = _run(WorldFertilizerAdapter(), FERT)
    assert fert["baseline_price_usd_per_t"]["mop"] == 360.0
    assert fert["peak_price_usd_per_t"]["urea"] == pytest.approx(400.0 * (1 + fert["price_urea_pct"] / 100), abs=0.01)


def test_half_lives_switch(tmp_path, monkeypatch):
    _calibration_file(tmp_path, monkeypatch)
    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION", "1")
    # Off by default (configs/model_configs/default.yaml).
    assert _run(FuturesAdapter(), FUT)["_calibration"]["values_used"]["half_lives_months"]["wheat"] == 4.0
    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION_HALF_LIVES", "1")
    mc.clear_cache()
    out = _run(FuturesAdapter(), FUT)
    assert out["_calibration"]["values_used"]["half_lives_months"] == {"wheat": 20.0, "palm_oil": 4.0}
    assert out["_calibration"]["values_used"]["half_life_source"]["palm_oil"] == "literature"

    monkeypatch.setenv("HORMUZ_MARKET_CALIBRATION_HALF_LIVES", "0")
    mc.clear_cache()
    out = _run(FuturesAdapter(), FUT)
    assert out["_calibration"]["values_used"]["half_lives_months"]["wheat"] == 4.0
    # Baselines still apply with half-lives off.
    assert _run(POLESJRCAdapter(), POLES)["baseline_price_usd_per_bbl"] == 64.0


def test_ar1_half_life_recovers_known_persistence():
    rng = random.Random(7)
    rho = 0.9
    level, d = math.log(100.0), 0.0
    pts = []
    for m in _months(1990, 432):
        d = rho * d + rng.gauss(0, 0.05)
        pts.append((m, math.exp(level + d)))
    est = mc.estimate_ar1_half_life(pts, "1995-01", "2025-12", ma_months=36)
    true_hl = math.log(0.5) / math.log(rho)
    assert est["n"] > 300
    # The trailing-mean detrending biases rho up a little; stay within 3 SE.
    assert abs(est["half_life_months"] - true_hl) < 3 * est["half_life_se_months"] + 1.0


def test_build_calibration_windows():
    pts = [(m, 50.0 + i) for i, m in enumerate(_months(2024, 30))]
    doc = mc.build_calibration({"brent": pts}, retrieved_at="2026-11-08T00:00:00+00:00", source="t")
    b = doc["baselines"]["brent"]
    assert b["months"] == ["2025-11", "2025-12", "2026-01"]
    assert b["value"] == 73.0  # median of 72, 73, 74
    assert b["mean"] == pytest.approx(73.0)


def test_median_baseline_resists_one_outlier_month():
    pts = [("2025-11", 3.8), ("2025-12", 4.2), ("2026-01", 7.6)]
    assert mc.window_median(pts, "2025-11", "2026-01") == 4.2
