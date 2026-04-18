"""Tests for the Schwartz scenario framework data structures."""

from src.scenarios.framework import (
    CriticalUncertainty,
    FocalIssue,
    ScenarioFramework,
    ScenarioMatrix,
)


def test_scenario_matrix_quadrants():
    """Verify the 2x2 matrix produces four correct quadrants."""
    matrix = ScenarioMatrix(
        uncertainty_x=CriticalUncertainty(
            name="Duration",
            description="How long the Strait is closed",
            pole_low="Swift (4-6 weeks)",
            pole_high="Prolonged (3-6+ months)",
        ),
        uncertainty_y=CriticalUncertainty(
            name="Escalation",
            description="Scope of conflict",
            pole_low="Contained",
            pole_high="Escalated",
        ),
    )

    quadrants = matrix.quadrants
    assert len(quadrants) == 4

    labels = [q["label"] for q in quadrants]
    assert labels == ["A", "B", "C", "D"]

    # Scenario A: swift + contained
    assert quadrants[0]["x"] == "Swift (4-6 weeks)"
    assert quadrants[0]["y"] == "Contained"

    # Scenario D: prolonged + escalated
    assert quadrants[3]["x"] == "Prolonged (3-6+ months)"
    assert quadrants[3]["y"] == "Escalated"


def test_scenario_framework_construction():
    """Verify framework can be constructed with all components."""
    framework = ScenarioFramework(
        focal_issue=FocalIssue(
            description="Test focal issue", time_horizon="1 year"
        ),
        scenario_matrix=ScenarioMatrix(
            uncertainty_x=CriticalUncertainty(
                name="X", description="X axis",
                pole_low="Low", pole_high="High",
            ),
            uncertainty_y=CriticalUncertainty(
                name="Y", description="Y axis",
                pole_low="Low", pole_high="High",
            ),
        ),
    )

    assert framework.focal_issue.description == "Test focal issue"
    assert len(framework.scenario_matrix.quadrants) == 4
