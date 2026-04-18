"""Shipping domain model adapters.

Adapters for AISdb and AIS_project. These models process AIS vessel tracking
data to estimate rerouting costs, transit time penalties, and fleet utilization
changes under Strait of Hormuz closure scenarios. Both operate at the commodity
analytical level and produce physical disruption parameters (additional transit
days, freight rate multipliers, fleet capacity reductions) that feed into
commodity-level price and supply models.
"""

from src.models.shipping.ais_project import AISProjectAdapter
from src.models.shipping.aisdb import AISDBAdapter

__all__ = [
    "AISDBAdapter",
    "AISProjectAdapter",
]
