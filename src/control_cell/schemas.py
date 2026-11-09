"""Shapes for the control-cell LLM tools: what the game sends, what the LLM must return.

Two families:

- the request bodies of ``POST /agri/cards`` and ``POST /agri/novel`` (:class:`CardsRequest`,
  :class:`NovelRequest`), which carry the game's own menus so the service never needs to know
  the game's vocabulary in advance;
- the structured outputs the LLM is asked for (:class:`CardDeck`, :class:`NovelExtraction`).
  Every field is optional or defaulted so a sloppy answer still parses; the menu validation in
  ``validate.py`` then accepts or rejects each item with reasons. Nothing is repaired.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

CATEGORIES: tuple[str, ...] = ("harvest", "disease", "hormuz", "partner_loss", "trade", "other")
CONFIDENCE: tuple[str, ...] = ("high", "medium", "low")


# --- request bodies ---------------------------------------------------------------------------


class CardsRequest(BaseModel):
    game_id: str
    turn: int = Field(1, ge=0)
    date: str = ""
    quarter: int | None = Field(None, ge=1, le=4)
    n_cards: int = Field(3, ge=1, le=6)
    focus: list[str] = Field(default_factory=list, description="Subset of harvest, disease, hormuz, partner_loss, trade")
    guidance: str = Field("", max_length=1000, description="Free text from the control cell")
    state: dict[str, Any] = Field(default_factory=dict, description="The game state summary the cards must fit")
    menu: dict[str, dict[str, Any]] = Field(..., min_length=1, description="The control moves the game accepts")


class NovelRequest(BaseModel):
    game_id: str
    turn: int = Field(1, ge=0)
    seat: str
    seat_name: str = ""
    text: str = Field(..., min_length=1, max_length=2000)
    state: dict[str, Any] = Field(default_factory=dict)
    order_menu: dict[str, dict[str, Any]] = Field(..., min_length=1)
    control_menu: dict[str, dict[str, Any]] = Field(default_factory=dict)


# --- structured outputs the LLM fills -------------------------------------------------------


class MenuFields(BaseModel):
    """The generic form fields of a game move or order. Null means absent."""

    team: str | None = Field(None, description="A team id, for control moves that name one")
    crop: str | None = Field(None, description="A crop, or ALL where the menu offers it")
    partner: str | None = Field(None, description="A partner seat, for orders that name one")
    a: float | None = Field(None, description="The first number, as the menu's `a` field names it")
    b: float | None = Field(None, description="The second number, as the menu's `b` field names it")
    text: str | None = Field(None, description="Free text, where the menu has a text field")


class DraftCard(BaseModel):
    move: str = Field(..., description="A control move id from the menu")
    category: str = Field("other", description="harvest, disease, hormuz, partner_loss, trade or other")
    fields: MenuFields = Field(default_factory=MenuFields)
    headline: str = Field("", description="One line a newsreader would say")
    rationale: str = Field("", description="Why this card fits the current state")
    partner_effects: str = Field("", description="Which other teams are exposed and through what")
    confidence: str = Field("medium", description="high, medium or low: fit to the state, not likelihood")


class CardDeck(BaseModel):
    cards: list[DraftCard] = Field(default_factory=list)


class OrderItem(BaseModel):
    type: str = Field(..., description="An order type from the team's order menu")
    fields: MenuFields = Field(default_factory=MenuFields)


class ControlItem(BaseModel):
    move: str = Field(..., description="A control move id from the control menu")
    fields: MenuFields = Field(default_factory=MenuFields)


class NovelExtraction(BaseModel):
    interpretation: str = Field("", description="One sentence: what the team is trying to do")
    orders: list[OrderItem] = Field(default_factory=list)
    control: list[ControlItem] = Field(default_factory=list)
    confidence: str = Field("medium", description="high only when every field is stated in the text")
    inferred: list[str] = Field(default_factory=list, description="Every guess made: a partner, a crop, a number")
    unmapped: str = Field("", description="What the text asks for that no menu entry covers")
