"""Pydantic schemas for synthesis output (Module 4)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.common.types import OutcomeScope, Scenario, TimeHorizon


class SynthesizedOutcome(BaseModel):
    """A single synthesized outcome variable."""

    variable: str
    value: str
    unit: str | None = None
    source_model_id: str
    narrative: str = ""
    reliability_note: str = ""


class ScopedSynthesis(BaseModel):
    """Synthesis for a specific (time_horizon, outcome_scope) pair."""

    time_horizon: TimeHorizon
    outcome_scope: OutcomeScope
    outcomes: list[SynthesizedOutcome] = Field(default_factory=list)


class ScenarioSynthesis(BaseModel):
    """Complete synthesis for a single scenario."""

    scenario_id: Scenario
    scenario_label: str
    sections: list[ScopedSynthesis] = Field(default_factory=list)
    failed_models: list[str] = Field(default_factory=list)
    consistency_warnings: list[str] = Field(default_factory=list)


class FullSynthesis(BaseModel):
    """Complete synthesis across all scenarios."""

    scenarios: list[ScenarioSynthesis] = Field(default_factory=list)
    cross_scenario_notes: str = ""
