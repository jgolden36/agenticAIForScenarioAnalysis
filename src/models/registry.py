"""Model registry — maps model IDs to adapter classes.

Supports querying by commodity system and analytical level.
"""

from __future__ import annotations

from src.common.logging import get_logger
from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter

logger = get_logger(__name__)


class ModelRegistry:
    """Registry of available domain model adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}

    def register(self, adapter: ModelAdapter) -> None:
        """Register a model adapter instance."""
        if adapter.model_id in self._adapters:
            logger.warning(f"Overwriting existing adapter for {adapter.model_id}")
        self._adapters[adapter.model_id] = adapter
        logger.info(
            f"Registered model: {adapter.model_id} "
            f"({adapter.commodity_system.value}/{adapter.analytical_level.value})"
        )

    def get(self, model_id: str) -> ModelAdapter | None:
        """Get an adapter by model ID."""
        return self._adapters.get(model_id)

    def get_by_commodity_system(
        self, system: CommoditySystem
    ) -> list[ModelAdapter]:
        """Get all adapters for a commodity system."""
        return [
            a for a in self._adapters.values() if a.commodity_system == system
        ]

    def get_by_analytical_level(
        self, level: AnalyticalLevel
    ) -> list[ModelAdapter]:
        """Get all adapters at a given analytical level."""
        return [
            a for a in self._adapters.values() if a.analytical_level == level
        ]

    def all_model_ids(self) -> list[str]:
        """Return all registered model IDs."""
        return list(self._adapters.keys())

    def all_adapters(self) -> list[ModelAdapter]:
        """Return all registered adapters."""
        return list(self._adapters.values())

    def __len__(self) -> int:
        return len(self._adapters)


def build_default_registry() -> ModelRegistry:
    """Build a registry with all model adapter stubs.

    Imports and registers all adapter stubs from the model subdirectories.
    """
    from src.models.fertilizer.apsim import APSIMAdapter
    from src.models.fertilizer.capri import CAPRIAdapter
    from src.models.fertilizer.futures import FuturesAdapter
    from src.models.fertilizer.gtap import GTAPAdapter
    from src.models.fertilizer.magpie import MAgPIEAdapter
    from src.models.fertilizer.simple_g import SIMPLEGAdapter
    from src.models.fertilizer.world_fertilizer import WorldFertilizerAdapter
    from src.models.helium.argonne_abm import ArgonneABMAdapter
    from src.models.helium.simrlfab import SimRLFabAdapter
    from src.models.helium.world_helium_model import WorldHeliumModelAdapter
    from src.models.lng.energy_flux_gas_power import EnergyFluxGasPowerAdapter
    from src.models.lng.energy_flux_lng_profits import EnergyFluxLNGProfitsAdapter
    from src.models.lng.ggm import GGMAdapter
    from src.models.lng.lngst import LNGSTAdapter
    from src.models.macro.miragrodep import MIRAGRODEPAdapter
    from src.models.macro.mpsge_jl import MPSGEJLAdapter
    from src.models.macro.nems import NEMSAdapter
    from src.models.macro.nrel import NRELAdapter
    from src.models.macro.opencge import OpenCGEAdapter
    from src.models.macro.pycge import PyCGEAdapter
    from src.models.oil.bornstein_krusell_rebelo import BornsteinKrusellRebeloAdapter
    from src.models.oil.fed_oil import FedOilAdapter
    from src.models.oil.marketsim import MarketSimAdapter
    from src.models.oil.poles_jrc import POLESJRCAdapter
    from src.models.shipping.ais_project import AISProjectAdapter
    from src.models.shipping.aisdb import AISDBAdapter
    from src.models.water.cwatm import CWatMAdapter
    from src.models.water.sahysmod import SahysModAdapter
    from src.models.water.watergap2 import WaterGAP2Adapter
    from src.models.water.weap import WEAPAdapter

    registry = ModelRegistry()

    all_adapters = [
        # Water
        WEAPAdapter(), SahysModAdapter(), WaterGAP2Adapter(), CWatMAdapter(),
        # Oil
        BornsteinKrusellRebeloAdapter(), POLESJRCAdapter(), MarketSimAdapter(), FedOilAdapter(),
        # LNG
        EnergyFluxGasPowerAdapter(), EnergyFluxLNGProfitsAdapter(), GGMAdapter(), LNGSTAdapter(),
        # Helium & Semiconductors
        WorldHeliumModelAdapter(), ArgonneABMAdapter(), SimRLFabAdapter(),
        # Fertilizer & Agriculture
        CAPRIAdapter(), MAgPIEAdapter(), SIMPLEGAdapter(), WorldFertilizerAdapter(),
        GTAPAdapter(), APSIMAdapter(), FuturesAdapter(),
        # Shipping
        AISDBAdapter(), AISProjectAdapter(),
        # Macro
        NEMSAdapter(), NRELAdapter(), MPSGEJLAdapter(), OpenCGEAdapter(),
        PyCGEAdapter(), MIRAGRODEPAdapter(),
    ]

    for adapter in all_adapters:
        registry.register(adapter)

    return registry
