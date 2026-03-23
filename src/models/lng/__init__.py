"""LNG model adapters.

This package contains adapter stubs for the four LNG domain models in the
pipeline inventory:

- EnergyFluxGasPowerAdapter  — Energy Flux US Gas Power Build-Out Constraint Model v1.0
- EnergyFluxLNGProfitsAdapter — Energy Flux US LNG War Profits Model v1.0
- GGMAdapter                 — Global Gas Model
- LNGSTAdapter               — LNG Spreadsheet Tool (Excel-based)

All adapters subclass ModelAdapter and are tagged with
CommoditySystem.LNG / AnalyticalLevel.COMMODITY.
"""

from src.models.lng.energy_flux_gas_power import EnergyFluxGasPowerAdapter
from src.models.lng.energy_flux_lng_profits import EnergyFluxLNGProfitsAdapter
from src.models.lng.ggm import GGMAdapter
from src.models.lng.lngst import LNGSTAdapter

__all__ = [
    "EnergyFluxGasPowerAdapter",
    "EnergyFluxLNGProfitsAdapter",
    "GGMAdapter",
    "LNGSTAdapter",
]
