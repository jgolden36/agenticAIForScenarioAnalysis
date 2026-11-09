"""Game adjudicator: the Hormuz pipeline as the economic war game's Tier 1 backend.

The economic war game (the ``EconomicWarGames`` repo) runs a weekly crisis clock. Every round it
clears markets with its own Tier 0 rule, then asks this package for the calibrated numbers the
pipeline's analytical-MVP adapters compute for the same world state. No LLM and no LangGraph
graph is involved: adapters are called directly through the ``ModelAdapter`` contract
(``validate_inputs`` -> ``translate_inputs`` -> ``execute``), the forwarding rules in
``configs/upstream_forwarding_mapping.yaml`` pass computed shocks between them, and every number
in the answer carries the model id, output key and implementation mode it came from.

The agricultural module (``AgriAdjudicator``, ``POST /adjudicate/agri``) runs the fertilizer, crop
yield (APSIM), futures and macro adapters for the game's ``agri`` ruleset the same way.

See ``docs/game/INTEGRATION_PLAN.md``, ``docs/game/ADJUDICATOR.md`` and ``docs/game/AGRI.md``.
"""

from .schemas import RoundRequest, RoundResponse, WorldState  # noqa: F401
from .adjudicator import Adjudicator  # noqa: F401
from .agri_schemas import AgriRoundRequest, AgriRoundResponse  # noqa: F401
from .agri import AgriAdjudicator  # noqa: F401

__all__ = ["Adjudicator", "AgriAdjudicator", "AgriRoundRequest", "AgriRoundResponse", "RoundRequest",
           "RoundResponse", "WorldState"]
