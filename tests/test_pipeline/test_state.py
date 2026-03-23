"""Tests for pipeline state management."""

from src.common.types import ConfidenceLevel, ModelExecutionStatus, Scenario
from src.pipeline.state import (
    ModelExecutionResult,
    ModelParameterSet,
    ParameterValue,
    PipelineState,
    ScenarioNarrativeState,
)


def test_pipeline_state_construction():
    """Test empty pipeline state construction."""
    state = PipelineState(run_id="test-run")
    assert state.run_id == "test-run"
    assert len(state.scenario_narratives) == 0
    assert not state.scenarios_validated


def test_get_narrative():
    """Test looking up a narrative by scenario ID."""
    state = PipelineState(
        scenario_narratives=[
            ScenarioNarrativeState(
                scenario_id=Scenario.A, label="Test A", narrative="Narrative A"
            ),
            ScenarioNarrativeState(
                scenario_id=Scenario.B, label="Test B", narrative="Narrative B"
            ),
        ]
    )

    result = state.get_narrative(Scenario.A)
    assert result is not None
    assert result.label == "Test A"

    assert state.get_narrative(Scenario.C) is None


def test_get_parameters():
    """Test looking up parameters by (scenario, model) pair."""
    state = PipelineState(
        parameter_sets=[
            ModelParameterSet(
                scenario_id=Scenario.A,
                model_id="poles_jrc",
                parameters=[
                    ParameterValue(
                        name="supply_loss_mbd", value=5.0,
                        confidence=ConfidenceLevel.HIGH,
                    ),
                ],
            ),
        ]
    )

    result = state.get_parameters(Scenario.A, "poles_jrc")
    assert result is not None
    assert len(result.parameters) == 1

    assert state.get_parameters(Scenario.A, "nonexistent") is None


def test_get_successful_results():
    """Test filtering for successful execution results."""
    state = PipelineState(
        execution_results=[
            ModelExecutionResult(
                scenario_id=Scenario.A, model_id="model1",
                status=ModelExecutionStatus.COMPLETED,
                outputs={"price": 100},
            ),
            ModelExecutionResult(
                scenario_id=Scenario.A, model_id="model2",
                status=ModelExecutionStatus.FAILED,
                error_message="timeout",
            ),
            ModelExecutionResult(
                scenario_id=Scenario.A, model_id="model3",
                status=ModelExecutionStatus.SKIPPED,
            ),
        ]
    )

    successful = state.get_successful_results()
    assert len(successful) == 1
    assert successful[0].model_id == "model1"
