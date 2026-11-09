"""Game adjudicator: the Hormuz pipeline as the economic war game's Tier 1 backend.

The economic war game (the ``EconomicWarGames`` repo) runs a weekly crisis clock. Every round it
clears markets with its own Tier 0 rule, then asks this package for the calibrated numbers the
pipeline's analytical-MVP adapters compute for the same world state. No LLM and no LangGraph
graph is involved: adapters are called directly through the ``ModelAdapter`` contract
(``validate_inputs`` -> ``translate_inputs`` -> ``execute``), the forwarding rules in
``configs/upstream_forwarding_mapping.yaml`` pass computed shocks between them, and every number
in the answer carries the model id, output key and implementation mode it came from.

See ``docs/game/INTEGRATION_PLAN.md`` and ``docs/game/ADJUDICATOR.md``.
"""

from .schemas import RoundRequest, RoundResponse, WorldState  # noqa: F401
from .adjudicator import Adjudicator  # noqa: F401

__all__ = ["Adjudicator", "RoundRequest", "RoundResponse", "WorldState"]
