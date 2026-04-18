"""LangChain tool wrapping for model adapters.

Each ModelAdapter becomes a LangChain tool that can be invoked by
LangGraph agents. Uses @tool with Pydantic args schemas for type safety.

The response_format="content_and_artifact" pattern returns both:
- A human-readable summary (sent to the LLM for reasoning)
- Structured data (stored in ToolMessage.artifact for pipeline state)
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.registry import ModelRegistry

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Generic model execution tool args schema
# ---------------------------------------------------------------------------


class ModelExecutionInput(BaseModel):
    """Input schema for the generic model execution tool."""

    model_id: str = Field(description="ID of the model to execute (from registry)")
    scenario_id: str = Field(description="Scenario identifier (e.g., 'swift_contained')")
    parameters: dict[str, Any] = Field(description="Parameter dict for the model")


class ModelValidationInput(BaseModel):
    """Input schema for the model validation tool."""

    model_id: str = Field(description="ID of the model to validate inputs for")
    parameters: dict[str, Any] = Field(description="Parameter dict to validate")


# ---------------------------------------------------------------------------
# Tool factory functions
# ---------------------------------------------------------------------------


def create_model_execution_tool(registry: ModelRegistry) -> StructuredTool:
    """Create a generic model execution tool backed by the registry.

    Returns both a human-readable summary and structured artifact data.
    """

    def _run_model(model_id: str, scenario_id: str, parameters: dict[str, Any]) -> tuple[str, dict]:
        adapter = registry.get(model_id)
        if adapter is None:
            return f"Model '{model_id}' not found in registry.", {"error": "not_found"}

        # Validate
        validation = adapter.validate_inputs(parameters)
        if not validation.valid:
            error_msg = f"Validation failed for {model_id}: {'; '.join(validation.errors)}"
            return error_msg, {"error": "validation_failed", "errors": validation.errors}

        # Translate and execute
        try:
            translated = adapter.translate_inputs(parameters)
            output = adapter.execute(translated)

            summary = (
                f"Model {model_id} completed for scenario {scenario_id}. "
                f"Produced {len(output.outputs)} output variables."
            )
            if output.convergence_status:
                summary += f" Convergence: {output.convergence_status}."

            artifact = {
                "model_id": model_id,
                "scenario_id": scenario_id,
                "outputs": output.outputs,
                "metadata": output.metadata,
                "convergence_status": output.convergence_status,
            }
            return summary, artifact

        except NotImplementedError as e:
            return f"Model {model_id} is not yet implemented: {e}", {"error": "not_implemented"}

        except Exception as e:
            error_msg = f"Model {model_id} failed: {type(e).__name__}: {e}"
            return error_msg, {"error": str(e)}

    return StructuredTool.from_function(
        func=_run_model,
        name="run_domain_model",
        description=(
            "Execute a domain model from the crisis analysis pipeline. "
            "Validates inputs, translates parameters, runs the model, "
            "and returns structured outputs with execution metadata."
        ),
        args_schema=ModelExecutionInput,
        response_format="content_and_artifact",
    )


def create_model_validation_tool(registry: ModelRegistry) -> StructuredTool:
    """Create a tool for validating model inputs without execution."""

    def _validate_model(model_id: str, parameters: dict[str, Any]) -> str:
        adapter = registry.get(model_id)
        if adapter is None:
            return f"Model '{model_id}' not found in registry."

        validation = adapter.validate_inputs(parameters)
        if validation.valid:
            result = f"Validation passed for {model_id}."
            if validation.warnings:
                result += f" Warnings: {'; '.join(validation.warnings)}"
            return result
        else:
            return (
                f"Validation failed for {model_id}. "
                f"Errors: {'; '.join(validation.errors)}"
            )

    return StructuredTool.from_function(
        func=_validate_model,
        name="validate_model_inputs",
        description=(
            "Validate parameters for a domain model without executing it. "
            "Returns validation errors and warnings."
        ),
        args_schema=ModelValidationInput,
    )


def create_adapter_tool(adapter: ModelAdapter) -> StructuredTool:
    """Create a dedicated LangChain tool for a specific model adapter.

    This creates a model-specific tool (e.g., 'run_mpsge_model') with
    the adapter's required parameter schema baked in.
    """

    class AdapterInput(BaseModel):
        scenario_id: str = Field(description="Scenario identifier")
        parameters: dict[str, Any] = Field(
            description=f"Parameters for {adapter.model_id} ({adapter.description[:100]})"
        )

    def _run(scenario_id: str, parameters: dict[str, Any]) -> tuple[str, dict]:
        validation = adapter.validate_inputs(parameters)
        if not validation.valid:
            return f"Validation failed: {'; '.join(validation.errors)}", {"error": "validation_failed"}

        try:
            translated = adapter.translate_inputs(parameters)
            output = adapter.execute(translated)

            summary = (
                f"{adapter.model_id} completed for scenario {scenario_id}. "
                f"Outputs: {list(output.outputs.keys())}"
            )
            artifact = {
                "model_id": adapter.model_id,
                "scenario_id": scenario_id,
                "outputs": output.outputs,
                "metadata": output.metadata,
            }
            return summary, artifact

        except NotImplementedError:
            return f"{adapter.model_id} is not yet implemented.", {"error": "not_implemented"}

        except Exception as e:
            return f"{adapter.model_id} failed: {e}", {"error": str(e)}

    return StructuredTool.from_function(
        func=_run,
        name=f"run_{adapter.model_id}",
        description=adapter.description[:200],
        args_schema=AdapterInput,
        response_format="content_and_artifact",
    )


def build_model_tools(registry: ModelRegistry) -> list[StructuredTool]:
    """Build all model-related tools from a registry.

    Returns:
        List containing the generic execution tool, validation tool,
        and one dedicated tool per registered adapter.
    """
    tools = [
        create_model_execution_tool(registry),
        create_model_validation_tool(registry),
    ]

    for adapter in registry.all_adapters():
        tools.append(create_adapter_tool(adapter))

    logger.info(f"Built {len(tools)} model tools ({len(registry)} adapters + 2 generic)")
    return tools
