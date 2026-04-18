"""Tests for LangChain tool wrapping of model adapters."""

from __future__ import annotations

from typing import Any

import pytest

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.registry import ModelRegistry
from src.models.tools import (
    build_model_tools,
    create_adapter_tool,
    create_model_execution_tool,
    create_model_validation_tool,
)


class MockAdapter(ModelAdapter):
    @property
    def model_id(self) -> str:
        return "mock_model"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "A mock model for testing tool wrapping"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        if "required_param" not in params:
            return ValidationResult(valid=False, errors=["Missing required_param"])
        return ValidationResult(valid=True)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        return ModelOutput(
            model_id=self.model_id,
            outputs={"price": 42.0, "quantity": 100},
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        return ModelOutput(model_id=self.model_id, outputs=raw)


class StubAdapter(ModelAdapter):
    @property
    def model_id(self) -> str:
        return "stub_model"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "A stub model that is not yet implemented"

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        raise NotImplementedError("Stub model")

    def parse_outputs(self, raw: Any) -> ModelOutput:
        return ModelOutput(model_id=self.model_id, outputs=raw)


def _build_test_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.register(MockAdapter())
    registry.register(StubAdapter())
    return registry


class TestModelExecutionTool:
    def test_successful_execution(self):
        registry = _build_test_registry()
        tool = create_model_execution_tool(registry)

        assert tool.name == "run_domain_model"

        # content_and_artifact returns content string on direct invoke;
        # artifact is available via ToolMessage in agent context
        result = tool.invoke({
            "model_id": "mock_model",
            "scenario_id": "swift_contained",
            "parameters": {"required_param": 1.0},
        })

        assert isinstance(result, str)
        assert "completed" in result.lower()

    def test_validation_failure(self):
        registry = _build_test_registry()
        tool = create_model_execution_tool(registry)

        result = tool.invoke({
            "model_id": "mock_model",
            "scenario_id": "swift_contained",
            "parameters": {},  # Missing required_param
        })

        assert isinstance(result, str)
        assert "validation failed" in result.lower()

    def test_model_not_found(self):
        registry = _build_test_registry()
        tool = create_model_execution_tool(registry)

        result = tool.invoke({
            "model_id": "nonexistent",
            "scenario_id": "test",
            "parameters": {},
        })

        assert "not found" in result.lower()

    def test_not_implemented_model(self):
        registry = _build_test_registry()
        tool = create_model_execution_tool(registry)

        result = tool.invoke({
            "model_id": "stub_model",
            "scenario_id": "test",
            "parameters": {},
        })

        assert "not yet implemented" in result.lower()


class TestModelValidationTool:
    def test_valid_params(self):
        registry = _build_test_registry()
        tool = create_model_validation_tool(registry)

        result = tool.invoke({
            "model_id": "mock_model",
            "parameters": {"required_param": 1.0},
        })

        assert "passed" in result.lower()

    def test_invalid_params(self):
        registry = _build_test_registry()
        tool = create_model_validation_tool(registry)

        result = tool.invoke({
            "model_id": "mock_model",
            "parameters": {},
        })

        assert "failed" in result.lower()

    def test_model_not_found(self):
        registry = _build_test_registry()
        tool = create_model_validation_tool(registry)

        result = tool.invoke({
            "model_id": "nonexistent",
            "parameters": {},
        })

        assert "not found" in result.lower()


class TestAdapterTool:
    def test_create_adapter_tool(self):
        adapter = MockAdapter()
        tool = create_adapter_tool(adapter)

        assert tool.name == "run_mock_model"
        result = tool.invoke({
            "scenario_id": "test",
            "parameters": {"required_param": 1.0},
        })

        # Direct invoke returns content string
        assert isinstance(result, str)
        assert "completed" in result.lower()


class TestBuildModelTools:
    def test_build_all_tools(self):
        registry = _build_test_registry()
        tools = build_model_tools(registry)

        # 2 generic tools + 2 adapter-specific tools
        assert len(tools) == 4

        tool_names = {t.name for t in tools}
        assert "run_domain_model" in tool_names
        assert "validate_model_inputs" in tool_names
        assert "run_mock_model" in tool_names
        assert "run_stub_model" in tool_names
