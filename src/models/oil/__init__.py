"""Oil model adapters.

Adapters for all oil-sector domain models:
- BornsteinKrusellRebeloAdapter: World Equilibrium Model of the Oil Market
- POLESJRCAdapter: POLES-JRC partial equilibrium energy model
- MarketSimAdapter: MarketSim (BOEM) consumer surplus and substitution model
- FedOilAdapter: Fed Workhorse Oil Model (Baumeister-Hamilton)
"""

from src.models.oil.bornstein_krusell_rebelo import (
    BornsteinKrusellRebeloAdapter,
    BornsteinKrusellRebeloConfig,
)
from src.models.oil.fed_oil import FedOilAdapter
from src.models.oil.marketsim import MarketSimAdapter
from src.models.oil.poles_jrc import POLESJRCAdapter

__all__ = [
    "BornsteinKrusellRebeloAdapter",
    "BornsteinKrusellRebeloConfig",
    "FedOilAdapter",
    "MarketSimAdapter",
    "POLESJRCAdapter",
]
