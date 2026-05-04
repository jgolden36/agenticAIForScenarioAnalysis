"""Tests for the analytical-MVP execute() paths added so each commodity
system in the SLURM-driven pipeline has at least one runnable model.

The four adapters covered here previously raised ``NotImplementedError``
in ``execute()``. Each now implements a closed-form computation:

  * POLES-JRC          -> oil price impulse via constant-elasticity equilibrium
  * World Helium Model -> helium market equilibrium with Qatar share
  * Futures            -> AR(1) mean-reversion forward curves
  * CWatM              -> analytical fallback when no CWatMConfig is provided

Each adapter is exercised against the four canonical Hormuz scenarios
(Swift Contained, Prolonged Contained, Swift Escalated, Prolonged
Escalated) so we know the MVP pipeline gets a populated ``ModelOutput``
for every (commodity_system, scenario) pair.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelOutput
from src.models.fertilizer.futures import FuturesAdapter
from src.models.helium.world_helium_model import WorldHeliumModelAdapter
from src.models.oil.poles_jrc import POLESJRCAdapter
from src.models.water.cwatm import CWatMAdapter


# ---------------------------------------------------------------------------
# Canonical Hormuz scenario parameter sets
# ---------------------------------------------------------------------------

POLES_PARAMS: dict[str, dict[str, Any]] = {
    "swift_contained": {
        "supply_loss_mbd": 18.0,
        "disruption_duration_months": 1.5,
        "rerouting_cost_multiplier": 1.2,
        "insurance_premium_increase_pct": 50.0,
        "substitute_energy_availability": 0.4,
    },
    "prolonged_contained": {
        "supply_loss_mbd": 18.0,
        "disruption_duration_months": 5.0,
        "rerouting_cost_multiplier": 1.4,
        "insurance_premium_increase_pct": 100.0,
        "substitute_energy_availability": 0.3,
    },
    "swift_escalated": {
        "supply_loss_mbd": 21.0,
        "disruption_duration_months": 2.0,
        "rerouting_cost_multiplier": 1.5,
        "insurance_premium_increase_pct": 200.0,
        "substitute_energy_availability": 0.2,
    },
    "prolonged_escalated": {
        "supply_loss_mbd": 23.0,
        "disruption_duration_months": 6.0,
        "rerouting_cost_multiplier": 1.6,
        "insurance_premium_increase_pct": 250.0,
        "substitute_energy_availability": 0.15,
    },
}

HELIUM_PARAMS: dict[str, dict[str, Any]] = {
    "swift_contained": {
        "qatar_helium_supply_loss_pct": 60.0,
        "disruption_duration_months": 1.5,
        # Modest BLM Cliffside-style drawdown; not enough to fully
        # offset Qatar at ~30% global share for 1.5 months.
        "strategic_reserve_release": 50.0,
    },
    "prolonged_contained": {
        "qatar_helium_supply_loss_pct": 80.0,
        "disruption_duration_months": 5.0,
        "strategic_reserve_release": 150.0,
    },
    "swift_escalated": {
        "qatar_helium_supply_loss_pct": 95.0,
        "disruption_duration_months": 2.0,
        "strategic_reserve_release": 75.0,
    },
    "prolonged_escalated": {
        "qatar_helium_supply_loss_pct": 100.0,
        "disruption_duration_months": 6.0,
        "strategic_reserve_release": 200.0,
    },
}

FUTURES_PARAMS: dict[str, dict[str, Any]] = {
    "swift_contained": {
        "initial_price_shock_pct": 25.0,
        "commodities": ["wheat", "urea", "natural_gas"],
        "forecast_horizon_months": 12,
    },
    "prolonged_contained": {
        "initial_price_shock_pct": 45.0,
        "commodities": ["wheat", "urea", "potash", "ammonia"],
        "forecast_horizon_months": 18,
    },
    "swift_escalated": {
        "initial_price_shock_pct": 60.0,
        "commodities": ["wheat", "corn", "soybeans", "urea"],
        "forecast_horizon_months": 12,
    },
    "prolonged_escalated": {
        "initial_price_shock_pct": 100.0,
        "commodities": ["wheat", "rice", "urea", "ammonia", "dap", "potash"],
        "forecast_horizon_months": 24,
    },
}

CWATM_PARAMS: dict[str, dict[str, Any]] = {
    "swift_contained": {
        "scenario_id": "swift_contained",
        "water_demand_change_pct": 5.0,
        "supply_infrastructure_status": "intact",
        "disruption_duration_months": 1.5,
    },
    "prolonged_contained": {
        "scenario_id": "prolonged_contained",
        "water_demand_change_pct": 10.0,
        "supply_infrastructure_status": "partially_damaged",
        "disruption_duration_months": 5.0,
    },
    "swift_escalated": {
        "scenario_id": "swift_escalated",
        "water_demand_change_pct": 15.0,
        "supply_infrastructure_status": "severely_damaged",
        "disruption_duration_months": 2.0,
    },
    "prolonged_escalated": {
        "scenario_id": "prolonged_escalated",
        "water_demand_change_pct": 20.0,
        "supply_infrastructure_status": "destroyed",
        "disruption_duration_months": 6.0,
    },
}

SCENARIOS: tuple[str, ...] = (
    "swift_contained",
    "prolonged_contained",
    "swift_escalated",
    "prolonged_escalated",
)


# ---------------------------------------------------------------------------
# POLES-JRC analytical-MVP execute()
# ---------------------------------------------------------------------------

class TestPOLESJRCAnalytical:
    def test_metadata(self) -> None:
        adapter = POLESJRCAdapter()
        assert adapter.model_id == "poles_jrc"
        assert adapter.commodity_system == CommoditySystem.OIL
        assert adapter.analytical_level == AnalyticalLevel.COMMODITY

    def test_relaxed_supply_loss_bound_accepts_21_mbd(self) -> None:
        adapter = POLESJRCAdapter()
        params = dict(POLES_PARAMS["swift_escalated"])
        result = adapter.validate_inputs(params)
        assert result.valid, result.errors

    def test_supply_loss_above_25_is_rejected(self) -> None:
        adapter = POLESJRCAdapter()
        params = dict(POLES_PARAMS["swift_escalated"], supply_loss_mbd=30.0)
        result = adapter.validate_inputs(params)
        assert not result.valid
        assert any("supply_loss_mbd" in e for e in result.errors)

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_execute_returns_populated_output(self, scenario: str) -> None:
        adapter = POLESJRCAdapter()
        params = POLES_PARAMS[scenario]
        validation = adapter.validate_inputs(params)
        assert validation.valid, validation.errors

        translated = adapter.translate_inputs(params)
        out = adapter.execute(translated)

        assert isinstance(out, ModelOutput)
        assert out.metadata.get("mode") == "analytical_mvp"
        assert out.convergence_status == "converged"

        outputs = out.outputs
        path = outputs["brent_price_path_usd_per_bbl"]
        assert isinstance(path, list) and len(path) >= 12
        assert all(isinstance(p, float) for p in path)
        assert outputs["peak_price_usd_per_bbl"] > outputs["baseline_price_usd_per_bbl"]
        # Price decays back to (or close to) baseline by the end of the horizon
        assert path[-1] == pytest.approx(outputs["baseline_price_usd_per_bbl"], rel=0.01)
        # Peak change is positive when supply is reduced
        assert outputs["peak_price_change_pct"] > 0

    def test_larger_shock_yields_higher_peak(self) -> None:
        adapter = POLESJRCAdapter()
        small = adapter.execute(adapter.translate_inputs(POLES_PARAMS["swift_contained"]))
        large = adapter.execute(adapter.translate_inputs(POLES_PARAMS["prolonged_escalated"]))
        assert large.outputs["peak_price_usd_per_bbl"] > small.outputs["peak_price_usd_per_bbl"]

    def test_zero_substitute_amplifies_response(self) -> None:
        adapter = POLESJRCAdapter()
        base = dict(POLES_PARAMS["swift_contained"])
        with_substitution = adapter.execute(adapter.translate_inputs(base))
        no_substitution = adapter.execute(
            adapter.translate_inputs(dict(base, substitute_energy_availability=0.0))
        )
        assert (
            no_substitution.outputs["peak_price_usd_per_bbl"]
            > with_substitution.outputs["peak_price_usd_per_bbl"]
        )


# ---------------------------------------------------------------------------
# World Helium Model analytical-MVP execute()
# ---------------------------------------------------------------------------

class TestWorldHeliumAnalytical:
    def test_metadata(self) -> None:
        adapter = WorldHeliumModelAdapter()
        assert adapter.model_id == "world_helium_model"
        assert adapter.commodity_system == CommoditySystem.HELIUM_SEMICONDUCTORS
        assert adapter.analytical_level == AnalyticalLevel.COMMODITY

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_execute_returns_populated_output(self, scenario: str) -> None:
        adapter = WorldHeliumModelAdapter()
        params = HELIUM_PARAMS[scenario]
        validation = adapter.validate_inputs(params)
        assert validation.valid, validation.errors

        translated = adapter.translate_inputs(params)
        out = adapter.execute(translated)

        assert isinstance(out, ModelOutput)
        assert out.metadata.get("mode") == "analytical_mvp"
        assert out.convergence_status == "converged"

        outputs = out.outputs
        assert outputs["equilibrium_price_usd_per_mscf"] > outputs["baseline_price_usd_per_mscf"]
        assert outputs["price_change_pct"] >= 0
        assert 0.0 <= outputs["effective_supply_gap_pct"] <= 100.0
        assert isinstance(outputs["sector_allocation_share"], dict)
        assert set(outputs["sector_allocation_share"]) == {
            "mri_medical",
            "semiconductors",
            "cryogenics_research",
            "aerospace_defense",
            "other",
        }

    def test_reserve_release_dampens_price(self) -> None:
        adapter = WorldHeliumModelAdapter()
        base = dict(HELIUM_PARAMS["prolonged_contained"])
        no_release = adapter.execute(
            adapter.translate_inputs(dict(base, strategic_reserve_release=0.0))
        )
        with_release = adapter.execute(
            adapter.translate_inputs(dict(base, strategic_reserve_release=2_000.0))
        )
        assert (
            with_release.outputs["equilibrium_price_usd_per_mscf"]
            <= no_release.outputs["equilibrium_price_usd_per_mscf"]
        )


# ---------------------------------------------------------------------------
# Futures analytical-MVP execute()
# ---------------------------------------------------------------------------

class TestFuturesAnalytical:
    def test_metadata(self) -> None:
        adapter = FuturesAdapter()
        assert adapter.model_id == "futures"
        assert adapter.commodity_system == CommoditySystem.FERTILIZER_AGRICULTURE
        assert adapter.analytical_level == AnalyticalLevel.COMMODITY

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_execute_returns_curves(self, scenario: str) -> None:
        adapter = FuturesAdapter()
        params = FUTURES_PARAMS[scenario]
        validation = adapter.validate_inputs(params)
        assert validation.valid, validation.errors

        translated = adapter.translate_inputs(params)
        out = adapter.execute(translated)

        assert isinstance(out, ModelOutput)
        assert out.metadata.get("mode") == "analytical_mvp"

        curves = out.outputs["forward_price_curves"]
        assert set(curves) == set(params["commodities"])
        for commodity, curve in curves.items():
            assert len(curve) == int(math.ceil(params["forecast_horizon_months"]))
            assert curve[0] == pytest.approx(
                1.0 + params["initial_price_shock_pct"] / 100.0, rel=1e-3
            )
            # Prices monotonically decay back toward baseline (=1.0)
            for prev, nxt in zip(curve[:-1], curve[1:]):
                assert nxt <= prev + 1e-9

    def test_time_to_normalisation_increases_with_shock(self) -> None:
        adapter = FuturesAdapter()
        small = adapter.execute(adapter.translate_inputs(FUTURES_PARAMS["swift_contained"]))
        large = adapter.execute(adapter.translate_inputs(FUTURES_PARAMS["prolonged_escalated"]))
        # Compare wheat across both runs (present in both lists)
        small_t = small.outputs["time_to_normalization_months_per_commodity"]["wheat"]
        large_t = large.outputs["time_to_normalization_months_per_commodity"]["wheat"]
        assert (small_t or 0) <= (large_t or 0)


# ---------------------------------------------------------------------------
# CWatM analytical-MVP fallback (when no CWatMConfig is supplied)
# ---------------------------------------------------------------------------

class TestCWatMAnalyticalFallback:
    def test_metadata(self) -> None:
        adapter = CWatMAdapter()
        assert adapter.model_id == "cwatm"
        assert adapter.commodity_system == CommoditySystem.WATER
        assert adapter.analytical_level == AnalyticalLevel.COMMODITY

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_execute_without_config_returns_real_output(self, scenario: str) -> None:
        adapter = CWatMAdapter()  # no CWatMConfig => analytical fallback
        params = CWATM_PARAMS[scenario]
        validation = adapter.validate_inputs(params)
        assert validation.valid, validation.errors

        translated = adapter.translate_inputs(params)
        out = adapter.execute(translated)

        assert isinstance(out, ModelOutput)
        assert out.metadata.get("mode") == "analytical_mvp"
        assert out.convergence_status == "converged"

        outputs = out.outputs
        assert outputs["scenario_id"] == scenario
        assert outputs["unmet_demand_pct"] >= 0.0
        assert outputs["mean_discharge_deviation_pct"] <= 0.0  # deficit, not surplus
        assert outputs["disruption_duration_months"] == params["disruption_duration_months"]

    def test_destroyed_infrastructure_yields_max_unmet_demand(self) -> None:
        adapter = CWatMAdapter()
        out = adapter.execute(adapter.translate_inputs(CWATM_PARAMS["prolonged_escalated"]))
        # demand_factor = 1.20, infra_factor = 0 => unmet = 100%
        assert out.outputs["unmet_demand_pct"] == pytest.approx(100.0, abs=0.01)
        assert out.outputs["mean_discharge_deviation_pct"] == pytest.approx(-50.0, abs=0.01)

    def test_intact_infrastructure_with_modest_demand_increase(self) -> None:
        adapter = CWatMAdapter()
        out = adapter.execute(adapter.translate_inputs(CWATM_PARAMS["swift_contained"]))
        # demand_factor = 1.05, infra_factor = 1.0 => unmet ~ 4.76%
        assert out.outputs["unmet_demand_pct"] == pytest.approx(
            (1.05 - 1.0) / 1.05 * 100.0, abs=0.01
        )
        assert out.outputs["mean_discharge_deviation_pct"] == pytest.approx(0.0, abs=0.01)
