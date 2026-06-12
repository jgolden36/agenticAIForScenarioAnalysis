"""Tests for src/news/materiality.py (rerun gating for Module 6)."""

from __future__ import annotations

from src.news.materiality import (
    MaterialityConfig,
    assess_materiality,
)
from src.news.summarizer import ObservedIndicator, WeeklyBrief


def _brief(indicators=None, actors=None, week="2026-03-01") -> WeeklyBrief:
    return WeeklyBrief(
        week_start=week,
        week_end=week,
        headline="h",
        summary="s",
        observed_indicators=[ObservedIndicator(**i) for i in (indicators or [])],
        new_actors_or_commodities=actors or [],
    )


def test_first_brief_is_always_material():
    a = assess_materiality(_brief(), previous_brief=None, n_articles=10)
    assert a.material
    assert "baseline" in a.reasons[0].lower()


def test_zero_articles_is_immaterial():
    prev = _brief([{"name": "brent_spot_usd_bbl", "value": 90.0}])
    curr = _brief([{"name": "brent_spot_usd_bbl", "value": 200.0}])
    a = assess_materiality(curr, previous_brief=prev, n_articles=0)
    assert not a.material


def test_small_indicator_move_is_immaterial():
    prev = _brief([{"name": "brent_spot_usd_bbl", "value": 100.0}])
    curr = _brief([{"name": "brent_spot_usd_bbl", "value": 104.0}])
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert not a.material
    assert len(a.indicator_deltas) == 1
    delta = a.indicator_deltas[0]
    assert delta.change_pct == 4.0
    assert not delta.material


def test_large_indicator_move_is_material():
    prev = _brief([{"name": "brent_spot_usd_bbl", "value": 100.0}])
    curr = _brief([{"name": "brent_spot_usd_bbl", "value": 125.0}])
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert a.material
    assert any("brent_spot_usd_bbl" in r for r in a.reasons)


def test_threshold_is_configurable():
    prev = _brief([{"name": "x", "value": 100.0}])
    curr = _brief([{"name": "x", "value": 104.0}])
    cfg = MaterialityConfig(indicator_change_threshold_pct=2.0)
    assert assess_materiality(curr, previous_brief=prev, n_articles=5, config=cfg).material


def test_indicator_names_are_normalised_for_matching():
    prev = _brief([{"name": "Brent Spot USD bbl", "value": 100.0}])
    curr = _brief([{"name": "brent_spot_usd_bbl", "value": 101.0}])
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert not a.material
    assert a.indicator_deltas[0].previous == 100.0


def test_new_actors_are_material():
    prev = _brief([{"name": "x", "value": 1.0}])
    curr = _brief([{"name": "x", "value": 1.0}], actors=["Houthi forces"])
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert a.material
    assert any("Houthi" in r for r in a.reasons)


def test_new_indicator_not_material_by_default():
    prev = _brief([{"name": "x", "value": 1.0}])
    curr = _brief(
        [{"name": "x", "value": 1.0}, {"name": "y", "value": 7.0}]
    )
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert not a.material
    cfg = MaterialityConfig(treat_new_indicators_as_material=True)
    assert assess_materiality(curr, previous_brief=prev, n_articles=5, config=cfg).material


def test_previous_brief_accepts_dict_form():
    """Briefs persisted as JSON round-trip through assess_materiality."""
    prev = _brief([{"name": "x", "value": 100.0}]).model_dump()
    curr = _brief([{"name": "x", "value": 150.0}])
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert a.material


def test_zero_previous_value_handled():
    prev = _brief([{"name": "x", "value": 0.0}])
    curr = _brief([{"name": "x", "value": 3.0}])
    a = assess_materiality(curr, previous_brief=prev, n_articles=5)
    assert a.material
    assert a.indicator_deltas[0].change_pct is None
