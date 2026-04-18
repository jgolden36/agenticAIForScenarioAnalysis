"""Energy-systems model adapters.

Adapters for long-run energy systems optimization models:

- OSeMOSYSAdapter: Open Source Energy Modelling System (otoole + GLPK MathProg).
- MESSAGEixAdapter: IIASA's MESSAGEix integrated assessment model (message-ix + ixmp).
- TEMOAAdapter: Tools for Energy Model Optimization and Analysis (Pyomo + CBC).

All three operate at the LONG_RUN_MACRO_STRATEGIC analytical level under
``CommoditySystem.ENERGY_SYSTEMS`` and consume the disruption-derived
fuel-supply / fuel-price / capital-cost shocks defined in
``src/parameters/model_specs/energy.py``.
"""

from src.models.energy.messageix import MESSAGEixAdapter, MESSAGEixConfig
from src.models.energy.osemosys import OSeMOSYSAdapter, OSeMOSYSConfig
from src.models.energy.temoa import TEMOAAdapter, TEMOAConfig

__all__ = [
    "MESSAGEixAdapter",
    "MESSAGEixConfig",
    "OSeMOSYSAdapter",
    "OSeMOSYSConfig",
    "TEMOAAdapter",
    "TEMOAConfig",
]
