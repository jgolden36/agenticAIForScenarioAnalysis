"""Pipeline state management.

This state container is passed through the pipeline and accumulates results
at each stage. It provides full provenance tracking from scenarios through
to final synthesis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import (
    ConfidenceLevel,
    ModelExecutionStatus,
    Scenario,
    ValidationStatus,
)


class ParameterValue(BaseModel):
    """A single extracted parameter with metadata."""

    name: str
    value: Any
    unit: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    extraction_note: str | None = None


class ModelParameterSet(BaseModel):
    """Extracted parameters for a specific (scenario, model) pair."""

    scenario_id: Scenario
    model_id: str
    parameters: list[ParameterValue] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validated_at: datetime | None = None


class ModelExecutionResult(BaseModel):
    """Result of a single domain model execution.

    The optional ``uncertainty`` field carries per-output quantiles
    (mean / std / p05-p95) when uncertainty quantification is enabled
    via ``UncertaintyConfig``. It is populated by either the adapter
    itself (native UQ — preferred) or the executor's perturbation
    wrapper (``src.models.uncertainty``).
    """

    scenario_id: Scenario
    model_id: str
    status: ModelExecutionStatus = ModelExecutionStatus.PENDING
    outputs: dict[str, Any] = Field(default_factory=dict)
    runtime_seconds: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stdout: str | None = None
    stderr: str | None = None
    uncertainty: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Serialized UncertaintyReport (see src.models.base). "
            "None when UQ was not performed."
        ),
    )


class ConsistencyFlag(BaseModel):
    """A flagged inconsistency between model outputs."""

    scenario_id: Scenario
    model_a_id: str
    model_b_id: str
    variable: str
    value_a: Any
    value_b: Any
    tolerance_pct: float
    deviation_pct: float
    message: str


class ScenarioNarrativeState(BaseModel):
    """State tracking for a generated scenario narrative."""

    scenario_id: Scenario
    label: str = ""
    narrative: str = ""
    quantitative_assumptions: dict[str, Any] = Field(default_factory=dict)
    consistency_notes: str = ""
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validated_at: datetime | None = None


class SynthesisResult(BaseModel):
    """Structured synthesis output."""

    scenario_id: Scenario
    time_horizon: str
    outcome_scope: str
    outcome_variable: str
    value: Any
    unit: str | None = None
    source_model_id: str
    narrative_summary: str = ""


class PipelineState(BaseModel):
    """Central state container for the full pipeline run.

    Accumulates results as each module executes and provides
    the provenance chain from scenarios through synthesis.
    """

    run_id: str = ""
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    crisis_description: str = ""

    # Module 1: Scenario narratives
    scenario_narratives: list[ScenarioNarrativeState] = Field(
        default_factory=list
    )
    scenarios_validated: bool = False

    # Module 2: Extracted parameters
    parameter_sets: list[ModelParameterSet] = Field(default_factory=list)
    parameters_validated: bool = False

    # Module 3: Model execution results
    execution_results: list[ModelExecutionResult] = Field(default_factory=list)

    # Module 4: Consistency checks and synthesis
    consistency_flags: list[ConsistencyFlag] = Field(default_factory=list)
    synthesis_results: list[SynthesisResult] = Field(default_factory=list)
    synthesis_validated: bool = False

    # Metadata
    completed_at: datetime | None = None
    errors: list[str] = Field(default_factory=list)

    def get_narrative(self, scenario_id: Scenario) -> ScenarioNarrativeState | None:
        """Get the narrative for a specific scenario."""
        for n in self.scenario_narratives:
            if n.scenario_id == scenario_id:
                return n
        return None

    def get_parameters(
        self, scenario_id: Scenario, model_id: str
    ) -> ModelParameterSet | None:
        """Get extracted parameters for a (scenario, model) pair."""
        for ps in self.parameter_sets:
            if ps.scenario_id == scenario_id and ps.model_id == model_id:
                return ps
        return None

    def get_execution_result(
        self, scenario_id: Scenario, model_id: str
    ) -> ModelExecutionResult | None:
        """Get the execution result for a (scenario, model) pair."""
        for er in self.execution_results:
            if er.scenario_id == scenario_id and er.model_id == model_id:
                return er
        return None

    def get_results_for_scenario(
        self, scenario_id: Scenario
    ) -> list[ModelExecutionResult]:
        """Get all execution results for a scenario."""
        return [
            er for er in self.execution_results if er.scenario_id == scenario_id
        ]

    def get_successful_results(self) -> list[ModelExecutionResult]:
        """Get all successfully completed execution results."""
        return [
            er
            for er in self.execution_results
            if er.status == ModelExecutionStatus.COMPLETED
        ]
