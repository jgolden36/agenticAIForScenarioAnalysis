"""The HTTP face of the adjudicator."""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.game.api import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["no_llm"] and body["as_of"] == "2026-11-08"


def test_models(client):
    rows = client.get("/models").json()
    assert any(r["model_id"] == "poles_jrc" for r in rows)


def test_baseline(client):
    body = client.get("/baseline").json()
    assert body["values"]["pre_crisis"]["oil_transit_mbd"] == 20.9
    assert any(r["path"] == "stocks.us_spr_inventory_mb" and r["status"] == "primary" for r in body["records"])


def test_adjudicate_round_trip(client):
    req = {"game_id": "demo", "turn": 2, "seed": 7,
           "world": {"transit_capacity_pct": 30, "escalation_rung": 6, "bypass_used_mbd": 4.0,
                     "stock_release_mbd": 2.0, "war_risk_premium_pct": 6.0, "weeks_elapsed": 1,
                     "expected_remaining_weeks": 7},
           "teams": {"US": {"region": "US"}, "GCC": {"region": "MENA_GCC"}}}
    r = client.post("/adjudicate", json=req)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok" and body["game_id"] == "demo" and body["turn"] == 2
    assert body["multipliers"]["oil"] > 1.0
    assert body["fallbacks"] == []
    assert set(body["macro_by_team"]) == {"US", "GCC"}
    assert body["provenance"][0].keys() >= {"model_id", "output_key", "value", "implementation_mode"}


def test_adjudicate_rejects_bad_world(client):
    r = client.post("/adjudicate", json={"game_id": "demo", "world": {"transit_capacity_pct": 140}})
    assert r.status_code == 422
