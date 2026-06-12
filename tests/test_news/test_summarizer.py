"""Tests for the structured observed_indicators on WeeklyBrief."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from src.news.summarizer import (
    ObservedIndicator,
    WeeklyBrief,
    render_brief_as_text,
    write_updated_crisis_yaml,
)


def _brief() -> WeeklyBrief:
    return WeeklyBrief(
        week_start="2026-03-01",
        week_end="2026-03-08",
        headline="Brent spikes as transits halt",
        summary="Tanker transits fell to zero; Brent rose to $128/bbl.",
        key_indicators=["Brent spot price: $128/bbl (+12% w/w)"],
        observed_indicators=[
            ObservedIndicator(
                name="brent_spot_usd_bbl",
                value=128.0,
                unit="USD/bbl",
                change_pct=12.0,
                source="EIA",
            ),
            ObservedIndicator(name="hormuz_daily_transits", value=0.0),
        ],
        scenario_signals=["Scenario B probability raised"],
    )


def test_observed_indicators_written_to_weekly_yaml(tmp_path: Path):
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text(
        yaml.safe_dump({"name": "Hormuz", "description": "Baseline."}),
        encoding="utf-8",
    )
    out = tmp_path / "weekly" / "2026-03-01.yaml"
    write_updated_crisis_yaml(
        baseline_path=baseline,
        output_path=out,
        brief=_brief(),
        week_start=date(2026, 3, 1),
        week_end=date(2026, 3, 8),
    )
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    observed = data["recent_developments"]["observed_indicators"]
    assert len(observed) == 2
    assert observed[0]["name"] == "brent_spot_usd_bbl"
    assert observed[0]["value"] == 128.0
    assert observed[0]["unit"] == "USD/bbl"
    # the weekly_briefs history carries them too
    assert data["weekly_briefs"][0]["observed_indicators"][0]["value"] == 128.0


def test_render_brief_as_text_includes_observed_indicators():
    text = render_brief_as_text(_brief())
    assert "Observed indicators (machine-readable):" in text
    assert "brent_spot_usd_bbl = 128.0 USD/bbl (+12.0% w/w)" in text
    assert "hormuz_daily_transits = 0.0" in text


def test_brief_round_trips_through_json():
    brief = _brief()
    restored = WeeklyBrief.model_validate_json(brief.model_dump_json())
    assert restored.observed_indicators[0].name == "brent_spot_usd_bbl"
    assert restored.observed_indicators[0].change_pct == 12.0
