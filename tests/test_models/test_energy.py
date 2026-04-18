"""Tests for the energy-systems model adapters.

These tests stay strictly in the validate / translate layer; they do
NOT invoke the real solvers (glpsol, GAMS, CBC). The execute() paths
are exercised in integration tests guarded by external prerequisites.
"""

from __future__ import annotations

from pathlib import Path

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.energy import (
    MESSAGEixAdapter,
    MESSAGEixConfig,
    OSeMOSYSAdapter,
    OSeMOSYSConfig,
    TEMOAAdapter,
    TEMOAConfig,
)


# ---------------------------------------------------------------------------
# Sample shock parameters used across all three adapters
# ---------------------------------------------------------------------------

SAMPLE_PARAMS = {
    "scenario_id": "test_B",
    "oil_supply_loss_mbd": 6.0,
    "gas_supply_loss_bcfd": 12.0,
    "disruption_duration_months": 6.0,
    "lng_export_capacity_loss_pct": 25.0,
    "capital_cost_multiplier": 1.15,
    "co2_price_baseline_usd_per_t": 50.0,
}


# ---------------------------------------------------------------------------
# OSeMOSYS
# ---------------------------------------------------------------------------


class TestOSeMOSYSAdapter:
    def test_metadata(self) -> None:
        adapter = OSeMOSYSAdapter()
        assert adapter.model_id == "osemosys"
        assert adapter.commodity_system == CommoditySystem.ENERGY_SYSTEMS
        assert adapter.analytical_level == AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    def test_validate_accepts_canonical_params(self) -> None:
        adapter = OSeMOSYSAdapter()
        result = adapter.validate_inputs(SAMPLE_PARAMS)
        assert result.valid, result.errors

    def test_validate_flags_missing_params(self) -> None:
        adapter = OSeMOSYSAdapter()
        params = {k: v for k, v in SAMPLE_PARAMS.items() if k != "capital_cost_multiplier"}
        result = adapter.validate_inputs(params)
        assert not result.valid
        assert any("capital_cost_multiplier" in e for e in result.errors)

    def test_validate_rejects_out_of_range(self) -> None:
        adapter = OSeMOSYSAdapter()
        bad = {**SAMPLE_PARAMS, "lng_export_capacity_loss_pct": 150.0}
        result = adapter.validate_inputs(bad)
        assert not result.valid
        assert any("lng_export_capacity_loss_pct" in e for e in result.errors)

    def test_translate_inputs_emits_pj_conversions(self) -> None:
        adapter = OSeMOSYSAdapter()
        translated = adapter.translate_inputs(SAMPLE_PARAMS)
        assert translated["scenario_id"] == "test_B"
        shocks = translated["shocks"]
        assert shocks["capital_cost_multiplier"] == 1.15
        assert shocks["lng_export_capacity_loss_pct"] == 25.0
        assert shocks["duration_years"] == 0.5
        assert shocks["oil_supply_loss_pj_per_yr"] > 0
        assert shocks["gas_supply_loss_pj_per_yr"] > 0

    def test_config_defaults_point_at_vendored_dir(self) -> None:
        cfg = OSeMOSYSConfig()
        assert cfg.osemosys_dir == Path("Models/Energy/OSeMOSYS")
        assert cfg.solver == "glpk"


# ---------------------------------------------------------------------------
# MESSAGEix
# ---------------------------------------------------------------------------


class TestMESSAGEixAdapter:
    def test_metadata(self) -> None:
        adapter = MESSAGEixAdapter()
        assert adapter.model_id == "messageix"
        assert adapter.commodity_system == CommoditySystem.ENERGY_SYSTEMS
        assert adapter.analytical_level == AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    def test_validate_accepts_canonical_params(self) -> None:
        adapter = MESSAGEixAdapter()
        result = adapter.validate_inputs(SAMPLE_PARAMS)
        # message-ix may not be installed in the test environment;
        # validation should still be valid (warnings only) when params
        # are well-formed.
        assert result.valid, result.errors

    def test_validate_flags_negative_co2_price(self) -> None:
        adapter = MESSAGEixAdapter()
        bad = {**SAMPLE_PARAMS, "co2_price_baseline_usd_per_t": -10.0}
        result = adapter.validate_inputs(bad)
        assert not result.valid
        assert any("co2_price_baseline_usd_per_t" in e for e in result.errors)

    def test_translate_inputs_passes_overrides_through(self) -> None:
        adapter = MESSAGEixAdapter()
        translated = adapter.translate_inputs(SAMPLE_PARAMS)
        shocks = translated["shocks"]
        assert shocks["oil_supply_loss_mbd"] == 6.0
        assert shocks["gas_supply_loss_bcfd"] == 12.0
        assert shocks["duration_years"] == 0.5
        assert shocks["lng_export_capacity_loss_pct"] == 25.0

    def test_config_default_fuel_mapping(self) -> None:
        cfg = MESSAGEixConfig()
        assert cfg.fuel_to_commodity["oil"] == "crudeoil"
        assert cfg.fuel_to_commodity["lng"] == "LNG"


# ---------------------------------------------------------------------------
# TEMOA
# ---------------------------------------------------------------------------


class TestTEMOAAdapter:
    def test_metadata(self) -> None:
        adapter = TEMOAAdapter()
        assert adapter.model_id == "temoa"
        assert adapter.commodity_system == CommoditySystem.ENERGY_SYSTEMS
        assert adapter.analytical_level == AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    def test_validate_accepts_canonical_params(self) -> None:
        adapter = TEMOAAdapter()
        result = adapter.validate_inputs(SAMPLE_PARAMS)
        assert result.valid, result.errors

    def test_validate_rejects_zero_capex_multiplier(self) -> None:
        adapter = TEMOAAdapter()
        bad = {**SAMPLE_PARAMS, "capital_cost_multiplier": 0.0}
        result = adapter.validate_inputs(bad)
        assert not result.valid

    def test_translate_inputs_carries_optional_oil_path(self) -> None:
        adapter = TEMOAAdapter()
        params = {**SAMPLE_PARAMS, "oil_price_path_override_usd": 120.0}
        translated = adapter.translate_inputs(params)
        assert translated["shocks"]["oil_price_path_override_usd"] == 120.0

    def test_config_defaults(self) -> None:
        cfg = TEMOAConfig()
        assert cfg.solver == "cbc"
        assert cfg.temoa_module == "temoa.temoa_run"
        assert cfg.baseline_db_path.suffix == ".sqlite"
