"""Tests for the model executor."""

import asyncio

from src.common.types import AnalyticalLevel, CommoditySystem, ModelExecutionStatus, Scenario
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.executor import ModelExecutor
from src.models.registry import ModelRegistry
from src.pipeline.config import ExecutionConfig


class SuccessAdapter(ModelAdapter):
    @property
    def model_id(self):
        return "success_model"

    @property
    def commodity_system(self):
        return CommoditySystem.OIL

    @property
    def analytical_level(self):
        return AnalyticalLevel.COMMODITY

    @property
    def description(self):
        return "Always succeeds"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        return ModelOutput(
            model_id="success_model",
            outputs={"price": 100.0},
        )

    def parse_outputs(self, raw):
        return raw


class FailAdapter(ModelAdapter):
    @property
    def model_id(self):
        return "fail_model"

    @property
    def commodity_system(self):
        return CommoditySystem.OIL

    @property
    def analytical_level(self):
        return AnalyticalLevel.COMMODITY

    @property
    def description(self):
        return "Always fails"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        raise RuntimeError("Model crashed")

    def parse_outputs(self, raw):
        return raw


class StubAdapter(ModelAdapter):
    @property
    def model_id(self):
        return "stub_model"

    @property
    def commodity_system(self):
        return CommoditySystem.OIL

    @property
    def analytical_level(self):
        return AnalyticalLevel.COMMODITY

    @property
    def description(self):
        return "Not implemented"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        raise NotImplementedError("Stub model")

    def parse_outputs(self, raw):
        return raw


def test_executor_success():
    """Test successful model execution."""
    registry = ModelRegistry()
    registry.register(SuccessAdapter())
    executor = ModelExecutor(registry)

    results = asyncio.run(
        executor.execute_all(
            Scenario.A, {"success_model": {"param1": 1.0}}
        )
    )

    assert len(results) == 1
    assert results[0].status == ModelExecutionStatus.COMPLETED
    assert results[0].outputs["price"] == 100.0


def test_executor_failure_isolation():
    """Test that one model failure doesn't crash others."""
    registry = ModelRegistry()
    registry.register(SuccessAdapter())
    registry.register(FailAdapter())
    executor = ModelExecutor(registry)

    results = asyncio.run(
        executor.execute_all(
            Scenario.A,
            {"success_model": {"param1": 1.0}, "fail_model": {"param1": 1.0}},
        )
    )

    assert len(results) == 2
    statuses = {r.model_id: r.status for r in results}
    assert statuses["success_model"] == ModelExecutionStatus.COMPLETED
    assert statuses["fail_model"] == ModelExecutionStatus.FAILED


def test_executor_stub_skipped():
    """Test that NotImplementedError results in SKIPPED status."""
    registry = ModelRegistry()
    registry.register(StubAdapter())
    executor = ModelExecutor(registry)

    results = asyncio.run(
        executor.execute_all(
            Scenario.A, {"stub_model": {"param1": 1.0}}
        )
    )

    assert len(results) == 1
    assert results[0].status == ModelExecutionStatus.SKIPPED


# ---------------------------------------------------------------------------
# Upstream forwarding barrier (Algorithm 1 step 11) inside execute_all
# ---------------------------------------------------------------------------

import yaml

from src.pipeline.upstream_forwarding import clear_mapping_cache


class UpstreamOilAdapter(ModelAdapter):
    """Commodity-tier mock that emits an oil price shock output."""

    @property
    def model_id(self):
        return "mock_oil"

    @property
    def commodity_system(self):
        return CommoditySystem.OIL

    @property
    def analytical_level(self):
        return AnalyticalLevel.COMMODITY

    @property
    def description(self):
        return "Mock upstream oil model"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        return ModelOutput(
            model_id="mock_oil",
            outputs={"peak_price_change_pct": 42.0},
        )

    def parse_outputs(self, raw):
        return raw


class EchoMacroAdapter(ModelAdapter):
    """Macro-tier mock that echoes its received parameters as outputs."""

    @property
    def model_id(self):
        return "mock_macro"

    @property
    def commodity_system(self):
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self):
        return AnalyticalLevel.SHORT_RUN_MACRO

    @property
    def description(self):
        return "Mock macro model"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        return ModelOutput(model_id="mock_macro", outputs=dict(inputs))

    def parse_outputs(self, raw):
        return raw


class FailingOilAdapter(UpstreamOilAdapter):
    def execute(self, inputs):
        raise RuntimeError("upstream model crashed")


def _write_forwarding_mapping(tmp_path):
    p = tmp_path / "mapping.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "models": {
                    "mock_macro": {
                        "oil_price_shock_pct": {
                            "sources": [
                                {
                                    "source_model": "mock_oil",
                                    "source_field": "peak_price_change_pct",
                                    "transform": "identity",
                                }
                            ]
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return p


def test_executor_forwards_upstream_outputs_to_macro_level(tmp_path):
    """execute_all applies the step-11 barrier between analytical levels."""
    clear_mapping_cache()
    registry = ModelRegistry()
    registry.register(UpstreamOilAdapter())
    registry.register(EchoMacroAdapter())
    executor = ModelExecutor(
        registry, forwarding_mapping_path=_write_forwarding_mapping(tmp_path)
    )

    results = asyncio.run(
        executor.execute_all(
            Scenario.A,
            {
                "mock_oil": {"disruption_duration_weeks": 6},
                "mock_macro": {"oil_price_shock_pct": 5.0},
            },
        )
    )

    by_id = {r.model_id: r for r in results}
    macro = by_id["mock_macro"]
    assert macro.status == ModelExecutionStatus.COMPLETED
    # The LLM-extracted 5.0 was replaced with the upstream-computed 42.0
    assert macro.outputs["oil_price_shock_pct"] == 42.0
    overrides = macro.outputs["_upstream_overrides"]
    assert overrides[0]["llm_value"] == 5.0
    assert overrides[0]["computed_value"] == 42.0
    assert overrides[0]["source_model_id"] == "mock_oil"
    # The upstream model's own result is untouched
    assert "_upstream_overrides" not in by_id["mock_oil"].outputs


def test_executor_forwarding_can_be_disabled(tmp_path):
    clear_mapping_cache()
    registry = ModelRegistry()
    registry.register(UpstreamOilAdapter())
    registry.register(EchoMacroAdapter())
    executor = ModelExecutor(
        registry, forwarding_mapping_path=_write_forwarding_mapping(tmp_path)
    )

    results = asyncio.run(
        executor.execute_all(
            Scenario.A,
            {
                "mock_oil": {"disruption_duration_weeks": 6},
                "mock_macro": {"oil_price_shock_pct": 5.0},
            },
            apply_upstream_forwarding=False,
        )
    )

    macro = {r.model_id: r for r in results}["mock_macro"]
    assert macro.outputs["oil_price_shock_pct"] == 5.0
    assert "_upstream_overrides" not in macro.outputs


def test_executor_preserves_llm_value_when_upstream_failed(tmp_path):
    """Graceful degradation: a FAILED upstream run leaves LLM params alone."""
    clear_mapping_cache()
    registry = ModelRegistry()
    registry.register(FailingOilAdapter())
    registry.register(EchoMacroAdapter())
    config = ExecutionConfig(retry_failed_models=False)
    executor = ModelExecutor(
        registry,
        config=config,
        forwarding_mapping_path=_write_forwarding_mapping(tmp_path),
    )

    results = asyncio.run(
        executor.execute_all(
            Scenario.A,
            {
                "mock_oil": {"disruption_duration_weeks": 6},
                "mock_macro": {"oil_price_shock_pct": 5.0},
            },
        )
    )

    by_id = {r.model_id: r for r in results}
    assert by_id["mock_oil"].status == ModelExecutionStatus.FAILED
    macro = by_id["mock_macro"]
    assert macro.status == ModelExecutionStatus.COMPLETED
    assert macro.outputs["oil_price_shock_pct"] == 5.0
    assert "_upstream_overrides" not in macro.outputs
