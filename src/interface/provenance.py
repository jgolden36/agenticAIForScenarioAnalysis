"""Provenance tracking (Module 5).

Traces any synthesized result back through the full chain:
synthesis → model output → model input → extracted parameter → scenario narrative.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.common.types import Scenario
from src.pipeline.state import PipelineState


class ProvenanceRecord(BaseModel):
    """Full provenance chain for a single synthesized result."""

    scenario_id: Scenario
    outcome_variable: str
    source_model_id: str

    # From synthesis
    synthesized_value: Any = None
    narrative_summary: str = ""

    # From model execution
    model_outputs: dict[str, Any] = Field(default_factory=dict)
    model_runtime_seconds: float | None = None

    # From parameter extraction
    model_inputs: dict[str, Any] = Field(default_factory=dict)
    parameter_confidence: dict[str, str] = Field(default_factory=dict)

    # From scenario narrative
    scenario_label: str = ""
    scenario_narrative_excerpt: str = ""
    relevant_assumptions: dict[str, Any] = Field(default_factory=dict)


class ProvenanceTracker:
    """Builds provenance records by tracing through the pipeline state."""

    def __init__(self, state: PipelineState) -> None:
        self.state = state

    def trace(
        self,
        scenario_id: Scenario,
        model_id: str,
        outcome_variable: str,
    ) -> ProvenanceRecord:
        """Trace a single result back through the full pipeline.

        Args:
            scenario_id: Which scenario.
            model_id: Which model produced the result.
            outcome_variable: Which output variable to trace.

        Returns:
            A ProvenanceRecord with all available chain links populated.
        """
        record = ProvenanceRecord(
            scenario_id=scenario_id,
            outcome_variable=outcome_variable,
            source_model_id=model_id,
        )

        # Trace to model execution
        exec_result = self.state.get_execution_result(scenario_id, model_id)
        if exec_result:
            record.model_outputs = exec_result.outputs
            record.model_runtime_seconds = exec_result.runtime_seconds
            if outcome_variable in exec_result.outputs:
                record.synthesized_value = exec_result.outputs[outcome_variable]

        # Trace to parameter extraction
        params = self.state.get_parameters(scenario_id, model_id)
        if params:
            record.model_inputs = {
                p.name: p.value for p in params.parameters
            }
            record.parameter_confidence = {
                p.name: p.confidence.value for p in params.parameters
            }

        # Trace to scenario narrative
        narrative = self.state.get_narrative(scenario_id)
        if narrative:
            record.scenario_label = narrative.label
            record.scenario_narrative_excerpt = narrative.narrative[:500]
            record.relevant_assumptions = narrative.quantitative_assumptions

        return record

    def trace_all_for_scenario(
        self, scenario_id: Scenario
    ) -> list[ProvenanceRecord]:
        """Build provenance records for all results in a scenario."""
        records = []
        results = self.state.get_results_for_scenario(scenario_id)
        for result in results:
            for variable in result.outputs:
                records.append(
                    self.trace(scenario_id, result.model_id, variable)
                )
        return records
