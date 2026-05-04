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


def test_default_config_dir_resolves_to_project_configs():
    """default_config_dir() should find the in-tree configs/model_configs/.

    This regression-tests the fix for the SLURM execution path that was
    silently degrading every configured adapter to its default
    (non-cluster) paths because run_model.py called
    build_default_registry() with no config_dir.
    """
    from pathlib import Path

    from src.models.registry import default_config_dir

    cfg = default_config_dir()
    assert cfg is not None, (
        "default_config_dir() returned None — configs/model_configs/ should "
        "exist at the project root"
    )
    assert cfg.exists()
    assert cfg.is_dir()
    assert cfg.name == "model_configs"
    assert cfg.parent.name == "configs"
    # Sanity: at least one adapter YAML lives there
    yamls = list(cfg.glob("*.yaml"))
    assert yamls, f"No YAML configs found in {cfg}"


def test_build_default_registry_uses_config_dir(tmp_path):
    """When build_default_registry receives a config_dir, OSeMOSYSConfig
    paths should be loaded from osemosys.yaml rather than the bare
    defaults pointed at Models/Energy/OSeMOSYS."""
    from pathlib import Path

    import yaml

    from src.models.registry import build_default_registry

    # Synthesize a minimal config dir with just osemosys.yaml.
    cfg_dir = tmp_path / "model_configs"
    cfg_dir.mkdir()
    osemosys_dir = tmp_path / "OSeMOSYS"
    osemosys_dir.mkdir()
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    output = tmp_path / "out"

    with open(cfg_dir / "osemosys.yaml", "w") as f:
        yaml.safe_dump(
            {
                "osemosys_dir": str(osemosys_dir),
                "baseline_data_dir": str(baseline),
                "output_dir": str(output),
            },
            f,
        )

    registry = build_default_registry(cfg_dir)
    osemosys = registry.get("osemosys")
    assert osemosys is not None
    # The adapter should have picked up the YAML config rather than the
    # default Models/Energy/OSeMOSYS path.
    assert Path(osemosys._config.osemosys_dir) == osemosys_dir
    assert Path(osemosys._config.baseline_data_dir) == baseline
