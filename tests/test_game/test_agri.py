"""The agricultural Tier 1 adjudicator: a Hormuz shock, a subsidy, a drought, a failing adapter."""
from __future__ import annotations

import time

import pytest

from src.game.agri import AgriAdjudicator
from src.game.agri_schemas import GAME_CROPS, AgriRoundRequest
from src.models.registry import build_default_registry

HORMUZ = {"gas_price_change_pct": 78.0, "middle_east_fertilizer_loss_pct": 30.0, "hormuz_transit_capacity_pct": 70.0,
          "fertilizer_price_change_pct": 45.0, "hormuz_component_pct": 39.0, "expected_shock_months": 6.0,
          "crop_price_change_pct": {"wheat": 12.0, "rice": 3.0, "maize": 8.0, "soybeans": -5.0}}
TEAMS = {"US": {"region": "US", "fertilizer_passthrough": 0.5},
         "BRA": {"region": "LAC", "fertilizer_passthrough": 0.9},
         "IND": {"region": "IND", "fertilizer_passthrough": 0.6, "fertilizer_subsidy_pct": 80.0,
                 "water_deficit_pct_by_crop": {"wheat": 40.0}},
         "ROW": {"region": "ROW", "fertilizer_passthrough": 0.6}}


def _req(world=None, teams=None, turn=2):
    return AgriRoundRequest.model_validate({"game_id": "g", "turn": turn, "world": world if world is not None else HORMUZ,
                                            "teams": teams if teams is not None else TEAMS})


@pytest.fixture(scope="module")
def adj():
    return AgriAdjudicator()


@pytest.fixture(scope="module")
def hormuz(adj):
    return adj.adjudicate(_req())


def test_hormuz_shock_raises_nitrogen_and_cuts_yields(hormuz):
    r = hormuz
    assert r.status == "ok" and r.no_llm and r.fallbacks == []
    assert r.fertilizer.source_model == "world_fertilizer"
    assert r.fertilizer.nitrogen_price_pct > 0
    assert r.fertilizer.implementation_mode == "analytical_reduction"
    # Tier 1 replaces the Hormuz part only; the 6 points from other causes stay
    assert r.fertilizer.world_change_pct == pytest.approx(r.fertilizer.nitrogen_price_pct + 6.0)
    assert r.farmgate_fertilizer_price_change_pct["BRA"] > r.farmgate_fertilizer_price_change_pct["US"] > 0
    assert r.application_reduction_pct["BRA"] == pytest.approx(0.35 * r.farmgate_fertilizer_price_change_pct["BRA"], rel=1e-3)
    for team in ("US", "BRA", "ROW"):
        assert set(r.yields[team]) == set(GAME_CROPS)
        assert all(r.yields[team][c].n_pct < 0 for c in GAME_CROPS)
        assert all(r.yields[team][c].water_pct == 0.0 for c in GAME_CROPS)
    # the legume loses less than the cereals to a nitrogen cut
    assert r.yields["BRA"]["soybeans"].n_pct > r.yields["BRA"]["maize"].n_pct
    assert set(r.macro_by_team) == set(TEAMS)
    assert r.macro_by_team["BRA"].region == "LAC"
    assert set(r.forward_curves) == {"wheat", "rice", "maize", "soybeans", "urea"}
    assert r.forward_curves["wheat"][0] == pytest.approx(1.12)
    assert r.forward_curves["soybeans"][0] == pytest.approx(0.95)
    assert all(p.implementation_mode == "analytical_reduction" for p in r.provenance)
    assert {p.model_id for p in r.provenance} >= {"world_fertilizer", "apsim", "futures", "macro_kernel"}


def test_bridge_is_recorded(hormuz):
    bridge = [o for o in hormuz.overrides if o["name"] == "fertilizer_application_reduction_pct"]
    assert {o["target_key"] for o in bridge} == set(TEAMS)
    assert all(o["transform"] == "price_to_demand_reduction" and o["elasticity"] == 0.35 for o in bridge)
    assert hormuz.derived["bridge"]["source"].endswith("upstream_forwarding_mapping.yaml")
    hz = next(o for o in hormuz.overrides if o["name"] == "hormuz_component_pct")
    assert hz["game_value"] == 39.0 and hz["computed_value"] == pytest.approx(hormuz.fertilizer.nitrogen_price_pct)


def test_subsidy_80_means_no_cut(hormuz):
    assert hormuz.farmgate_fertilizer_price_change_pct["IND"] < 0
    assert hormuz.application_reduction_pct["IND"] == 0.0
    assert all(hormuz.yields["IND"][c].n_pct == 0.0 for c in GAME_CROPS)


def test_drought_gives_a_water_loss_for_that_crop_only(hormuz):
    assert hormuz.yields["IND"]["wheat"].water_pct < 0
    assert hormuz.yields["IND"]["rice"].water_pct == 0.0
    labels = [x.label for x in hormuz.runs if x.model_id == "apsim"]
    assert "IND:water:wheat" in labels and "IND:nitrogen" in labels


def test_no_hormuz_skips_world_fertilizer_and_uses_the_game_number(adj):
    world = {"fertilizer_price_change_pct": 20.0, "crop_price_change_pct": {"wheat": 5.0}}
    r = adj.adjudicate(_req(world=world))
    assert all(x.model_id != "world_fertilizer" for x in r.runs)
    assert r.fertilizer.source_model == "game" and r.fertilizer.nitrogen_price_pct is None
    assert r.fertilizer.world_change_pct == 20.0
    assert r.farmgate_fertilizer_price_change_pct["US"] == pytest.approx(10.0)
    assert set(r.forward_curves) == {"wheat", "urea"}
    assert r.fallbacks == []


def test_quiet_world_is_calm_and_fast(adj):
    t = time.perf_counter()
    r = adj.adjudicate(_req(world={}, teams={"US": {"region": "US"}}))
    assert time.perf_counter() - t < 2.0
    assert r.application_reduction_pct == {"US": 0.0}
    assert all(r.yields["US"][c].n_pct == 0.0 for c in GAME_CROPS)


class _Boom:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def execute(self, inputs):
        raise RuntimeError("boom")


def test_failing_world_fertilizer_is_a_fallback():
    registry = build_default_registry(None)
    registry._adapters["world_fertilizer"] = _Boom(registry.get("world_fertilizer"))  # noqa: SLF001
    r = AgriAdjudicator(registry).adjudicate(_req())
    assert [f.model_id for f in r.fallbacks] == ["world_fertilizer"]
    assert r.fertilizer.source_model == "game"
    assert r.fertilizer.world_change_pct == 45.0     # the game's own number, all components
    assert all(r.yields["US"][c].n_pct < 0 for c in GAME_CROPS)


def test_failing_apsim_leaves_yields_unknown_not_zero():
    registry = build_default_registry(None)
    registry._adapters["apsim"] = _Boom(registry.get("apsim"))  # noqa: SLF001
    r = AgriAdjudicator(registry).adjudicate(_req())
    assert r.status == "ok"
    assert all(r.yields["US"][c].n_pct is None for c in GAME_CROPS)
    assert r.yields["IND"]["wheat"].water_pct is None
    assert {f.model_id for f in r.fallbacks} == {"apsim"}


def test_request_rejects_unknown_crops():
    with pytest.raises(ValueError):
        AgriRoundRequest.model_validate({"game_id": "g", "world": {"crop_price_change_pct": {"barley": 3.0}}})
    with pytest.raises(ValueError):
        AgriRoundRequest.model_validate({"game_id": "g", "teams": {"US": {"water_deficit_pct_by_crop": {"wheat": 120}}}})


def test_models_listing(adj):
    ids = [r["model_id"] for r in adj.models()]
    assert ids == ["world_fertilizer", "apsim", "futures", "macro_kernel"]


fastapi = pytest.importorskip("fastapi")


def test_api_round_trip():
    from fastapi.testclient import TestClient

    from src.game.api import create_app

    with TestClient(create_app()) as c:
        body = c.post("/adjudicate/agri", json=_req().model_dump()).json()
        assert body["status"] == "ok" and body["no_llm"]
        assert body["yields"]["BRA"]["maize"]["n_pct"] < 0
        assert body["fertilizer"]["source_model"] == "world_fertilizer"
        assert [r["model_id"] for r in c.get("/models/agri").json()][-1] == "macro_kernel"
        base = c.get("/baseline/agri").json()
        assert base["baseline_id"] == "agri_2027_game" and base["bridge"]["elasticity"] == 0.35
        assert all(r["status"] == "designer" for r in base["records"])
        assert "agri" in c.get("/healthz").json()["modules"]
        bad = c.post("/adjudicate/agri", json={"game_id": "g", "world": {"middle_east_fertilizer_loss_pct": 140}})
        assert bad.status_code == 422
