"""Tests for scenario narrative schemas."""

import pytest
from pydantic import ValidationError

from src.common.types import Scenario
from src.scenarios.generator import require_scenario_count
from src.scenarios.schemas import QuantitativeAssumption, ScenarioNarrative, ScenarioSet


def test_scenario_narrative_construction():
    """Verify a scenario narrative can be constructed with all fields."""
    narrative = ScenarioNarrative(
        scenario_id=Scenario.A,
        label="Swift Resolution, Contained Conflict",
        description="Strait reopened in 4-6 weeks via naval escort + ceasefire.",
        narrative_timeline="Week 1: Mining of strait...",
        quantitative_assumptions=[
            QuantitativeAssumption(
                variable="oil_supply_loss",
                value="5",
                unit="mb/d",
                rationale="Based on historical transit volumes",
            ),
        ],
        consistency_notes="Timeline is consistent with historical precedent.",
    )

    assert narrative.scenario_id == Scenario.A
    assert len(narrative.quantitative_assumptions) == 1
    assert narrative.quantitative_assumptions[0].value == "5"


def test_scenario_set():
    """Verify a complete scenario set can be constructed."""
    scenario_set = ScenarioSet(
        crisis_description="Test crisis",
        scenarios=[
            ScenarioNarrative(
                scenario_id=scenario_id,
                label=f"Scenario {scenario_id.name}",
                description=f"Description for {scenario_id.name}",
                narrative_timeline=f"Timeline for {scenario_id.name}",
            )
            for scenario_id in Scenario
        ],
    )

    # 4 matrix quadrants (A-D) + 1 prescribed tail-risk (E: infrastructure_collapse)
    assert len(scenario_set.scenarios) == 5


@pytest.mark.parametrize("payload", [{"crisis_description": "x"}, {"crisis_description": "x", "scenarios": []}])
def test_scenario_set_rejects_empty_reply(payload):
    """A truncated structured reply must fail, not parse as zero scenarios."""
    with pytest.raises(ValidationError):
        ScenarioSet(**payload)


def _narrative(scenario_id):
    return ScenarioNarrative(scenario_id=scenario_id, label="l", description="d", narrative_timeline="t")


def test_require_scenario_count():
    """Module 1 raises on a partial set and accepts a complete one."""
    partial = ScenarioSet(crisis_description="x", scenarios=[_narrative(Scenario.A)])
    with pytest.raises(ValueError, match="1 of 5"):
        require_scenario_count(partial, 5)
    require_scenario_count(partial, 1)
