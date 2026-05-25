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


class TestExecuteNodeUncertainty:
    """The per-model LangGraph node must thread UQ onto its result entry
    when the (serialized) config enables uncertainty quantification."""

    def _linear_registry(self):
        from src.common.types import AnalyticalLevel, CommoditySystem
        from src.models.base import ModelAdapter, ModelOutput, ValidationResult
        from src.models.registry import ModelRegistry

        class _LinearAdapter(ModelAdapter):
            @property
            def model_id(self):
                return "linear_node_adapter"

            @property
            def commodity_system(self):
                return CommoditySystem.OIL

            @property
            def analytical_level(self):
                return AnalyticalLevel.COMMODITY

            @property
            def description(self):
                return "linear node test adapter"

            def validate_inputs(self, params):
                return ValidationResult(valid=True)

            def translate_inputs(self, params):
                return params

            def execute(self, inputs):
                return ModelOutput(
                    model_id=self.model_id,
                    outputs={"y": 2.0 * float(inputs["x"]) + 5.0},
                )

            def parse_outputs(self, raw):
                return raw

        reg = ModelRegistry()
        reg.register(_LinearAdapter())
        return reg

    def _state(self, enabled: bool):
        from src.common.types import Scenario
        from src.models.uncertainty import UncertaintyConfig
        from src.pipeline.config import PipelineConfig

        config = PipelineConfig(
            uncertainty=UncertaintyConfig(
                enabled=enabled,
                method="perturbation",
                n_replicates=8,
                perturbation_pct=10.0,
                seed=7,
            )
        )
        return {
            "current_scenario_id": Scenario.A.value,
            "current_model_id": "linear_node_adapter",
            "current_params": {"x": 100.0},
            "current_upstream_overrides": [],
            "config": config.model_dump(mode="json"),
        }

    def test_node_populates_uncertainty_when_enabled(self, monkeypatch):
        import src.pipeline.graph as graph

        reg = self._linear_registry()
        monkeypatch.setattr(graph, "build_default_registry", lambda *a, **k: reg)

        out = graph._execute_one_model_node(self._state(enabled=True))
        entry = out["execution_results"][0]

        assert entry["status"] == "completed"
        assert entry["outputs"]["y"] == 205.0
        assert "uncertainty" in entry
        assert entry["uncertainty"]["method"] == "perturbation"
        q = entry["uncertainty"]["estimates"]["y"]["quantiles"]
        assert q["p05"] < q["p95"]

    def test_node_omits_uncertainty_when_disabled(self, monkeypatch):
        import src.pipeline.graph as graph

        reg = self._linear_registry()
        monkeypatch.setattr(graph, "build_default_registry", lambda *a, **k: reg)

        out = graph._execute_one_model_node(self._state(enabled=False))
        entry = out["execution_results"][0]

        assert entry["status"] == "completed"
        assert "uncertainty" not in entry


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
