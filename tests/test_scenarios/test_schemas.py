"""Tests for scenario narrative schemas."""

from src.common.types import Scenario
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

    assert len(scenario_set.scenarios) == 4
