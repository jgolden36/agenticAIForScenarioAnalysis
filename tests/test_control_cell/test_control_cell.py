"""The control-cell LLM tools with a fake LLM: validation, ids, the unavailable path, the API."""
from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableLambda

from src.control_cell.cards import card_id, check_deck, draft_cards
from src.control_cell.llm_call import LLMHandle, LLMUnavailable
from src.control_cell.novel import extract_novel
from src.control_cell.schemas import CardDeck, CardsRequest, NovelRequest
from src.control_cell.validate import validate_fields

TEAMS = ["US", "CHN", "EU", "BRA", "RUS", "IND", "MENA", "ROW"]
CROPS = ["wheat", "rice", "maize", "soybeans"]
SEATS = ["US", "CHN", "EU", "BRA", "RUS", "IND", "MENA"]

MENU = {
    "drought": {"label": "Drought", "fields": {"team": {"options": TEAMS}, "crop": {"options": CROPS + ["ALL"]},
                                                "a": {"name": "water_deficit_pct", "min": 5, "max": 90}}},
    "crop_disease": {"label": "Crop disease", "fields": {"team": {"options": TEAMS}, "crop": {"options": CROPS},
                                                         "a": {"name": "severity_pct", "min": 5, "max": 80},
                                                         "b": {"name": "infected_share", "min": 0.01, "max": 1.0},
                                                         "text": {"name": "pathogen", "required": True}}},
    "hormuz_shock": {"label": "Hormuz shock", "fields": {"a": {"name": "transit_capacity_pct", "min": 0, "max": 100},
                                                         "b": {"name": "qatar_damaged_share", "min": 0, "max": 1,
                                                               "required": False}}},
    "news": {"label": "News", "fields": {"text": {"name": "text"}}},
}
ORDER_MENU = {
    "import_tariff": {"label": "Import tariff", "fields": {"crop": {"options": CROPS}, "partner": {"options": SEATS + ["ALL"]},
                                                           "a": {"name": "pct", "min": 1, "max": 200}}},
    "export_ban": {"label": "Export ban", "fields": {"crop": {"options": CROPS}}},
    "buy_stocks": {"label": "Buy stocks", "fields": {"crop": {"options": CROPS}, "a": {"name": "mt", "min": 0.1, "max": 20}}},
}
STATE = {"teams": TEAMS, "crops": CROPS, "growing": {"IND": ["wheat"], "US": ["maize", "soybeans"]},
         "main_suppliers": {"MENA": {"wheat": ["RUS", "EU"]}}}


class FakeLLM:
    """Stands in for a chat model: ``with_structured_output`` returns a RunnableLambda that records
    the rendered messages and answers with a canned object."""

    def __init__(self, answer, model="fake-model"):
        self.answer = answer
        self.model = model
        self.calls = []

    def with_structured_output(self, schema):
        def _invoke(messages):
            self.calls.append({"schema": schema.__name__, "messages": messages})
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer
        return RunnableLambda(_invoke)


def _handle(answer):
    return LLMHandle(llm=FakeLLM(answer), provider="fake", model="fake-model", temperature=0.4)


GOOD = {"move": "drought", "category": "harvest", "fields": {"team": "IND", "crop": "wheat", "a": 35},
        "headline": "Heatwave over the wheat belt", "rationale": "Wheat is growing in IND.", "partner_effects": "MENA",
        "confidence": "medium"}
DISEASE = {"move": "crop_disease", "category": "disease",
           "fields": {"team": "RUS", "crop": "wheat", "a": 20, "b": 0.1, "text": "stem rust"},
           "headline": "Rust in the Black Earth belt", "rationale": "RUS supplies MENA.", "confidence": "high"}


def _cards_req(n=3, menu=MENU):
    return CardsRequest(game_id="g", turn=3, date="2027-07-01", quarter=3, n_cards=n, focus=["harvest", "disease"],
                        state=STATE, menu=menu)


def test_valid_cards_pass_and_carry_their_audit_record():
    llm = FakeLLM(CardDeck.model_validate({"cards": [GOOD, DISEASE]}))
    out = draft_cards(LLMHandle(llm=llm, provider="fake", model="fake-model", temperature=0.4), _cards_req())
    assert out["status"] == "ok" and out["rejected"] == []
    assert [c["move"] for c in out["cards"]] == ["drought", "crop_disease"]
    c0 = out["cards"][0]
    assert c0["fields"] == {"team": "IND", "crop": "wheat", "a": 35.0, "b": None, "text": None}
    assert c0["card_id"].startswith("c-") and len(c0["card_id"]) == 10
    assert "scenario assumption" in c0["assumption_note"]
    assert len(out["llm"]["prompt_sha256"]) == 64 and out["llm"]["model"] == "fake-model"
    assert out["llm"]["raw"]["cards"][1]["fields"]["text"] == "stem rust"
    # the menu and the state reached the prompt
    human = llm.calls[0]["messages"][-1].content
    assert "water_deficit_pct" in human and "main_suppliers" in human


def test_out_of_range_card_is_rejected_not_clamped():
    bad = {**GOOD, "fields": {"team": "IND", "crop": "wheat", "a": 120}}
    out = draft_cards(_handle(CardDeck.model_validate({"cards": [bad]})), _cards_req())
    assert out["cards"] == []
    assert out["rejected"][0]["card"]["fields"]["a"] == 120
    assert any("above max 90" in r for r in out["rejected"][0]["reasons"])


def test_unknown_move_bad_option_and_stray_field_are_rejected():
    deck = CardDeck.model_validate({"cards": [
        {**GOOD, "move": "locust_swarm"},
        {**GOOD, "fields": {"team": "ATLANTIS", "crop": "wheat", "a": 30}},
        {**GOOD, "fields": {"team": "IND", "crop": "wheat", "a": 30, "partner": "US"}},
        {**DISEASE, "fields": {"team": "RUS", "crop": "wheat", "a": 20, "b": 0.1}},   # pathogen missing
    ]})
    cards, rejected = check_deck(deck, _cards_req())
    assert cards == []
    reasons = [" ".join(r["reasons"]) for r in rejected]
    assert "not on the menu" in reasons[0]
    assert "not one of" in reasons[1]
    assert "not part of this move" in reasons[2]
    assert "pathogen (text) is required" in reasons[3]


def test_one_card_per_team_crop_and_the_requested_count():
    twin = {**GOOD, "headline": "Another heatwave"}
    other = {**GOOD, "fields": {"team": "US", "crop": "maize", "a": 30}, "headline": "Dry July"}
    cards, rejected = check_deck(CardDeck.model_validate({"cards": [GOOD, twin, other]}), _cards_req(n=1))
    assert len(cards) == 1
    assert any("already drafted" in " ".join(r["reasons"]) for r in rejected)
    assert any("beyond the 1 card" in " ".join(r["reasons"]) for r in rejected)


def test_card_id_is_deterministic():
    f = {"team": "IND", "crop": "wheat", "a": 35.0, "b": None, "text": None}
    assert card_id("drought", f, "x") == card_id("drought", dict(f), "x")
    assert card_id("drought", f, "x") != card_id("drought", {**f, "a": 36.0}, "x")
    a = draft_cards(_handle(CardDeck.model_validate({"cards": [GOOD]})), _cards_req())
    b = draft_cards(_handle(CardDeck.model_validate({"cards": [GOOD]})), _cards_req())
    assert a["cards"][0]["card_id"] == b["cards"][0]["card_id"]


def test_dict_answers_parse_and_off_schema_answers_are_unavailable():
    out = draft_cards(_handle({"cards": [GOOD]}), _cards_req())
    assert len(out["cards"]) == 1
    with pytest.raises(LLMUnavailable):
        draft_cards(_handle({"cards": "not a list"}), _cards_req())
    with pytest.raises(LLMUnavailable):
        draft_cards(_handle(RuntimeError("rate limited")), _cards_req())


def _novel_req(text="We put a 25 percent tariff on American soybeans and ban our wheat exports."):
    return NovelRequest(game_id="g", turn=2, seat="CHN", seat_name="China", text=text, state=STATE,
                        order_menu=ORDER_MENU, control_menu=MENU)


def test_novel_mapping_is_validated():
    answer = {"interpretation": "China retaliates against US soybeans and keeps its wheat at home.",
              "orders": [{"type": "import_tariff", "fields": {"crop": "soybeans", "partner": "US", "a": 25}},
                         {"type": "export_ban", "fields": {"crop": "wheat"}},
                         {"type": "import_tariff", "fields": {"crop": "soybeans", "partner": "US", "a": 500}},
                         {"type": "seize_ships", "fields": {}}],
              "control": [{"move": "news", "fields": {"text": "Beijing announces retaliation."}}],
              "confidence": "high", "inferred": [], "unmapped": ""}
    out = extract_novel(_handle(answer), _novel_req())
    assert out["status"] == "ok"
    assert out["orders"] == [{"type": "import_tariff", "fields": {"crop": "soybeans", "partner": "US", "a": 25.0, "b": None, "text": None}},
                             {"type": "export_ban", "fields": {"crop": "wheat", "partner": None, "a": None, "b": None, "text": None}}]
    assert out["control"] == [{"move": "news", "fields": {"team": None, "crop": None, "a": None, "b": None,
                                                            "text": "Beijing announces retaliation."}}]
    assert len(out["rejected"]) == 2
    assert out["confidence"] == "high"
    assert len(out["llm"]["prompt_sha256"]) == 64


def test_novel_caps_orders_at_three():
    o = {"type": "buy_stocks", "fields": {"crop": "wheat", "a": 1}}
    answer = {"interpretation": "x", "orders": [o, {**o, "fields": {"crop": "rice", "a": 1}},
                                                {**o, "fields": {"crop": "maize", "a": 1}},
                                                {**o, "fields": {"crop": "soybeans", "a": 1}}], "confidence": "medium"}
    out = extract_novel(_handle(answer), _novel_req("Buy everything."))
    assert len(out["orders"]) == 3
    assert "beyond the 3 orders" in " ".join(out["rejected"][0]["reasons"])


def test_validate_fields_optional_number():
    assert validate_fields("hormuz_shock", {"a": 30}, MENU) == []
    assert validate_fields("hormuz_shock", {"a": 30, "b": 1.5}, MENU) == ["hormuz_shock: qatar_damaged_share = 1.5 is above max 1"]
    assert validate_fields("hormuz_shock", {}, MENU) == ["hormuz_shock: transit_capacity_pct (a) is required"]


# --- the HTTP face --------------------------------------------------------------------------

fastapi = pytest.importorskip("fastapi")


def _client(**kw):
    from fastapi.testclient import TestClient

    from src.control_cell.api import create_app

    return TestClient(create_app(**kw))


def test_api_with_a_fake_llm():
    c = _client(llm=FakeLLM(CardDeck.model_validate({"cards": [GOOD]})), provider="fake")
    h = c.get("/healthz").json()
    assert h["llm_configured"] and h["provider"] == "fake" and h["model"] == "fake-model"
    r = c.post("/agri/cards", json=_cards_req().model_dump())
    assert r.status_code == 200 and r.json()["status"] == "ok" and len(r.json()["cards"]) == 1
    assert c.post("/agri/cards", json={"game_id": "g", "menu": {}}).status_code == 422


def test_api_without_an_llm_is_unavailable_with_200():
    def no_llm(_temperature):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    c = _client(llm_factory=no_llm)
    h = c.get("/healthz").json()
    assert h["ok"] and not h["llm_configured"] and "ANTHROPIC_API_KEY" in h["reason"]
    r = c.post("/agri/cards", json=_cards_req().model_dump())
    assert r.status_code == 200 and r.json()["status"] == "unavailable" and "ANTHROPIC_API_KEY" in r.json()["reason"]
    r = c.post("/agri/novel", json=_novel_req().model_dump())
    assert r.status_code == 200 and r.json()["status"] == "unavailable"


def test_api_llm_failure_is_unavailable():
    c = _client(llm=FakeLLM(RuntimeError("upstream 529")), provider="fake")
    r = c.post("/agri/novel", json=_novel_req().model_dump())
    assert r.status_code == 200 and r.json()["status"] == "unavailable" and "529" in r.json()["reason"]
