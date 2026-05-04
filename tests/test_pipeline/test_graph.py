"""Tests for the LangGraph-based pipeline orchestrator."""

from __future__ import annotations

import pytest

from src.pipeline.graph import (
    OverallSimulationState,
    build_pipeline_graph,
    create_initial_state,
)


class TestOverallSimulationState:
    def test_state_type_is_typed_dict(self):
        """Verify OverallSimulationState is a TypedDict (not Pydantic)."""
        # TypedDicts have __annotations__ but are not Pydantic models
        assert hasattr(OverallSimulationState, "__annotations__")
        assert "run_id" in OverallSimulationState.__annotations__
        assert "scenario_narratives" in OverallSimulationState.__annotations__
        assert "parameter_sets" in OverallSimulationState.__annotations__
        assert "execution_results" in OverallSimulationState.__annotations__

    def test_state_has_required_fields(self):
        """Verify all Algorithm 1 stages are represented in state."""
        annotations = OverallSimulationState.__annotations__
        # Module 1
        assert "scenario_narratives" in annotations
        assert "scenarios_validated" in annotations
        # Module 2
        assert "parameter_sets" in annotations
        assert "parameters_validated" in annotations
        # Module 3
        assert "execution_results" in annotations
        # Module 4
        assert "consistency_flags" in annotations
        assert "synthesis_results" in annotations
        assert "synthesis_validated" in annotations
        # Error tracking
        assert "errors" in annotations


class TestCreateInitialState:
    def test_creates_valid_state(self):
        """Test that create_initial_state produces a well-formed state dict."""
        from src.scenarios.framework import (
            CriticalUncertainty,
            FocalIssue,
            ScenarioFramework,
            ScenarioMatrix,
        )

        framework = ScenarioFramework(
            focal_issue=FocalIssue(description="Test crisis"),
            scenario_matrix=ScenarioMatrix(
                uncertainty_x=CriticalUncertainty(
                    name="Duration", description="Duration of closure",
                    pole_low="Swift", pole_high="Prolonged",
                ),
                uncertainty_y=CriticalUncertainty(
                    name="Scope", description="Scope of escalation",
                    pole_low="Contained", pole_high="Escalated",
                ),
            ),
        )

        state = create_initial_state(
            crisis_description="Test crisis description",
            framework=framework,
        )

        assert state["run_id"] != ""
        assert state["crisis_description"] == "Test crisis description"
        assert state["scenarios_validated"] is False
        assert state["parameters_validated"] is False
        assert state["synthesis_validated"] is False
        assert state["scenario_narratives"] == []
        assert state["parameter_sets"] == []
        assert state["execution_results"] == []
        assert state["errors"] == []

    def test_state_includes_serialized_config(self):
        from src.pipeline.config import PipelineConfig
        from src.scenarios.framework import (
            CriticalUncertainty,
            FocalIssue,
            ScenarioFramework,
            ScenarioMatrix,
        )

        framework = ScenarioFramework(
            focal_issue=FocalIssue(description="Test"),
            scenario_matrix=ScenarioMatrix(
                uncertainty_x=CriticalUncertainty(
                    name="X", description="X axis", pole_low="Low", pole_high="High",
                ),
                uncertainty_y=CriticalUncertainty(
                    name="Y", description="Y axis", pole_low="Low", pole_high="High",
                ),
            ),
        )

        config = PipelineConfig(num_scenarios=2)
        state = create_initial_state("Test", framework, config)

        assert state["config"]["num_scenarios"] == 2


class TestBuildPipelineGraph:
    def test_graph_builds_without_error(self):
        """Verify the graph can be constructed (node/edge consistency)."""
        builder = build_pipeline_graph()
        assert builder is not None

    def test_graph_has_expected_nodes(self):
        """Verify all pipeline nodes are present in the graph."""
        builder = build_pipeline_graph()
        # Access nodes from the builder
        node_names = set(builder.nodes.keys())

        expected_nodes = {
            "generate_scenarios",
            "review_scenarios",
            "extract_single_parameters",
            "review_parameters",
            "execute_commodity_model",
            "merge_upstream_into_commodity_downstream_params",
            "execute_commodity_downstream_model",
            "merge_upstream_into_macro_params",
            "execute_macro_model",
            "synthesize_results",
            "review_synthesis",
        }

        for node in expected_nodes:
            assert node in node_names, f"Missing node: {node}"
