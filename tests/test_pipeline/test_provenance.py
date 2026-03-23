"""Tests for provenance tracking."""

from src.common.types import ConfidenceLevel, ModelExecutionStatus, Scenario
from src.interface.provenance import ProvenanceTracker
from src.pipeline.state import (
    ModelExecutionResult,
    ModelParameterSet,
    ParameterValue,
    PipelineState,
    ScenarioNarrativeState,
)


def test_provenance_trace():
    """Test tracing a result back through the full pipeline."""
    state = PipelineState(
        run_id="test",
        scenario_narratives=[
            ScenarioNarrativeState(
                scenario_id=Scenario.A,
                label="Swift Contained",
                narrative="The strait reopens after 4 weeks...",
                quantitative_assumptions={"oil_loss": "5 mb/d"},
            ),
        ],
        parameter_sets=[
            ModelParameterSet(
                scenario_id=Scenario.A,
                model_id="poles_jrc",
                parameters=[
                    ParameterValue(
                        name="supply_loss_mbd",
                        value=5.0,
                        unit="mb/d",
                        confidence=ConfidenceLevel.HIGH,
                    ),
                ],
            ),
        ],
        execution_results=[
            ModelExecutionResult(
                scenario_id=Scenario.A,
                model_id="poles_jrc",
                status=ModelExecutionStatus.COMPLETED,
                outputs={"oil_price_usd": 120.0, "supply_deficit_mbd": 3.2},
                runtime_seconds=45.2,
            ),
        ],
    )

    tracker = ProvenanceTracker(state)
    record = tracker.trace(Scenario.A, "poles_jrc", "oil_price_usd")

    assert record.scenario_id == Scenario.A
    assert record.source_model_id == "poles_jrc"
    assert record.synthesized_value == 120.0
    assert record.model_runtime_seconds == 45.2
    assert record.model_inputs["supply_loss_mbd"] == 5.0
    assert record.parameter_confidence["supply_loss_mbd"] == "high"
    assert record.scenario_label == "Swift Contained"
    assert "oil_loss" in record.relevant_assumptions


def test_provenance_trace_all():
    """Test tracing all results for a scenario."""
    state = PipelineState(
        execution_results=[
            ModelExecutionResult(
                scenario_id=Scenario.A,
                model_id="poles_jrc",
                status=ModelExecutionStatus.COMPLETED,
                outputs={"oil_price_usd": 120.0, "supply_deficit": 3.2},
            ),
        ],
    )

    tracker = ProvenanceTracker(state)
    records = tracker.trace_all_for_scenario(Scenario.A)
    assert len(records) == 2  # Two output variables
