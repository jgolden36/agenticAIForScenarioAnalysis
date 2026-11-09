"""Map a team's free-text novel action onto the game's menus (``POST /agri/novel``).

This is the integration plan's "parameter extraction becomes the matrix-game adjudicator"
(Section 6): the LLM proposes orders (and, rarely, control moves) with a confidence and a list
of what it inferred; ``validate.py`` checks each item against the menus the game sent; the
control cell approves or rejects in the game. Nothing applies on its own.
"""
from __future__ import annotations

import json
import time
from typing import Any

from .llm_call import LLMHandle, structured_call
from .prompts import NOVEL_PROMPT
from .schemas import CONFIDENCE, NovelExtraction, NovelRequest
from .validate import validate_fields

ORDER_FIELDS: tuple[str, ...] = ("crop", "partner", "a", "b", "text")
CONTROL_FIELDS: tuple[str, ...] = ("team", "crop", "a", "b", "text")
MAX_ORDERS = 3
MAX_CONTROL = 2


def _json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, indent=1, default=str)


def prompt_variables(req: NovelRequest) -> dict[str, Any]:
    return {"game_id": req.game_id, "turn": req.turn, "seat": req.seat, "seat_name": req.seat_name or req.seat,
            "text": req.text.strip(), "state": _json(req.state), "order_menu": _json(req.order_menu),
            "control_menu": _json(req.control_menu)}


def check_extraction(ex: NovelExtraction, req: NovelRequest) -> dict[str, Any]:
    """The wire form of an extraction: accepted orders and control moves, rejected items with reasons."""
    orders: list[dict[str, Any]] = []
    control: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for o in ex.orders:
        fields = o.fields.model_dump()
        reasons = validate_fields(o.type, fields, req.order_menu)
        if not reasons and len(orders) >= MAX_ORDERS:
            reasons.append(f"beyond the {MAX_ORDERS} orders a novel action may map to")
        if reasons:
            rejected.append({"item": {"kind": "order", **o.model_dump(mode="json")}, "reasons": reasons})
        else:
            orders.append({"type": o.type, "fields": {k: fields.get(k) for k in ORDER_FIELDS}})
    for c in ex.control:
        fields = c.fields.model_dump()
        reasons = validate_fields(c.move, fields, req.control_menu) if req.control_menu else ["the request carries no control menu"]
        if not reasons and len(control) >= MAX_CONTROL:
            reasons.append(f"beyond the {MAX_CONTROL} control moves a novel action may map to")
        if reasons:
            rejected.append({"item": {"kind": "control", **c.model_dump(mode="json")}, "reasons": reasons})
        else:
            control.append({"move": c.move, "fields": {k: fields.get(k) for k in CONTROL_FIELDS}})
    confidence = (ex.confidence or "").strip().lower()
    if confidence not in CONFIDENCE:
        rejected.append({"item": {"kind": "confidence", "value": ex.confidence},
                         "reasons": [f"confidence {ex.confidence!r} is not one of {list(CONFIDENCE)}; reported as low"]})
        confidence = "low"
    return {"interpretation": (ex.interpretation or "").strip(), "orders": orders, "control": control,
            "confidence": confidence, "inferred": [str(x) for x in ex.inferred], "unmapped": (ex.unmapped or "").strip(),
            "rejected": rejected}


def extract_novel(handle: LLMHandle, req: NovelRequest) -> dict[str, Any]:
    """One LLM call, then validation. Raises ``LLMUnavailable`` (the API reports it)."""
    t0 = time.perf_counter()
    ex, meta = structured_call(handle, NOVEL_PROMPT, prompt_variables(req), NovelExtraction)
    body = check_extraction(ex, req)  # type: ignore[arg-type]
    return {"status": "ok", **body, "llm": meta, "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 2)}
