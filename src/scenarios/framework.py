"""Data structures for the Schwartz scenario framework."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FocalIssue(BaseModel):
    """The central question the scenario exercise addresses."""

    description: str
    time_horizon: str = ""


class KeyFactor(BaseModel):
    """A key factor in the local environment relevant to the focal issue."""

    name: str
    description: str
    category: str = ""


class DrivingForce(BaseModel):
    """A macro-level driving force (STEEP dimensions).

    STEEP: Social, Technological, Economic, Environmental, Political.
    """

    name: str
    description: str
    dimension: str  # One of: social, technological, economic, environmental, political


class PredeterminedElement(BaseModel):
    """A locked-in factor that appears in all scenarios regardless of uncertainty resolution."""

    name: str
    description: str
    value: str | None = None


class CriticalUncertainty(BaseModel):
    """An axis of the scenario matrix — a high-impact, high-uncertainty factor."""

    name: str
    description: str
    pole_low: str
    pole_high: str


class ScenarioMatrix(BaseModel):
    """The 2x2 scenario matrix defined by two critical uncertainties.

    Generates four scenario quadrants from the cross-product of two
    uncertainty axes, each with a low and high pole.
    """

    uncertainty_x: CriticalUncertainty
    uncertainty_y: CriticalUncertainty

    @property
    def quadrants(self) -> list[dict[str, str]]:
        """Return the four quadrant labels."""
        return [
            {
                "label": "A",
                "x": self.uncertainty_x.pole_low,
                "y": self.uncertainty_y.pole_low,
            },
            {
                "label": "B",
                "x": self.uncertainty_x.pole_high,
                "y": self.uncertainty_y.pole_low,
            },
            {
                "label": "C",
                "x": self.uncertainty_x.pole_low,
                "y": self.uncertainty_y.pole_high,
            },
            {
                "label": "D",
                "x": self.uncertainty_x.pole_high,
                "y": self.uncertainty_y.pole_high,
            },
        ]


class ScenarioFramework(BaseModel):
    """Complete Schwartz scenario framework specification.

    This is the structured input to Module 1 (scenario generation).
    """

    focal_issue: FocalIssue
    key_factors: list[KeyFactor] = Field(default_factory=list)
    driving_forces: list[DrivingForce] = Field(default_factory=list)
    predetermined_elements: list[PredeterminedElement] = Field(
        default_factory=list
    )
    scenario_matrix: ScenarioMatrix
