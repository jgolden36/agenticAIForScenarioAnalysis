"""Materiality assessment for news-driven pipeline reruns.

Re-running Modules 1-4 costs hours of LLM and model time, so the
automatic updater (``src.news.updater``) only reruns the pipeline when
the week's news *materially* changes the picture. This module decides
that, deterministically and without an LLM call, by comparing the
current week's :class:`~src.news.summarizer.WeeklyBrief` against the
previous one:

* First brief ever -> material (the baseline analysis must exist).
* Zero articles fetched -> immaterial (nothing new to react to).
* Any observed indicator whose value moved more than
  ``indicator_change_threshold_pct`` relative to the previous week ->
  material.
* New actors or commodities surfaced by the summariser -> material
  (the scenario space itself may need to change).

Every decision carries human-readable reasons and per-indicator deltas
so the skip/rerun choice is auditable in the weekly update summary --
an analyst can always override with ``--force``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MaterialityConfig:
    """Thresholds controlling when a weekly brief triggers a rerun."""

    # Relative change (percent of the previous value) above which an
    # observed indicator counts as material. 10% catches e.g. a Brent
    # move from $90 to $99 while ignoring daily noise.
    indicator_change_threshold_pct: float = 10.0
    # New actors / commodities imply the scenario space may need to
    # change, which only a full Module 1 rerun can do.
    treat_new_actors_as_material: bool = True
    # Indicators present this week but absent last week. Off by
    # default: LLM naming drift would otherwise cause spurious reruns.
    treat_new_indicators_as_material: bool = False
    # Minimum number of fetched articles for the week to be evaluated
    # at all; below this the week is immaterial regardless of content.
    min_articles: int = 1


@dataclass
class IndicatorDelta:
    """Week-over-week change for one observed indicator."""

    name: str
    previous: float | None
    current: float | None
    change_pct: float | None
    material: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "previous": self.previous,
            "current": self.current,
            "change_pct": self.change_pct,
            "material": self.material,
        }


@dataclass
class MaterialityAssessment:
    """Outcome of the materiality check, with full reasoning."""

    material: bool
    reasons: list[str] = field(default_factory=list)
    indicator_deltas: list[IndicatorDelta] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "material": self.material,
            "reasons": self.reasons,
            "indicator_deltas": [d.to_dict() for d in self.indicator_deltas],
        }


def _normalise_name(name: str) -> str:
    return "_".join(str(name).strip().lower().split())


def _indicators_of(brief: Any) -> dict[str, dict[str, Any]]:
    """Extract ``{normalised_name: indicator_dict}`` from a brief.

    Accepts a :class:`WeeklyBrief`, its ``model_dump()`` dict, or the
    ``recent_developments`` block read back from a weekly crisis YAML,
    so previous-week briefs can be loaded from any persisted form.
    """
    if brief is None:
        return {}
    if hasattr(brief, "observed_indicators"):
        raw = brief.observed_indicators
    elif isinstance(brief, dict):
        raw = brief.get("observed_indicators") or []
    else:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for item in raw:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name:
            continue
        try:
            item = dict(item)
            item["value"] = float(value)
        except (TypeError, ValueError):
            continue
        out[_normalise_name(name)] = item
    return out


def _actors_of(brief: Any) -> list[str]:
    if brief is None:
        return []
    if hasattr(brief, "new_actors_or_commodities"):
        return list(brief.new_actors_or_commodities or [])
    if isinstance(brief, dict):
        return list(brief.get("new_actors_or_commodities") or [])
    return []


def assess_materiality(
    current_brief: Any,
    previous_brief: Any = None,
    n_articles: int | None = None,
    config: MaterialityConfig | None = None,
) -> MaterialityAssessment:
    """Decide whether this week's brief warrants a full pipeline rerun.

    Args:
        current_brief: This week's ``WeeklyBrief`` (or its dict form).
        previous_brief: The previous week's brief in any persisted form
            (``WeeklyBrief``, ``model_dump()`` dict, or the
            ``recent_developments`` block of a weekly crisis YAML).
            ``None`` means there is no prior analysis.
        n_articles: Number of articles fetched this week (post-dedup).
            ``None`` skips the empty-week short-circuit.
        config: Thresholds; defaults to :class:`MaterialityConfig`.

    Returns:
        :class:`MaterialityAssessment` with the decision, reasons, and
        per-indicator deltas (also computed for immaterial weeks so the
        summary shows *how close* the week came to the threshold).
    """
    cfg = config or MaterialityConfig()

    if previous_brief is None:
        return MaterialityAssessment(
            material=True,
            reasons=["No previous brief: baseline analysis run required."],
        )

    if n_articles is not None and n_articles < cfg.min_articles:
        return MaterialityAssessment(
            material=False,
            reasons=[
                f"Only {n_articles} article(s) fetched this week "
                f"(minimum {cfg.min_articles}); nothing new to analyse."
            ],
        )

    reasons: list[str] = []
    deltas: list[IndicatorDelta] = []

    prev = _indicators_of(previous_brief)
    curr = _indicators_of(current_brief)

    for name, item in curr.items():
        current_value = item["value"]
        prev_item = prev.get(name)
        if prev_item is None:
            material = cfg.treat_new_indicators_as_material
            deltas.append(
                IndicatorDelta(
                    name=name,
                    previous=None,
                    current=current_value,
                    change_pct=None,
                    material=material,
                )
            )
            if material:
                reasons.append(
                    f"New indicator observed: {name} = {current_value}."
                )
            continue

        previous_value = prev_item["value"]
        if previous_value == 0:
            change_pct = None
            material = current_value != 0
        else:
            change_pct = (
                (current_value - previous_value) / abs(previous_value) * 100.0
            )
            material = abs(change_pct) > cfg.indicator_change_threshold_pct
        deltas.append(
            IndicatorDelta(
                name=name,
                previous=previous_value,
                current=current_value,
                change_pct=change_pct,
                material=material,
            )
        )
        if material:
            moved = (
                f"{change_pct:+.1f}%"
                if change_pct is not None
                else f"from 0 to {current_value}"
            )
            reasons.append(
                f"Indicator {name} moved {moved} "
                f"(threshold {cfg.indicator_change_threshold_pct}%)."
            )

    if cfg.treat_new_actors_as_material:
        actors = _actors_of(current_brief)
        if actors:
            reasons.append(
                "New actors/commodities surfaced: "
                + ", ".join(str(a) for a in actors)
                + ". The scenario space may need regeneration."
            )

    material = bool(reasons)
    if not material:
        reasons.append(
            "No indicator moved beyond "
            f"{cfg.indicator_change_threshold_pct}% and no new "
            "actors/commodities appeared; previous analysis stands."
        )

    assessment = MaterialityAssessment(
        material=material, reasons=reasons, indicator_deltas=deltas
    )
    logger.info(
        "Materiality: %s (%d indicator deltas) -- %s",
        "MATERIAL" if material else "immaterial",
        len(deltas),
        "; ".join(reasons),
    )
    return assessment
