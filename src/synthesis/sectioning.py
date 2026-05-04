"""Section catalogue + routing for chunked Module 4 synthesis.

The legacy Module 4 synthesizer made one LLM call per scenario and
crammed every completed model's outputs + regional + sectoral +
override-audit blocks into a single prompt. With ~30 adapters and
heavy outputs (NEMS yearly_results, MIRAGRODEP regional_sectoral,
OG-Core sectoral paths) that single prompt routinely blew past the
8K context window served by the SBU AI Cluster vLLM sidecar.

This module declares a *section catalogue*:

    section := (TimeHorizon, OutcomeScope)

with six sections per scenario covering the full
``synthesis_outcomes`` matrix. Each section has a *routing rule* that
maps from (``AnalyticalLevel``, ``CommoditySystem``) to "include this
model in the section's prompt". A model can appear in multiple
sections — that's fine, because each section's prompt only contains
the models genuinely relevant to that ``(time_horizon, outcome_scope)``
pair, which is much smaller than the union of all models.

The defaults below match the routing intuition documented in
``CLAUDE.md`` (Outcome Variables section). Operators can override any
section's rule by dropping a ``configs/synthesis_sectioning.yaml``
file with shape::

    sections:
      - time_horizon: short_run
        outcome_scope: micro
        analytical_levels: [commodity, commodity_downstream]
        commodity_systems_include:
          - water
          - oil
          ...
        commodity_systems_exclude: [shipping]

When a YAML override is present it *replaces* the in-code defaults
for the matching section (so partial overrides should re-state the
levels they want). Sections not listed in the YAML keep the in-code
defaults. This satisfies the CLAUDE.md "configuration over
hardcoding" constraint without forcing every install to ship a YAML.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from src.common.types import (
    AnalyticalLevel,
    CommoditySystem,
    OutcomeScope,
    TimeHorizon,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------
# Routing rule
# --------------------------------------------------------------------


@dataclass(frozen=True)
class SectionKey:
    """A (time_horizon, outcome_scope) section identifier."""

    time_horizon: TimeHorizon
    outcome_scope: OutcomeScope

    def label(self) -> str:
        return f"{self.time_horizon.value}/{self.outcome_scope.value}"


@dataclass
class SectionRoute:
    """Routing predicate for one section."""

    key: SectionKey
    analytical_levels: set[AnalyticalLevel] = field(default_factory=set)
    commodity_systems_include: set[CommoditySystem] | None = None
    commodity_systems_exclude: set[CommoditySystem] = field(default_factory=set)

    def matches(
        self,
        analytical_level: AnalyticalLevel,
        commodity_system: CommoditySystem,
    ) -> bool:
        """Return True if a model with this (level, system) belongs in this section."""
        if self.analytical_levels and analytical_level not in self.analytical_levels:
            return False
        if commodity_system in self.commodity_systems_exclude:
            return False
        if (
            self.commodity_systems_include is not None
            and commodity_system not in self.commodity_systems_include
        ):
            return False
        return True


# --------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------


# Resource commodities that drive the MICRO outcome columns of the
# synthesis matrix (oil/LNG/fertilizer/helium prices, water adequacy,
# semiconductor industry growth). SHIPPING is intentionally excluded
# here and routed to STRATEGIC instead because its outcomes (rerouting
# costs, freedom of navigation) are strategic-tier signals.
_MICRO_COMMODITY_SYSTEMS: set[CommoditySystem] = {
    CommoditySystem.WATER,
    CommoditySystem.OIL,
    CommoditySystem.LNG,
    CommoditySystem.HELIUM_SEMICONDUCTORS,
    CommoditySystem.FERTILIZER_AGRICULTURE,
}

_MACRO_COMMODITY_SYSTEMS: set[CommoditySystem] = {
    CommoditySystem.MACROECONOMIC,
    CommoditySystem.ENERGY_SYSTEMS,
}

_STRATEGIC_COMMODITY_SYSTEMS: set[CommoditySystem] = {
    CommoditySystem.SHIPPING,
    CommoditySystem.MACROECONOMIC,
}


def default_section_routes() -> list[SectionRoute]:
    """Return the in-code default routing rules for all six sections."""
    return [
        # -------- SHORT-RUN sections --------
        SectionRoute(
            key=SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO),
            analytical_levels={
                AnalyticalLevel.COMMODITY,
                AnalyticalLevel.COMMODITY_DOWNSTREAM,
            },
            commodity_systems_include=_MICRO_COMMODITY_SYSTEMS,
        ),
        SectionRoute(
            key=SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MACRO),
            analytical_levels={AnalyticalLevel.SHORT_RUN_MACRO},
        ),
        SectionRoute(
            key=SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.STRATEGIC),
            analytical_levels={
                AnalyticalLevel.COMBAT,
                AnalyticalLevel.COMMODITY,
                AnalyticalLevel.SHORT_RUN_MACRO,
            },
            commodity_systems_include=_STRATEGIC_COMMODITY_SYSTEMS,
        ),
        # -------- LONG-RUN sections --------
        SectionRoute(
            key=SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.MICRO),
            analytical_levels={
                AnalyticalLevel.COMMODITY,
                AnalyticalLevel.COMMODITY_DOWNSTREAM,
            },
            commodity_systems_include=_MICRO_COMMODITY_SYSTEMS,
        ),
        SectionRoute(
            key=SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.MACRO),
            analytical_levels={AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC},
            commodity_systems_include=_MACRO_COMMODITY_SYSTEMS,
        ),
        SectionRoute(
            key=SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.STRATEGIC),
            analytical_levels={
                AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC,
                AnalyticalLevel.COMMODITY,
            },
            commodity_systems_include=_STRATEGIC_COMMODITY_SYSTEMS,
        ),
    ]


# --------------------------------------------------------------------
# YAML override
# --------------------------------------------------------------------


def _parse_enum_list(values: list[str] | None, enum_cls):
    """Parse a list of enum-string values, raising on unknown names."""
    if not values:
        return set()
    out = set()
    for v in values:
        try:
            out.add(enum_cls(v))
        except ValueError as exc:
            raise ValueError(
                f"Unknown {enum_cls.__name__} value {v!r}; "
                f"allowed: {[e.value for e in enum_cls]}"
            ) from exc
    return out


def load_section_routes(
    config_path: Path | str | None = None,
) -> list[SectionRoute]:
    """Load section routes, applying ``configs/synthesis_sectioning.yaml`` overrides.

    When ``config_path`` is None, looks for
    ``<project_root>/configs/synthesis_sectioning.yaml``. Returns the
    in-code defaults when the file is absent (no override case).
    """
    routes = {r.key: r for r in default_section_routes()}

    if config_path is None:
        # Default search path. We intentionally do NOT resolve via
        # SLURM_SUBMIT_DIR here because the synthesis module also runs
        # under the imperative orchestrator outside of SLURM.
        candidate = Path(__file__).resolve().parents[2] / "configs" / "synthesis_sectioning.yaml"
        if candidate.exists():
            config_path = candidate

    if config_path is None:
        return list(routes.values())

    config_path = Path(config_path)
    if not config_path.exists():
        logger.debug(f"No section override at {config_path}; using in-code defaults.")
        return list(routes.values())

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            f"Failed to read {config_path}: {exc}; falling back to in-code defaults."
        )
        return list(routes.values())

    sections_yaml = raw.get("sections", []) or []
    for entry in sections_yaml:
        try:
            key = SectionKey(
                TimeHorizon(entry["time_horizon"]),
                OutcomeScope(entry["outcome_scope"]),
            )
            route = SectionRoute(
                key=key,
                analytical_levels=_parse_enum_list(
                    entry.get("analytical_levels"), AnalyticalLevel
                ),
                commodity_systems_include=(
                    _parse_enum_list(
                        entry.get("commodity_systems_include"), CommoditySystem
                    )
                    or None
                ),
                commodity_systems_exclude=_parse_enum_list(
                    entry.get("commodity_systems_exclude"), CommoditySystem
                ),
            )
            routes[key] = route
        except Exception as exc:
            logger.warning(
                f"Skipping invalid sectioning entry {entry!r} in {config_path}: {exc}"
            )

    return list(routes.values())


# --------------------------------------------------------------------
# Routing API
# --------------------------------------------------------------------


@dataclass
class ModelMetadata:
    """Minimal metadata required to route a model to a section.

    Decoupled from ``ModelAdapter`` so the synthesizer can route on
    just the (model_id, commodity_system, analytical_level) tuple
    without having to import the full registry (which pulls in every
    optional adapter dependency).
    """

    model_id: str
    commodity_system: CommoditySystem
    analytical_level: AnalyticalLevel


def route_models_to_sections(
    models: Iterable[ModelMetadata],
    routes: list[SectionRoute] | None = None,
) -> dict[SectionKey, list[str]]:
    """Bucket model IDs by section.

    Returns a dict keyed by every section in ``routes`` (in declared
    order), with the list of matching model_ids per section. Sections
    with no matching models still appear in the dict with an empty
    list so the caller can decide whether to skip the LLM call for
    that section or emit an empty ``ScopedSynthesis`` placeholder.
    """
    routes = routes or load_section_routes()
    out: dict[SectionKey, list[str]] = {r.key: [] for r in routes}
    for meta in models:
        for route in routes:
            if route.matches(meta.analytical_level, meta.commodity_system):
                out[route.key].append(meta.model_id)
    return out


def lookup_model_metadata(
    model_ids: Iterable[str],
) -> dict[str, ModelMetadata]:
    """Best-effort lookup of (commodity_system, analytical_level) from the registry.

    Models that are not in the registry (e.g. because their optional
    dependency stack is missing in the synthesis-stage environment) are
    omitted. The synthesis caller is expected to fall back to a
    catch-all section for those.
    """
    try:
        from src.models.registry import build_default_registry  # noqa: WPS433
    except Exception as exc:
        logger.debug(f"Could not import registry for sectioning lookup: {exc}")
        return {}

    try:
        registry = build_default_registry()
    except Exception as exc:
        logger.debug(f"Could not build default registry: {exc}")
        return {}

    out: dict[str, ModelMetadata] = {}
    for mid in model_ids:
        adapter = registry.get(mid)
        if adapter is None:
            continue
        out[mid] = ModelMetadata(
            model_id=mid,
            commodity_system=adapter.commodity_system,
            analytical_level=adapter.analytical_level,
        )
    return out


# --------------------------------------------------------------------
# Catch-all section for unrouted models
# --------------------------------------------------------------------


CATCH_ALL_SECTION = SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO)
"""Section that receives models the registry could not classify.

We default to (SHORT_RUN, MICRO) because every commodity-tier model
belongs there and that section is the closest fit for an unknown
adapter. The synthesizer logs a warning when this fallback fires so
operators can add the model to a more appropriate route.
"""


def all_section_keys(routes: list[SectionRoute] | None = None) -> list[SectionKey]:
    """Enumerate the canonical six section keys, in display order."""
    routes = routes or default_section_routes()
    return [r.key for r in routes]
