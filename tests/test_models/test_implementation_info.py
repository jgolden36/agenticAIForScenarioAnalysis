"""Every registered adapter must carry a complete ImplementationInfo entry."""

from __future__ import annotations

from pathlib import Path

from src.common.types import ImplementationMode
from src.models.implementation_info import IMPLEMENTATION_INFO
from src.models.registry import build_default_registry, default_config_dir


def _registry():
    return build_default_registry(default_config_dir())


def test_every_registered_adapter_has_an_entry():
    reg = _registry()
    missing = [a.model_id for a in reg.all_adapters() if a.model_id not in IMPLEMENTATION_INFO]
    assert missing == [], f"adapters without implementation info: {missing}"
    extra = [m for m in IMPLEMENTATION_INFO if reg.get(m) is None]
    assert extra == [], f"implementation info for unregistered ids: {extra}"


def test_entries_are_internally_consistent():
    for model_id, info in IMPLEMENTATION_INFO.items():
        assert info.status_label, model_id
        assert info.display_name, model_id
        assert info.modes_available, model_id
        assert info.mode_when_executed in info.modes_available, model_id
        assert info.mode_when_executed != ImplementationMode.UNKNOWN, model_id
        if info.mode_when_executed == ImplementationMode.STUB:
            assert "stub" in info.status_label.lower(), model_id
        else:
            assert "stub" not in info.status_label.lower() or info.requires_config, model_id
        if ImplementationMode.ANALYTICAL_REDUCTION in info.modes_available:
            assert info.display_name_reduced, model_id
            assert info.calibration_sources, model_id
            assert info.key_equations, model_id
            assert "analytical" in info.status_label.lower(), model_id
        if info.requires_config:
            assert "config" in info.status_label.lower(), model_id


def test_inventory_rows_point_at_existing_adapter_files():
    reg = _registry()
    rows = reg.inventory()
    assert len(rows) == len(reg)
    root = Path(__file__).resolve().parents[2]
    for r in rows:
        assert (root / r["adapter_path"]).exists(), r
        assert r["status_label"] == IMPLEMENTATION_INFO[r["model_id"]].status_label
        assert r["mode_when_executed"] == IMPLEMENTATION_INFO[r["model_id"]].mode_when_executed.value


def test_adapter_property_resolves_from_table():
    reg = _registry()
    assert reg.get("fed_oil").implementation_info.mode_when_executed == ImplementationMode.ANALYTICAL_REDUCTION
    assert reg.get("gtap").implementation_info.mode_when_executed == ImplementationMode.STUB
    assert reg.get("mam").implementation_info.mode_when_executed == ImplementationMode.PUBLISHED_OUTPUT_INGESTION
    assert reg.get("bornstein_krusell_rebelo").implementation_info.mode_when_executed == ImplementationMode.FULL_UPSTREAM
