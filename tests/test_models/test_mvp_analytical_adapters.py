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


# ===========================================================================
# Additional analytical-MVP adapters (11 stubs converted)
# ===========================================================================
#
# Each adapter previously raised ``NotImplementedError`` from execute();
# the MVP path lets it return a populated ModelOutput without external
# binaries, licenses, or upstream code. Tests verify standard MVP
# metadata + a small set of structural invariants per adapter.


def _assert_mvp_metadata(out: ModelOutput) -> None:
    assert isinstance(out, ModelOutput)
    assert out.convergence_status == "converged"
    assert out.metadata.get("mode") == "analytical_mvp"
    cs = out.metadata.get("calibration_source")
    assert isinstance(cs, str) and len(cs) > 0


def _assert_finite_number(value: Any) -> None:
    assert isinstance(value, (int, float))
    assert math.isfinite(float(value))


# --- SHIPPING tier ---------------------------------------------------------

class TestAISDBAnalytical:
    def test_closed_strait_via_cape_produces_positive_cost_and_premium(self) -> None:
        from src.models.shipping.aisdb import AISDBAdapter

        out = AISDBAdapter().execute({
            "strait_closure_flag": True,
            "alternative_routes": ["cape_of_good_hope"],
            "vessel_types": ["tanker", "lng_carrier"],
        })
        _assert_mvp_metadata(out)
        for key in (
            "rerouting_cost_multiplier",
            "effective_fleet_capacity_loss_pct",
            "war_risk_insurance_premium_pct",
            "max_additional_transit_days",
        ):
            assert key in out.outputs
            _assert_finite_number(out.outputs[key])
        assert out.outputs["rerouting_cost_multiplier"] > 1.0
        assert out.outputs["war_risk_insurance_premium_pct"] > 0.0

    def test_open_strait_yields_baseline_cost_and_zero_premium(self) -> None:
        from src.models.shipping.aisdb import AISDBAdapter

        out = AISDBAdapter().execute({
            "strait_closure_flag": False,
            "alternative_routes": ["none"],
            "vessel_types": ["tanker"],
        })
        _assert_mvp_metadata(out)
        assert out.outputs["rerouting_cost_multiplier"] == pytest.approx(1.0)
        assert out.outputs["war_risk_insurance_premium_pct"] == pytest.approx(0.0)


class TestAISProjectAnalytical:
    def test_cape_rerouting_lifts_tanker_rates(self) -> None:
        from src.models.shipping.ais_project import AISProjectAdapter

        out = AISProjectAdapter().execute({
            "strait_closure_flag": True,
            "rerouting_via_cape": True,
            "fleet_size_change_pct": 0.0,
            "disruption_duration_months": 6.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "rerouting_cost_multiplier",
            "tanker_rate_change_pct",
            "fleet_utilization_multiplier",
            "voyage_days_lost_per_baseline_voyage",
        ):
            assert key in out.outputs
            _assert_finite_number(out.outputs[key])
        assert out.outputs["rerouting_cost_multiplier"] > 1.0
        assert out.outputs["tanker_rate_change_pct"] > 0.0


# --- OIL tier --------------------------------------------------------------

class TestFedOilAnalytical:
    def test_supply_shock_contracts_gdp_and_lifts_cpi(self) -> None:
        from src.models.oil.fed_oil import FedOilAdapter

        out = FedOilAdapter().execute({
            "oil_price_change_pct": 50.0,
            "shock_type": "supply",
            "disruption_duration_quarters": 2.0,
            "fed_funds_rate_baseline": 4.5,
        })
        _assert_mvp_metadata(out)
        assert out.outputs["peak_gdp_impact_pct"] < 0.0
        assert out.outputs["peak_cpi_impact_pp"] > 0.0
        horizon = out.outputs["horizon_quarters"]
        assert len(out.outputs["gdp_irf_pct_quarterly"]) == horizon
        assert len(out.outputs["cpi_irf_pp_quarterly"]) == horizon
        # FEVD share is in (0, 1)
        assert 0.0 < out.outputs["fevd_oil_share"] < 1.0

    def test_demand_shock_smaller_than_supply_shock(self) -> None:
        """Baumeister-Hamilton (2019): demand shocks should produce smaller
        GDP / CPI impacts than supply shocks of equal magnitude."""
        from src.models.oil.fed_oil import FedOilAdapter

        base = {
            "oil_price_change_pct": 50.0,
            "disruption_duration_quarters": 2.0,
            "fed_funds_rate_baseline": 4.5,
        }
        supply = FedOilAdapter().execute({**base, "shock_type": "supply"})
        demand = FedOilAdapter().execute({**base, "shock_type": "demand"})
        assert abs(demand.outputs["peak_gdp_impact_pct"]) < abs(
            supply.outputs["peak_gdp_impact_pct"]
        )


class TestMarketSimAnalytical:
    def test_oil_and_gas_shock_produce_consumer_surplus_loss(self) -> None:
        from src.models.oil.marketsim import MarketSimAdapter

        out = MarketSimAdapter().execute({
            "oil_price_shock_pct": 50.0,
            "natural_gas_price_change_pct": 30.0,
            "disruption_duration_months": 6.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "consumer_surplus_loss_bn_usd",
            "producer_surplus_change_oil_bn_usd",
            "net_welfare_impact_bn_usd",
            "oil_demand_destruction_mbd",
            "fuel_switching_oil_to_gas_mmbtu",
        ):
            assert key in out.outputs
            _assert_finite_number(out.outputs[key])
        assert out.outputs["consumer_surplus_loss_bn_usd"] > 0.0


# --- MACRO tier ------------------------------------------------------------

class TestMPSGEJLAnalytical:
    def test_oil_shock_helps_gcc_hurts_india(self) -> None:
        from src.models.macro.mpsge_jl import MPSGEJLAdapter

        out = MPSGEJLAdapter().execute({
            "oil_price_shock_pct": 50.0,
            "trade_disruption_spec": {"trade_cost_multiplier": 1.2},
            "commodity_price_shocks": {"lng": 30.0, "fertilizer": 20.0},
            "disruption_duration_months": 6.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "gdp_impact_pct",
            "welfare_pct_change_by_region",
            "regional_vars",
            "bilateral_trade_flow_change_pct",
            "terms_of_trade_pct_change_by_region",
        ):
            assert key in out.outputs
        welfare = out.outputs["welfare_pct_change_by_region"]
        assert welfare["MENA_GCC"] > 0.0
        assert welfare["IND"] < 0.0


class TestNRELAnalytical:
    def test_gas_shock_lifts_retail_and_shifts_dispatch_to_renewables(self) -> None:
        from src.models.macro.nrel import NRELAdapter

        out = NRELAdapter().execute({
            "natural_gas_price_change_pct": 50.0,
            "electricity_demand_change_pct": 2.0,
            "disruption_duration_months": 6.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "retail_electricity_price_change_pct",
            "generation_dispatch_pct_change",
            "co2_emissions_pct_change",
            "renewables_dispatch_gain_pp",
            "coal_dispatch_gain_pp",
            "gdp_impact_pct",  # macro companion
        ):
            assert key in out.outputs
        assert out.outputs["retail_electricity_price_change_pct"] > 0.0
        dispatch = out.outputs["generation_dispatch_pct_change"]
        assert dispatch["natural_gas"] < 0.0
        assert dispatch["coal"] > 0.0
        assert dispatch["renewables"] > 0.0


# --- HELIUM_DOWNSTREAM tier -----------------------------------------------

class TestArgonneABMAnalytical:
    def test_replications_emit_mean_and_std_companion_fields(self) -> None:
        from src.models.helium.argonne_abm import ArgonneABMAdapter

        out = ArgonneABMAdapter().execute({
            "supply_shock_pct": 25.0,
            "disruption_duration_months": 6.0,
            "demand_response_elasticity": -0.15,
        })
        _assert_mvp_metadata(out)
        for base in (
            "equilibrium_price_change_pct",
            "unmet_demand_pct",
            "critical_application_failure_rate",
        ):
            assert f"{base}_mean" in out.outputs
            assert f"{base}_std" in out.outputs
        assert out.outputs["n_replications"] == 20
        assert out.outputs["equilibrium_price_change_pct_std"] >= 0.0
        assert "agent_population_summary" in out.outputs


# --- FERTILIZER_AGRICULTURE tier ------------------------------------------

class TestWorldFertilizerAnalytical:
    def test_ng_and_me_loss_lift_nitrogen_index(self) -> None:
        from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter

        out = WorldFertilizerAdapter().execute({
            "natural_gas_price_change_pct": 50.0,
            "middle_east_production_loss_pct": 30.0,
            "disruption_duration_months": 6.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "fertilizer_price_index_pct",
            "nitrogen_price_pct",
            "phosphate_price_pct",
            "potash_price_pct",
            "forward_price_curves",
            "trade_flows",
        ):
            assert key in out.outputs
        assert out.outputs["nitrogen_price_pct"] > 0.0
        assert "urea" in out.outputs["forward_price_curves"]
        assert len(out.outputs["forward_price_curves"]["urea"]) >= 12


class TestAPSIMAnalytical:
    def test_input_reductions_drop_yields(self) -> None:
        from src.models.fertilizer.apsim import APSIMAdapter

        out = APSIMAdapter().execute({
            "fertilizer_application_reduction_pct": 30.0,
            "irrigation_water_reduction_pct": 20.0,
            "growing_season": "2026_winter_wheat",
        })
        _assert_mvp_metadata(out)
        for key in (
            "yield_pct_change_by_crop",
            "mean_yield_pct_change",
            "n_use_efficiency_new",
            "crop_yield_loss_pct",
        ):
            assert key in out.outputs
        assert out.outputs["mean_yield_pct_change"] < 0.0
        assert "wheat" in out.outputs["yield_pct_change_by_crop"]


# --- LNG tier --------------------------------------------------------------

class TestLNGSTAnalytical:
    def test_qatar_uae_loss_lifts_ttf_more_than_henry_hub(self) -> None:
        from src.models.lng.lngst import LNGSTAdapter

        out = LNGSTAdapter().execute({
            "qatar_export_reduction_pct": 80.0,
            "uae_export_reduction_pct": 50.0,
            "spot_price_multiplier": 1.5,
            "disruption_duration_months": 6.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "ttf_price",
            "henry_hub_price",
            "jkm_price",
            "supply_shortfall_bcm",
            "lng_price_usd_mmbtu",
        ):
            assert key in out.outputs
            _assert_finite_number(out.outputs[key])
        assert out.outputs["ttf_price"] > out.outputs["henry_hub_price"]


# --- WATER tier ------------------------------------------------------------

class TestWEAPMENAAnalytical:
    def test_kuwait_higher_unmet_share_than_uae(self) -> None:
        from src.models.water.weap import WEAPAdapter

        out = WEAPAdapter().execute({
            "desalination_capacity_loss_pct": 30.0,
            "disruption_duration_weeks": 12.0,
            "affected_countries": ["uae", "qatar", "saudi_arabia", "kuwait"],
            "alternative_supply_available": True,
            "population_affected_millions": 50.0,
        })
        _assert_mvp_metadata(out)
        for key in (
            "aggregate_unmet_demand_pct",
            "unmet_demand_pct_by_country",
            "supply_coverage_pct_by_country",
            "cumulative_water_deficit_pct_weeks",
        ):
            assert key in out.outputs
        by_country = out.outputs["unmet_demand_pct_by_country"]
        # Kuwait has the highest desal dependence (0.92) -> highest
        # unmet-demand share for the same loss percentage.
        assert by_country["kuwait"] > by_country["uae"]


# ---------------------------------------------------------------------------
# Forwarding-rule structural test
# ---------------------------------------------------------------------------


class TestUpstreamForwardingMappingNewRules:
    def test_new_rules_present(self) -> None:
        """The 8 new forwarding rules should be parseable and present."""
        import yaml
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        cfg = yaml.safe_load(
            (repo_root / "configs" / "upstream_forwarding_mapping.yaml").read_text()
        )
        models = cfg["models"]

        # SHIPPING -> POLES-JRC
        assert "rerouting_cost_multiplier" in models["poles_jrc"]
        assert "insurance_premium_increase_pct" in models["poles_jrc"]
        primary_source = (
            models["poles_jrc"]["rerouting_cost_multiplier"]["sources"][0][
                "source_model"
            ]
        )
        assert primary_source == "aisdb"

        # New macro/oil downstream targets
        assert "fed_oil" in models
        assert "marketsim" in models
        assert "nrel" in models

        # MPSGE.jl trade-disruption-spec rule
        assert "trade_disruption_spec" in models["mpsge_jl"]

        # World fertilizer is now the primary source for the fertilizer
        # price shock in the macro CGE adapters.
        for downstream in ("opencge", "pycge", "mpsge_jl"):
            rule = models[downstream]["commodity_price_shocks__fertilizer"]
            assert rule["sources"][0]["source_model"] == "world_fertilizer"
