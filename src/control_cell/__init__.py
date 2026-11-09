"""Control-cell LLM tools for the economic war game (integration plan, Phase 4).

The game's control cell (the host) can ask an LLM to draft agricultural shock cards against the
game's own control menu, and to map a team's free-text novel action onto the order menu. Both
are proposals: ``validate.py`` rejects anything outside the menus with reasons and never repairs
a value, the game records every answer in its action log, and nothing changes the game until
the host approves it.

This package is the only LLM user on the game path. ``src/game/`` (the Tier 1 adjudicator)
stays LLM-free and deterministic. See ``docs/game/AGRI.md``.
"""

from .schemas import CardDeck, CardsRequest, NovelExtraction, NovelRequest  # noqa: F401

__all__ = ["CardDeck", "CardsRequest", "NovelExtraction", "NovelRequest"]
