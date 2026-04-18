"""Water domain model adapters.

Adapters for WEAP-MENA, SahysMod, WaterGAP2, and CWatM. These models assess
desalination capacity loss, agro-hydrological salinity impacts, gridded
hydrological disruption, and community-scale water availability under
Strait of Hormuz closure scenarios.
"""

from src.models.water.cwatm import CWatMAdapter
from src.models.water.sahysmod import SahysModAdapter
from src.models.water.watergap2 import WaterGAP2Adapter
from src.models.water.weap import WEAPAdapter

__all__ = [
    "WEAPAdapter",
    "SahysModAdapter",
    "WaterGAP2Adapter",
    "CWatMAdapter",
]
