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
