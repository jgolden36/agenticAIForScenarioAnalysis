"""The Tier 1 adjudicator: a closed strait, an open strait, and a failing adapter."""
from __future__ import annotations

import time

import pytest

from src.game import Adjudicator, RoundRequest
from src.game.schemas import TeamSpec, WorldState
from src.models.registry import build_default_registry

CLOSED = WorldState(transit_capacity_pct=20, mine_density=0.5, escalation_rung=6, qatar_damaged_share=0.17,
                    bypass_used_mbd=4.0, stock_release_mbd=2.0, war_risk_premium_pct=5.0,
                    weeks_elapsed=2, expected_remaining_weeks=6)


@pytest.fixture(scope="module")
def adjudicator():
    return Adjudicator()


def test_closed_strait(adjudicator):
    t = time.perf_counter()
    r = adjudicator.adjudicate(RoundRequest(game_id="g", turn=3, world=CLOSED))
    assert time.perf_counter() - t < 2.0
    assert r.status == "ok" and r.no_llm
    assert r.fallbacks == []
    assert r.scenario_label == "prolonged_escalated"
    assert r.multipliers["oil"] > 1.3
    assert r.multipliers["diesel"] > r.multipliers["oil"]
    assert r.peak_multipliers["oil"] >= r.multipliers["oil"]
    assert 1.1 <= r.lane.rerouting_cost_multiplier <= 2.0
    assert r.lane.effective_fleet_capacity_loss_pct > 10
    assert {p.model_id for p in r.provenance} >= {"poles_jrc", "lngst", "world_helium_model", "world_fertilizer",
                                                  "aisdb", "ais_project", "marketsim", "fed_oil", "macro_kernel"}
    assert len(r.provenance) >= 9
    assert all(p.implementation_mode == "analytical_reduction" for p in r.provenance)
    # six baseline teams, GCC gains as an exporter
    assert set(r.macro_by_team) == {"US", "CHN", "EU", "GCC", "IND", "JPK"}
    assert r.macro_by_team["GCC"].gdp_impact_pct > 0 > r.macro_by_team["IND"].gdp_impact_pct
    assert r.macro_by_team["JPK"].region == "ROW"
    # forwarding happened and was recorded, with the game's premium left alone
    names = {o["name"] for o in r.overrides}
    assert "rerouting_cost_multiplier" in names
    assert "natural_gas_price_change_pct" in names
    assert "initial_price_shock_pct" in names
    assert "insurance_premium_increase_pct" not in names
    poles = next(x for x in r.runs if x.model_id == "poles_jrc")
    assert poles.inputs["insurance_premium_increase_pct"] == pytest.approx(1900.0)


def test_open_strait(adjudicator):
    r = adjudicator.adjudicate(RoundRequest(game_id="g", turn=1, world=WorldState()))
    assert r.fallbacks == []
    assert all(abs(m - 1.0) < 0.01 for m in r.multipliers.values())
    assert r.lane.rerouting_cost_multiplier == pytest.approx(1.0)


def test_ramp_rises_with_weeks(adjudicator):
    w1 = CLOSED.model_copy(update={"weeks_elapsed": 0})
    w4 = CLOSED.model_copy(update={"weeks_elapsed": 5})
    r1 = adjudicator.adjudicate(RoundRequest(game_id="g", turn=1, world=w1))
    r4 = adjudicator.adjudicate(RoundRequest(game_id="g", turn=6, world=w4))
    assert r1.multipliers["oil"] < r4.multipliers["oil"]
    assert r4.multipliers["oil"] == pytest.approx(r4.peak_multipliers["oil"])


def test_team_regions_from_request(adjudicator):
    r = adjudicator.adjudicate(RoundRequest(game_id="g", turn=1, world=CLOSED,
                                            teams={"A": TeamSpec(region="US"), "B": TeamSpec(region="MENA_GCC")}))
    assert set(r.macro_by_team) == {"A", "B"}


def test_infrastructure_collapse_label(adjudicator):
    w = CLOSED.model_copy(update={"qatar_damaged_share": 0.4})
    r = adjudicator.adjudicate(RoundRequest(game_id="g", turn=1, world=w))
    assert r.scenario_label == "infrastructure_collapse"


class _Boom:
    """An adapter whose execute() raises, wrapped around the real one."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def execute(self, inputs):
        raise RuntimeError("boom")


def test_one_failing_adapter_is_a_fallback_not_an_error():
    registry = build_default_registry(None)
    registry._adapters["lngst"] = _Boom(registry.get("lngst"))  # noqa: SLF001
    r = Adjudicator(registry).adjudicate(RoundRequest(game_id="g", turn=1, world=CLOSED))
    assert [f.model_id for f in r.fallbacks] == ["lngst"]
    assert "lng" not in r.multipliers
    assert r.multipliers["oil"] > 1.3
    lng_run = next(x for x in r.runs if x.model_id == "lngst")
    assert lng_run.status == "failed" and "boom" in lng_run.error


def test_models_listing(adjudicator):
    rows = adjudicator.models()
    ids = [r["model_id"] for r in rows]
    assert ids[:2] == ["aisdb", "ais_project"] and ids[-1] == "macro_kernel"
    assert all(r["registered"] for r in rows)
    assert {r["mode_when_executed"] for r in rows} == {"analytical_reduction"}
