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


class PrescribedScenario(BaseModel):
    """A scenario prescribed outside the 2x2 matrix.

    Schwartz scenario planning treats the 2x2 matrix as the analytic
    backbone, but real crisis assessments routinely add a small number
    of *prescribed* scenarios -- tail-risk cases, reference baselines,
    or "stress tests" that fix specific parameter values to probe
    sensitivity. ``PrescribedScenario`` lets the framework spec carry
    those alongside the matrix quadrants.

    The ``scenario_id`` must match a value in ``src.common.types.Scenario``
    (e.g. ``"infrastructure_collapse"``). ``narrative_seeds`` are short,
    high-priority facts the LLM must incorporate verbatim into the
    generated narrative -- they are how we force, for example, the
    "desalination plants destroyed" assumption into Module 1's output
    so it survives parameter extraction in Module 2.
    """

    scenario_id: str = Field(
        description=(
            "String identifier matching a value in src.common.types.Scenario. "
            "Used by downstream pipeline components to thread the scenario "
            "through parameter extraction, model execution, and synthesis."
        ),
    )
    label: str = Field(description="Short descriptive name for the scenario.")
    summary: str = Field(
        default="",
        description="One-paragraph summary of what makes this scenario distinct.",
    )
    narrative_seeds: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete facts / parameter targets the generated narrative MUST "
            "incorporate (e.g. 'desalination capacity reduced 60-80%'). These "
            "are passed verbatim to the scenario-generation prompt so the "
            "downstream parameter extractor sees them in the narrative."
        ),
    )


class ScenarioFramework(BaseModel):
    """Complete Schwartz scenario framework specification.

    This is the structured input to Module 1 (scenario generation).

    The scenario set ultimately produced by Module 1 is the union of
    the 2x2 matrix quadrants (always 4) and any ``additional_scenarios``
    declared in the framework YAML. ``additional_scenarios`` is the
    extension point for tail-risk / reference / stress-test cases that
    don't sit naturally on the matrix axes.
    """

    focal_issue: FocalIssue
    key_factors: list[KeyFactor] = Field(default_factory=list)
    driving_forces: list[DrivingForce] = Field(default_factory=list)
    predetermined_elements: list[PredeterminedElement] = Field(
        default_factory=list
    )
    scenario_matrix: ScenarioMatrix
    additional_scenarios: list[PrescribedScenario] = Field(
        default_factory=list,
        description=(
            "Prescribed scenarios outside the 2x2 matrix (tail-risk, "
            "reference, or stress-test cases). Each must have a "
            "scenario_id that matches a value in src.common.types.Scenario."
        ),
    )

    @property
    def total_scenarios(self) -> int:
        """Total scenario count = matrix quadrants + additional scenarios."""
        return len(self.scenario_matrix.quadrants) + len(self.additional_scenarios)
