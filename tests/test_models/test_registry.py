"""Tests for the model registry."""

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult


class MockAdapter(ModelAdapter):
    """Mock adapter for testing the registry."""

    def __init__(self, mid: str, cs: CommoditySystem, al: AnalyticalLevel):
        self._model_id = mid
        self._cs = cs
        self._al = al

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def commodity_system(self) -> CommoditySystem:
        return self._cs

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return self._al

    @property
    def description(self) -> str:
        return f"Mock {self._model_id}"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        raise NotImplementedError("Mock")

    def parse_outputs(self, raw):
        return ModelOutput(model_id=self._model_id)


def test_registry_register_and_get():
    from src.models.registry import ModelRegistry

    registry = ModelRegistry()
    adapter = MockAdapter("test1", CommoditySystem.OIL, AnalyticalLevel.COMMODITY)
    registry.register(adapter)

    assert registry.get("test1") is adapter
    assert registry.get("nonexistent") is None
    assert len(registry) == 1


def test_registry_query_by_system():
    from src.models.registry import ModelRegistry

    registry = ModelRegistry()
    registry.register(MockAdapter("oil1", CommoditySystem.OIL, AnalyticalLevel.COMMODITY))
    registry.register(MockAdapter("oil2", CommoditySystem.OIL, AnalyticalLevel.COMMODITY))
    registry.register(MockAdapter("water1", CommoditySystem.WATER, AnalyticalLevel.COMMODITY))

    oil_adapters = registry.get_by_commodity_system(CommoditySystem.OIL)
    assert len(oil_adapters) == 2

    water_adapters = registry.get_by_commodity_system(CommoditySystem.WATER)
    assert len(water_adapters) == 1


def test_registry_query_by_level():
    from src.models.registry import ModelRegistry

    registry = ModelRegistry()
    registry.register(MockAdapter("m1", CommoditySystem.OIL, AnalyticalLevel.COMMODITY))
    registry.register(MockAdapter("m2", CommoditySystem.OIL, AnalyticalLevel.SHORT_RUN_MACRO))
    registry.register(MockAdapter("m3", CommoditySystem.WATER, AnalyticalLevel.COMMODITY))

    commodity = registry.get_by_analytical_level(AnalyticalLevel.COMMODITY)
    assert len(commodity) == 2

    macro = registry.get_by_analytical_level(AnalyticalLevel.SHORT_RUN_MACRO)
    assert len(macro) == 1
