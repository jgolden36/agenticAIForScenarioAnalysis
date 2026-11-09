"""Draft agricultural shock cards for the control cell (``POST /agri/cards``).

The LLM proposes cards against the menu the game sent; ``validate.py`` accepts or rejects each
one with reasons; nothing is clamped. Accepted cards carry a deterministic ``card_id`` so the
game can refer to a card in the record. The game stores the whole answer in its action payload
and plays a card only when the host approves it.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from .llm_call import LLMHandle, structured_call
from .prompts import CARDS_PROMPT
from .schemas import CATEGORIES, CONFIDENCE, CardDeck, CardsRequest
from .validate import validate_fields

CARD_FIELDS: tuple[str, ...] = ("team", "crop", "a", "b", "text")
ASSUMPTION_NOTE = "The magnitude is a scenario assumption for play, not a model output."


def card_id(move: str, fields: dict[str, Any], headline: str) -> str:
    blob = json.dumps({"move": move, "fields": fields, "headline": headline}, sort_keys=True, ensure_ascii=False)
    return "c-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]


def _json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, indent=1, default=str)


def prompt_variables(req: CardsRequest) -> dict[str, Any]:
    return {"game_id": req.game_id, "turn": req.turn, "date": req.date or "(no date)",
            "quarter": req.quarter if req.quarter is not None else "(not given)", "n_cards": req.n_cards,
            "focus": ", ".join(req.focus) if req.focus else "any",
            "guidance": req.guidance.strip() or "(none)", "state": _json(req.state), "menu": _json(req.menu)}


def check_deck(deck: CardDeck, req: CardsRequest) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split the LLM's cards into accepted (wire form) and rejected (with reasons)."""
    cards: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for c in deck.cards:
        fields = c.fields.model_dump()
        reasons = validate_fields(c.move, fields, req.menu)
        category = (c.category or "").strip().lower()
        if category not in CATEGORIES:
            reasons.append(f"category {c.category!r} is not one of {list(CATEGORIES)}")
        confidence = (c.confidence or "").strip().lower()
        if confidence not in CONFIDENCE:
            reasons.append(f"confidence {c.confidence!r} is not one of {list(CONFIDENCE)}")
        if not (c.headline or "").strip():
            reasons.append("the card has no headline")
        key = (fields.get("team"), fields.get("crop"))
        if not reasons and key != (None, None) and key in seen:
            reasons.append(f"a card for {key[0]} {key[1]} was already drafted (one card per team and crop)")
        if not reasons and len(cards) >= req.n_cards:
            reasons.append(f"beyond the {req.n_cards} card(s) requested")
        if reasons:
            rejected.append({"card": c.model_dump(mode="json"), "reasons": reasons})
            continue
        seen.add(key)
        wire = {k: fields.get(k) for k in CARD_FIELDS}
        cards.append({"card_id": card_id(c.move, wire, c.headline.strip()), "move": c.move, "category": category,
                      "fields": wire, "headline": c.headline.strip(), "rationale": (c.rationale or "").strip(),
                      "partner_effects": (c.partner_effects or "").strip(), "confidence": confidence,
                      "assumption_note": ASSUMPTION_NOTE})
    return cards, rejected


def draft_cards(handle: LLMHandle, req: CardsRequest) -> dict[str, Any]:
    """One LLM call, then validation. Raises ``LLMUnavailable`` (the API reports it)."""
    t0 = time.perf_counter()
    deck, meta = structured_call(handle, CARDS_PROMPT, prompt_variables(req), CardDeck)
    cards, rejected = check_deck(deck, req)  # type: ignore[arg-type]
    return {"status": "ok", "cards": cards, "rejected": rejected, "llm": meta,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}
