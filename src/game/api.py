"""HTTP face of the adjudicator, for the game server to call once per crisis round.

    python -m src.game.api --port 8031

Endpoints:

- ``POST /adjudicate``  a :class:`RoundRequest` in, a :class:`RoundResponse` out
- ``GET /healthz``      liveness plus the baseline date and adapter count
- ``GET /models``       the adapters the adjudicator uses and the mode each runs in
- ``GET /baseline``     the frozen baseline with its provenance records

Requires the ``[game]`` extra (``fastapi``, ``uvicorn``). No LLM provider is configured or
called; the service runs on a laptop with the core install.
"""
from __future__ import annotations

import argparse
import logging

from fastapi import FastAPI

from . import baseline as baseline_mod
from .adjudicator import Adjudicator
from .schemas import RoundRequest, RoundResponse

logger = logging.getLogger(__name__)


def create_app(adjudicator: Adjudicator | None = None) -> FastAPI:
    app = FastAPI(title="Hormuz game adjudicator", version="0.1.0",
                  description="Tier 1 adjudication for the economic war game: analytical-MVP "
                              "adapters called through the ModelAdapter contract, no LLM.")
    app.state.adjudicator = adjudicator

    def adj() -> Adjudicator:
        if app.state.adjudicator is None:
            app.state.adjudicator = Adjudicator()
        return app.state.adjudicator

    @app.get("/healthz")
    def healthz() -> dict:
        a = adj()
        return {"ok": True, "as_of": a.baseline.get("as_of"), "baseline_id": a.baseline.get("baseline_id"),
                "adapters": len(a.registry), "no_llm": True}

    @app.get("/models")
    def models() -> list[dict]:
        return adj().models()

    @app.get("/baseline")
    def baseline() -> dict:
        a = adj()
        return {"as_of": a.baseline.get("as_of"), "version": a.baseline.get("version"),
                "values": a.baseline_values, "records": baseline_mod.records(a.baseline)}

    @app.post("/adjudicate", response_model=RoundResponse)
    def adjudicate(req: RoundRequest) -> RoundResponse:
        return adj().adjudicate(req)

    return app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the game adjudicator service.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8031)
    p.add_argument("--log-level", default="info")
    args = p.parse_args(argv)
    import uvicorn

    logging.basicConfig(level=args.log_level.upper())
    uvicorn.run(create_app(Adjudicator()), host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
