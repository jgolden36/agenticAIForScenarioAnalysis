"""HTTP face of the control-cell LLM tools, for the game server to call on the host's request.

    python -m src.control_cell.api --port 8032

Endpoints:

- ``GET /healthz``       liveness and whether an LLM can be built (provider, model, reason)
- ``POST /agri/cards``   draft agricultural shock cards against the game's control menu
- ``POST /agri/novel``   map a team's free-text novel action onto the game's menus

The LLM comes from ``src.common.llm.get_llm`` (``PIPELINE_LLM_PROVIDER``, ``PIPELINE_LLM_MODEL``,
``PIPELINE_LLM_BASE_URL`` and the provider's own key), built lazily on the first request. When it
cannot be built or called, every endpoint answers HTTP 200 with
``{"status": "unavailable", "reason": ...}`` so the game shows a badge and the host carries on
with the menus. Malformed requests are 422.

This service is the one place the game's agricultural module meets an LLM. It lives outside
``src/game/`` on purpose: the adjudicator there is LLM-free and deterministic. The game records
every answer from here in its action log and applies a card or a mapping only after the host
approves it, so a replay never calls this service.
"""
from __future__ import annotations

import argparse
import logging
import os
from typing import Any, Callable

from fastapi import FastAPI

from .cards import draft_cards
from .llm_call import LLMHandle, LLMUnavailable
from .novel import extract_novel
from .schemas import CardsRequest, NovelRequest

logger = logging.getLogger(__name__)

CARDS_TEMPERATURE = 0.4
NOVEL_TEMPERATURE = 0.0


def _default_factory(temperature: float) -> Any:
    from src.common.llm import get_llm

    return get_llm(temperature=temperature)


def _model_name(llm: Any) -> str:
    for attr in ("model", "model_name", "model_id"):
        v = getattr(llm, attr, None)
        if isinstance(v, str) and v:
            return v
    return os.environ.get("PIPELINE_LLM_MODEL") or "provider default"


def create_app(llm: Any = None, llm_factory: Callable[[float], Any] | None = None,
               provider: str | None = None) -> FastAPI:
    """``llm`` is used as is for every call (tests inject a fake). Otherwise ``llm_factory(temperature)``
    builds one per call, defaulting to ``get_llm``."""
    app = FastAPI(title="Control-cell LLM tools", version="0.1.0",
                  description="LLM drafting for the economic war game's control cell: agricultural shock cards "
                              "and novel-action mapping. Proposals only; the game's host approves every one.")
    factory = llm_factory or _default_factory
    provider_name = provider or ("injected" if llm is not None else os.environ.get("PIPELINE_LLM_PROVIDER", "anthropic"))

    def handle(temperature: float) -> LLMHandle:
        try:
            model = llm if llm is not None else factory(temperature)
        except Exception as e:  # noqa: BLE001  -- missing package, missing key, bad provider
            raise LLMUnavailable(f"no LLM could be built ({provider_name}): {type(e).__name__}: {str(e)[:300]}") from e
        if model is None:
            raise LLMUnavailable("no LLM configured")
        return LLMHandle(llm=model, provider=provider_name, model=_model_name(model), temperature=temperature)

    def unavailable(e: Exception) -> dict[str, Any]:
        logger.warning("control cell LLM unavailable: %s", e)
        return {"status": "unavailable", "reason": str(e)[:400]}

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        try:
            h = handle(NOVEL_TEMPERATURE)
            return {"ok": True, "llm_configured": True, "provider": h.provider, "model": h.model, "reason": ""}
        except LLMUnavailable as e:
            return {"ok": True, "llm_configured": False, "provider": provider_name, "model": "", "reason": str(e)[:400]}

    @app.post("/agri/cards")
    def agri_cards(req: CardsRequest) -> dict[str, Any]:
        try:
            return draft_cards(handle(CARDS_TEMPERATURE), req)
        except LLMUnavailable as e:
            return unavailable(e)

    @app.post("/agri/novel")
    def agri_novel(req: NovelRequest) -> dict[str, Any]:
        try:
            return extract_novel(handle(NOVEL_TEMPERATURE), req)
        except LLMUnavailable as e:
            return unavailable(e)

    return app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the control-cell LLM tools service.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8032)
    p.add_argument("--log-level", default="info")
    args = p.parse_args(argv)
    import uvicorn

    logging.basicConfig(level=args.log_level.upper())
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
