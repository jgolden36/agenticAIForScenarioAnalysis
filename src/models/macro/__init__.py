"""Macroeconomic domain model adapters.

Adapters for NEMS, MAM, NREL, MPSGE.jl, OpenCGE, pycge, and MIRAGRODEP. These
models translate commodity-level price shocks and supply disruptions into
economy-wide impacts: GDP, inflation, employment, trade balances, and long-run
structural adjustments. They operate at either the short-run macro or long-run
macro/strategic analytical level, forming the final tier of the four-level
pipeline before synthesis.
"""

from src.models.macro.mam import MAMAdapter
from src.models.macro.miragrodep import MIRAGRODEPAdapter
from src.models.macro.mpsge_jl import MPSGEJLAdapter
from src.models.macro.nems import NEMSAdapter
from src.models.macro.nrel import NRELAdapter
from src.models.macro.opencge import OpenCGEAdapter
from src.models.macro.pycge import PyCGEAdapter

__all__ = [
    "NEMSAdapter",
    "MAMAdapter",
    "NRELAdapter",
    "MPSGEJLAdapter",
    "OpenCGEAdapter",
    "PyCGEAdapter",
    "MIRAGRODEPAdapter",
]
