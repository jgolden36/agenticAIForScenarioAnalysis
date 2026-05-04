"""Tests for specialized runtime adapter base classes."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.anylogic_adapter import AnyLogicAdapter, AnyLogicConfig
from src.models.adapters.excel_adapter import CellMapping, ExcelAdapter, ExcelConfig
from src.models.adapters.gams_adapter import GAMSAdapter, GAMSConfig
from src.models.adapters.julia_adapter import JuliaAdapter, JuliaConfig
from src.models.adapters.r_adapter import RAdapter, RConfig
from src.models.adapters.subprocess_adapter import (
    SubprocessAdapter,
    SubprocessConfig,
)
from src.models.base import ModelOutput, ValidationResult


# ---------------------------------------------------------------------------
# Concrete test implementations of the abstract adapters
# ---------------------------------------------------------------------------


class ConcreteSubprocessAdapter(SubprocessAdapter):
    @property
    def model_id(self) -> str:
        return "test_subprocess"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "Test subprocess adapter"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

    def parse_outputs(self, raw: Any) -> ModelOutput:
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )


class ConcreteJuliaAdapter(JuliaAdapter):
    @property
    def model_id(self) -> str:
        return "test_julia"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return "Test Julia adapter"

    @property
    def julia_function_name(self) -> str:
        return "test_solve"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    def translate_inputs_for_julia(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

    def parse_outputs(self, raw: Any) -> ModelOutput:
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )


class ConcreteGAMSAdapter(GAMSAdapter):
    @property
    def model_id(self) -> str:
        return "test_gams"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "Test GAMS adapter"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    def populate_database(self, db: Any, params: dict[str, Any]) -> None:
        pass

    def extract_results(self, out_db: Any) -> dict[str, Any]:
        return {"price": 100.0}


class ConcreteExcelAdapter(ExcelAdapter):
    @property
    def model_id(self) -> str:
        return "test_excel"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "Test Excel adapter"

    @property
    def input_mappings(self) -> list[CellMapping]:
        return [CellMapping(sheet="Inputs", cell="B4", param_name="price")]

    @property
    def output_mappings(self) -> list[CellMapping]:
        return [CellMapping(sheet="Outputs", cell="C12", param_name="result")]

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)


class ConcreteAnyLogicAdapter(AnyLogicAdapter):
    @property
    def model_id(self) -> str:
        return "test_anylogic"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.HELIUM_SEMICONDUCTORS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "Test AnyLogic adapter"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    def build_cli_args(self, params: dict[str, Any]) -> list[str]:
        return ["--test"]

    def aggregate_replications(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {}
        values = [r.get("price", 0) for r in results]
        return {"price_mean": sum(values) / len(values)}


class ConcreteRAdapter(RAdapter):
    @property
    def model_id(self) -> str:
        return "test_r"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "Test R adapter"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        return params


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSubprocessAdapter:
    def test_properties(self):
        adapter = ConcreteSubprocessAdapter()
        assert adapter.model_id == "test_subprocess"
        assert adapter.commodity_system == CommoditySystem.OIL
        assert adapter.analytical_level == AnalyticalLevel.COMMODITY

    def test_config_required_for_execution(self):
        adapter = ConcreteSubprocessAdapter()
        with pytest.raises(ValueError, match="requires a SubprocessConfig"):
            adapter.subprocess_config

    def test_execute_with_config(self):
        """Test that subprocess execution works with a real command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a script that reads JSON input and writes JSON output
            script = Path(tmpdir) / "model.sh"
            script.write_text(
                '#!/bin/bash\n'
                'cat "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); '
                "d['result']=42; json.dump(d, open(sys.argv[1].replace('inputs','outputs'),'w'))\" "
                '"$1"\n'
            )
            script.chmod(0o755)

            config = SubprocessConfig(
                command_template=f"{script} {{input_path}}",
                run_dir_base=Path(tmpdir) / "runs",
            )
            adapter = ConcreteSubprocessAdapter(config)
            output = adapter.execute({"scenario_id": "test", "value": 10})
            assert isinstance(output, ModelOutput)
            assert output.outputs.get("result") == 42

    def test_get_run_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SubprocessConfig(
                command_template="echo test",
                run_dir_base=Path(tmpdir),
            )
            adapter = ConcreteSubprocessAdapter(config)
            run_dir = adapter._get_run_dir("scenario_a")
            assert run_dir.exists()
            assert "test_subprocess_scenario_a" in str(run_dir)


class TestJuliaAdapter:
    def test_properties(self):
        adapter = ConcreteJuliaAdapter()
        assert adapter.model_id == "test_julia"
        assert adapter.julia_function_name == "test_solve"

    def test_config_required_for_execution(self):
        adapter = ConcreteJuliaAdapter()
        with pytest.raises(ValueError, match="requires a JuliaConfig"):
            adapter.julia_config

    def test_subprocess_fallback_requires_script_path(self):
        config = JuliaConfig(
            julia_project_path=Path("/tmp/fake"),
            use_juliacall=False,
            julia_script_path=None,
        )
        adapter = ConcreteJuliaAdapter(config)
        with pytest.raises(ValueError, match="julia_script_path must be set"):
            adapter.execute({"test": 1})


class TestGAMSAdapter:
    def test_properties(self):
        adapter = ConcreteGAMSAdapter()
        assert adapter.model_id == "test_gams"
        assert adapter.commodity_system == CommoditySystem.FERTILIZER_AGRICULTURE

    def test_config_required_for_execution(self):
        adapter = ConcreteGAMSAdapter()
        with pytest.raises(ValueError, match="requires a GAMSConfig"):
            adapter.gams_config

    def test_execute_raises_import_error_without_gams(self):
        config = GAMSConfig(
            gams_system_dir=Path("/opt/gams"),
            model_gms_path=Path("/tmp/model.gms"),
        )
        adapter = ConcreteGAMSAdapter(config)
        with pytest.raises(ImportError, match="gamsapi is not installed"):
            adapter.execute({"scenario_id": "test"})


class TestExcelAdapter:
    def test_properties(self):
        adapter = ConcreteExcelAdapter()
        assert adapter.model_id == "test_excel"
        assert len(adapter.input_mappings) == 1
        assert len(adapter.output_mappings) == 1

    def test_config_required_for_execution(self):
        adapter = ConcreteExcelAdapter()
        with pytest.raises(ValueError, match="requires an ExcelConfig"):
            adapter.excel_config

    def test_cell_mapping_fields(self):
        mapping = CellMapping(sheet="Sheet1", cell="A1", param_name="test_param")
        assert mapping.sheet == "Sheet1"
        assert mapping.cell == "A1"
        assert mapping.param_name == "test_param"


class TestAnyLogicAdapter:
    def test_properties(self):
        adapter = ConcreteAnyLogicAdapter()
        assert adapter.model_id == "test_anylogic"

    def test_aggregate_replications_empty(self):
        adapter = ConcreteAnyLogicAdapter()
        assert adapter.aggregate_replications([]) == {}

    def test_aggregate_replications_single(self):
        adapter = ConcreteAnyLogicAdapter()
        result = adapter.aggregate_replications([{"price": 100}])
        assert result["price_mean"] == 100

    def test_aggregate_replications_multiple(self):
        adapter = ConcreteAnyLogicAdapter()
        result = adapter.aggregate_replications([
            {"price": 80},
            {"price": 100},
            {"price": 120},
        ])
        assert result["price_mean"] == 100.0

    def test_build_cli_args(self):
        adapter = ConcreteAnyLogicAdapter()
        assert adapter.build_cli_args({}) == ["--test"]


class TestRAdapter:
    def test_properties(self):
        adapter = ConcreteRAdapter()
        assert adapter.model_id == "test_r"

    def test_config_required_for_execution(self):
        adapter = ConcreteRAdapter()
        with pytest.raises(ValueError, match="requires an RConfig"):
            adapter.r_config


class TestUpdatedModelStubs:
    """Test that the updated model stubs still work correctly."""

    def test_mpsge_jl_inherits_julia_adapter(self):
        from src.models.macro.mpsge_jl import MPSGEJLAdapter

        adapter = MPSGEJLAdapter()
        assert isinstance(adapter, JuliaAdapter)
        assert adapter.model_id == "mpsge_jl"
        assert adapter.julia_function_name == "solve_mpsge"

    def test_mpsge_jl_runs_analytical_fallback_without_config(self):
        """Without a JuliaConfig, the adapter falls through to the
        macro_kernel-backed analytical MVP path instead of raising."""
        from src.models.macro.mpsge_jl import MPSGEJLAdapter

        adapter = MPSGEJLAdapter()
        out = adapter.execute({
            "oil_price_shock_pct": 50.0,
            "trade_disruption_spec": {"trade_cost_multiplier": 1.2},
            "commodity_price_shocks": {"lng": 30.0, "fertilizer": 20.0},
            "disruption_duration_months": 6.0,
        })
        assert out.convergence_status == "converged"
        assert out.metadata.get("mode") == "analytical_mvp"
        assert "gdp_impact_pct" in out.outputs
        assert "regional_vars" in out.outputs

    def test_lngst_inherits_excel_adapter(self):
        from src.models.lng.lngst import LNGSTAdapter

        adapter = LNGSTAdapter()
        assert isinstance(adapter, ExcelAdapter)
        assert adapter.model_id == "lngst"
        assert len(adapter.input_mappings) > 0
        assert len(adapter.output_mappings) > 0

    def test_lngst_runs_analytical_fallback_without_config(self):
        """Without an ExcelConfig, the adapter falls through to the
        closed-form Qatar/UAE LNG market fallback."""
        from src.models.lng.lngst import LNGSTAdapter

        adapter = LNGSTAdapter()
        out = adapter.execute({
            "qatar_export_reduction_pct": 80.0,
            "uae_export_reduction_pct": 50.0,
            "spot_price_multiplier": 1.5,
            "disruption_duration_months": 6.0,
        })
        assert out.convergence_status == "converged"
        assert out.metadata.get("mode") == "analytical_mvp"
        for key in ("ttf_price", "henry_hub_price", "jkm_price",
                   "supply_shortfall_bcm", "lng_price_usd_mmbtu"):
            assert key in out.outputs

    def test_world_fertilizer_inherits_gams_adapter(self):
        from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter

        adapter = WorldFertilizerAdapter()
        assert isinstance(adapter, GAMSAdapter)
        assert adapter.model_id == "world_fertilizer"

    def test_world_fertilizer_runs_analytical_fallback_without_config(self):
        """Without a GAMSConfig, the adapter falls through to the
        closed-form NG-feedstock + ME-loss fertilizer market fallback."""
        from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter

        adapter = WorldFertilizerAdapter()
        out = adapter.execute({
            "natural_gas_price_change_pct": 50.0,
            "middle_east_production_loss_pct": 30.0,
            "disruption_duration_months": 6.0,
        })
        assert out.convergence_status == "converged"
        assert out.metadata.get("mode") == "analytical_mvp"
        assert "fertilizer_price_index_pct" in out.outputs
        assert "forward_price_curves" in out.outputs

    def test_argonne_abm_inherits_anylogic_adapter(self):
        from src.models.helium.argonne_abm import ArgonneABMAdapter

        adapter = ArgonneABMAdapter()
        assert isinstance(adapter, AnyLogicAdapter)
        assert adapter.model_id == "argonne_abm"

    def test_argonne_abm_runs_analytical_fallback_without_config(self):
        """Without an AnyLogicConfig, the adapter falls through to the
        20-replication stochastic stand-in built around the
        world_helium_model elasticity formula."""
        from src.models.helium.argonne_abm import ArgonneABMAdapter

        adapter = ArgonneABMAdapter()
        out = adapter.execute({
            "supply_shock_pct": 25.0,
            "disruption_duration_months": 6.0,
            "demand_response_elasticity": -0.15,
        })
        assert out.convergence_status == "converged"
        assert out.metadata.get("mode") == "analytical_mvp"
        assert "equilibrium_price_change_pct_mean" in out.outputs
        assert "equilibrium_price_change_pct_std" in out.outputs
        assert out.outputs["n_replications"] == 20

    def test_argonne_abm_aggregate_replications(self):
        from src.models.helium.argonne_abm import ArgonneABMAdapter

        adapter = ArgonneABMAdapter()
        result = adapter.aggregate_replications([
            {"helium_price_usd": 200, "stockouts": 5},
            {"helium_price_usd": 250, "stockouts": 8},
            {"helium_price_usd": 300, "stockouts": 3},
        ])
        assert result["helium_price_usd"] == 250.0
        assert result["helium_price_usd_n"] == 3
        assert "helium_price_usd_std" in result
