"""Tests for the Schwartz scenario framework data structures."""

from pathlib import Path

import yaml

from src.common.types import Scenario
from src.scenarios.framework import (
    CriticalUncertainty,
    FocalIssue,
    PrescribedScenario,
    ScenarioFramework,
    ScenarioMatrix,
)
from src.scenarios.generator import _format_framework_inputs


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
    # No additional_scenarios by default — framework stays a pure 2x2.
    assert framework.additional_scenarios == []
    assert framework.total_scenarios == 4


def _minimal_matrix() -> ScenarioMatrix:
    return ScenarioMatrix(
        uncertainty_x=CriticalUncertainty(
            name="X", description="X axis",
            pole_low="Low", pole_high="High",
        ),
        uncertainty_y=CriticalUncertainty(
            name="Y", description="Y axis",
            pole_low="Low", pole_high="High",
        ),
    )


def test_additional_scenarios_extend_total_count():
    """Prescribed scenarios are appended to the matrix quadrants."""
    framework = ScenarioFramework(
        focal_issue=FocalIssue(description="F", time_horizon="1y"),
        scenario_matrix=_minimal_matrix(),
        additional_scenarios=[
            PrescribedScenario(
                scenario_id="infrastructure_collapse",
                label="Infrastructure Collapse (Tail Risk)",
                summary="Worst case with infrastructure destruction.",
                narrative_seeds=[
                    "Desal capacity reduced 60-80%.",
                    "Qatari LNG exports drop to 30-40% for 18-24 months.",
                ],
            )
        ],
    )

    assert len(framework.additional_scenarios) == 1
    assert framework.total_scenarios == 5  # 4 quadrants + 1 prescribed
    ps = framework.additional_scenarios[0]
    assert ps.scenario_id == "infrastructure_collapse"
    # Every prescribed scenario_id must resolve to a Scenario enum value
    # so downstream pipeline state typing succeeds.
    assert Scenario(ps.scenario_id) is Scenario.E


def test_format_framework_inputs_renders_additional_scenarios():
    """The generator's prompt formatter must surface additional scenarios."""
    framework = ScenarioFramework(
        focal_issue=FocalIssue(description="F", time_horizon="1y"),
        scenario_matrix=_minimal_matrix(),
        additional_scenarios=[
            PrescribedScenario(
                scenario_id="infrastructure_collapse",
                label="Infrastructure Collapse (Tail Risk)",
                summary="Severe damage to desalination + LNG + oil terminals.",
                narrative_seeds=[
                    "Desalination capacity reduced 60-80%.",
                    "Qatari LNG export complex damaged for 18-24 months.",
                ],
            )
        ],
    )

    out = _format_framework_inputs({
        "framework": framework,
        "crisis_description": "test crisis",
    })

    # Default num_scenarios is derived from the framework
    assert out["num_scenarios"] == 5
    block = out["additional_scenarios"]
    assert "infrastructure_collapse" in block
    assert "Infrastructure Collapse (Tail Risk)" in block
    assert "Desalination capacity reduced 60-80%." in block
    assert "Qatari LNG export complex damaged for 18-24 months." in block
    # Caller-supplied num_scenarios still wins when explicitly provided
    out2 = _format_framework_inputs({
        "framework": framework,
        "crisis_description": "test crisis",
        "num_scenarios": 7,
    })
    assert out2["num_scenarios"] == 7


def test_hormuz_2026_yaml_includes_infrastructure_collapse():
    """The shipped Hormuz framework YAML carries the tail-risk scenario."""
    path = (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "scenario_frameworks"
        / "hormuz_2026.yaml"
    )
    with open(path) as f:
        data = yaml.safe_load(f)

    framework = ScenarioFramework(**data)
    assert framework.total_scenarios == 5

    ids = [ps.scenario_id for ps in framework.additional_scenarios]
    assert "infrastructure_collapse" in ids

    collapse = next(
        ps for ps in framework.additional_scenarios
        if ps.scenario_id == "infrastructure_collapse"
    )
    # Sanity-check that the seeds carry the three damage axes the
    # downstream water / LNG / oil adapters need to see in the
    # generated narrative.
    seed_text = " | ".join(collapse.narrative_seeds).lower()
    assert "desalination" in seed_text
    assert "lng" in seed_text or "ras laffan" in seed_text
    assert "oil" in seed_text or "ras tanura" in seed_text
