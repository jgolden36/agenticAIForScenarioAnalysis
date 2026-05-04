"""Tests for the section catalogue + routing rules used by the
chunked Module 4 synthesizer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.common.types import (
    AnalyticalLevel,
    CommoditySystem,
    OutcomeScope,
    TimeHorizon,
)
from src.synthesis import sectioning


# --------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------


def test_default_routes_cover_all_six_sections() -> None:
    routes = sectioning.default_section_routes()
    keys = {r.key for r in routes}
    expected = {
        sectioning.SectionKey(th, sc)
        for th in TimeHorizon
        for sc in OutcomeScope
    }
    assert keys == expected


def test_all_section_keys_returns_six() -> None:
    keys = sectioning.all_section_keys()
    assert len(keys) == 6


# --------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------


def _meta(model_id: str, system: CommoditySystem, level: AnalyticalLevel):
    return sectioning.ModelMetadata(
        model_id=model_id,
        commodity_system=system,
        analytical_level=level,
    )


def test_micro_section_includes_commodity_models() -> None:
    routes = sectioning.default_section_routes()
    short_micro = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO)
    models = [
        _meta("poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY),
        _meta("ggm", CommoditySystem.LNG, AnalyticalLevel.COMMODITY),
        _meta("simrlfab", CommoditySystem.HELIUM_SEMICONDUCTORS, AnalyticalLevel.COMMODITY_DOWNSTREAM),
        _meta("nems", CommoditySystem.MACROECONOMIC, AnalyticalLevel.SHORT_RUN_MACRO),
    ]
    routed = sectioning.route_models_to_sections(models, routes)
    micro_ids = set(routed[short_micro])
    assert "poles_jrc" in micro_ids
    assert "ggm" in micro_ids
    assert "simrlfab" in micro_ids
    # NEMS is a macro-tier macroeconomic model and must NOT land in MICRO.
    assert "nems" not in micro_ids


def test_macro_section_includes_macro_tier() -> None:
    routes = sectioning.default_section_routes()
    short_macro = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MACRO)
    long_macro = sectioning.SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.MACRO)
    models = [
        _meta("nems", CommoditySystem.MACROECONOMIC, AnalyticalLevel.SHORT_RUN_MACRO),
        _meta("opencge", CommoditySystem.MACROECONOMIC, AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC),
        _meta("temoa", CommoditySystem.ENERGY_SYSTEMS, AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC),
        _meta("poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY),
    ]
    routed = sectioning.route_models_to_sections(models, routes)
    assert "nems" in routed[short_macro]
    assert "opencge" in routed[long_macro]
    assert "temoa" in routed[long_macro]
    # Commodity-tier oil model should not land in macro.
    assert "poles_jrc" not in routed[short_macro]
    assert "poles_jrc" not in routed[long_macro]


def test_strategic_section_includes_shipping() -> None:
    routes = sectioning.default_section_routes()
    short_strat = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.STRATEGIC)
    long_strat = sectioning.SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.STRATEGIC)
    models = [
        _meta("aisdb", CommoditySystem.SHIPPING, AnalyticalLevel.COMMODITY),
        _meta("opencge", CommoditySystem.MACROECONOMIC, AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC),
    ]
    routed = sectioning.route_models_to_sections(models, routes)
    assert "aisdb" in routed[short_strat]
    assert "aisdb" in routed[long_strat]
    assert "opencge" in routed[long_strat]


def test_empty_section_returned_for_unmatched_models() -> None:
    routes = sectioning.default_section_routes()
    short_macro = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MACRO)
    routed = sectioning.route_models_to_sections([], routes)
    # Every section key still appears, with an empty list.
    assert short_macro in routed
    assert routed[short_macro] == []


# --------------------------------------------------------------------
# YAML overrides
# --------------------------------------------------------------------


def test_yaml_override_replaces_default_route(tmp_path: Path) -> None:
    yaml_path = tmp_path / "synthesis_sectioning.yaml"
    yaml_path.write_text(
        """
sections:
  - time_horizon: short_run
    outcome_scope: macro
    analytical_levels: [combat]
    commodity_systems_include: [shipping]
"""
    )
    routes = sectioning.load_section_routes(yaml_path)
    short_macro = next(
        r for r in routes
        if r.key == sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MACRO)
    )
    assert short_macro.analytical_levels == {AnalyticalLevel.COMBAT}
    assert short_macro.commodity_systems_include == {CommoditySystem.SHIPPING}


def test_yaml_missing_falls_back_to_defaults(tmp_path: Path) -> None:
    routes = sectioning.load_section_routes(tmp_path / "does_not_exist.yaml")
    assert len(routes) == 6


def test_yaml_invalid_entry_skipped_not_fatal(tmp_path: Path) -> None:
    yaml_path = tmp_path / "synthesis_sectioning.yaml"
    yaml_path.write_text(
        """
sections:
  - time_horizon: short_run
    outcome_scope: NOT_A_SCOPE
  - time_horizon: long_run
    outcome_scope: macro
    analytical_levels: [long_run_macro_strategic]
"""
    )
    # The bad entry is logged and skipped; the good one applies.
    routes = sectioning.load_section_routes(yaml_path)
    assert len(routes) == 6
    long_macro = next(
        r for r in routes
        if r.key == sectioning.SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.MACRO)
    )
    assert long_macro.analytical_levels == {AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC}
