"""Pydantic schemas for scenario narratives."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.common.types import Scenario


class QuantitativeAssumption(BaseModel):
    """A single quantitative assumption within a scenario narrative."""

    variable: str
    value: str
    unit: str | None = None
    rationale: str = ""


class ScenarioNarrative(BaseModel):
    """A fully specified scenario narrative produced by Module 1.

    Each narrative describes one quadrant of the scenario matrix with
    enough quantitative detail for Module 2 (parameter extraction).
    """

    scenario_id: Scenario
    label: str
    description: str
    narrative_timeline: str
    quantitative_assumptions: list[QuantitativeAssumption] = Field(
        default_factory=list
    )
    consistency_notes: str = ""


class ScenarioSet(BaseModel):
    """The complete set of generated scenario narratives."""

    crisis_description: str
    scenarios: list[ScenarioNarrative] = Field(default_factory=list)
