"""Model input specifications by commodity system.

Each module defines the parameter schemas that domain models in that
commodity system require. These specifications drive Module 2 (parameter
extraction) — the LLM uses them to know what to extract from scenario narratives.
"""

from src.parameters.model_specs.energy import ENERGY_MODEL_SPECS
from src.parameters.model_specs.fertilizer import FERTILIZER_MODEL_SPECS
from src.parameters.model_specs.helium import HELIUM_MODEL_SPECS
from src.parameters.model_specs.lng import LNG_MODEL_SPECS
from src.parameters.model_specs.macro import MACRO_MODEL_SPECS
from src.parameters.model_specs.oil import OIL_MODEL_SPECS
from src.parameters.model_specs.shipping import SHIPPING_MODEL_SPECS
from src.parameters.model_specs.water import WATER_MODEL_SPECS

ALL_MODEL_SPECS: dict[str, dict] = {}
for specs in [
    WATER_MODEL_SPECS,
    OIL_MODEL_SPECS,
    LNG_MODEL_SPECS,
    HELIUM_MODEL_SPECS,
    FERTILIZER_MODEL_SPECS,
    SHIPPING_MODEL_SPECS,
    MACRO_MODEL_SPECS,
    ENERGY_MODEL_SPECS,
]:
    ALL_MODEL_SPECS.update(specs)
