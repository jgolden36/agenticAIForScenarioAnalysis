"""Fertilizer and agriculture domain model adapters.

Adapters for CAPRI, MAgPIE, SIMPLE-G, World Fertilizer Model, GTAP, APSIM,
and futures forecasting models. These models assess fertilizer price shocks,
crop yield impacts, agricultural trade disruptions, and commodity futures
trajectories under Strait of Hormuz closure scenarios.
"""

from src.models.fertilizer.apsim import APSIMAdapter
from src.models.fertilizer.capri import CAPRIAdapter
from src.models.fertilizer.futures import FuturesAdapter
from src.models.fertilizer.gtap import GTAPAdapter
from src.models.fertilizer.magpie import MAgPIEAdapter
from src.models.fertilizer.simple_g import SIMPLEGAdapter
from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter

__all__ = [
    "CAPRIAdapter",
    "MAgPIEAdapter",
    "SIMPLEGAdapter",
    "WorldFertilizerAdapter",
    "GTAPAdapter",
    "APSIMAdapter",
    "FuturesAdapter",
]
