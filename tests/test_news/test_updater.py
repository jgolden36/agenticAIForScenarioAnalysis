"""Tests for the automatic weekly update driver (src/news/updater.py).

Uses a fake registered news source, an injected summarise_fn, and an
injected pipeline_runner so no network, LLM, or domain model is
touched. Exercises the fetch -> brief -> YAML -> materiality gate ->
rerun decision -> summary chain end to end.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml

from src.news.aggregator import register
from src.news.base import NewsArticle, NewsSource
from src.news.materiality import MaterialityConfig
from src.news.summarizer import ObservedIndicator, WeeklyBrief
from src.news.updater import find_previous_brief, run_weekly_update
from src.pipeline.config import PipelineConfig
from src.pipeline.state import PipelineState


class FakeSource(NewsSource):
    """Deterministic in-memory source; article count set per test."""

    name = "fake"
    requires_api_key = False
    articles_to_return: int = 3  # class-level knob

    def fetch(self, start, end, query, max_results=100):
        return [
            NewsArticle(
                source="fake",
                title=f"Article {i} ({start.isoformat()})",
                url=f"https://example.com/{start.isoformat()}/{i}",
                published_at=datetime(
                    start.year, start.month, start.day, tzinfo=timezone.utc
                ),
                description="Brent at $128/bbl.",
            )
            for i in range(type(self).articles_to_return)
        ]


register("fake", FakeSource)


@pytest.fixture
def env(tmp_path: Path):
    """Config files + directories for an isolated updater run."""
    baseline = tmp_path / "baseline.yaml"
    baseline.write_text(
        yaml.safe_dump({"name": "Hormuz", "description": "Baseline crisis."}),
        encoding="utf-8",
    )
    sources_config = tmp_path / "sources.yaml"
    sources_config.write_text(
        yaml.safe_dump(
            {
                "crisis": {"name": "Hormuz Closure", "date": "2026-02"},
                "query": "Hormuz",
                "sources": [{"name": "fake"}],
            }
        ),
        encoding="utf-8",
    )
    framework = tmp_path / "framework.yaml"
    framework.write_text(yaml.safe_dump({}), encoding="utf-8")
    FakeSource.articles_to_return = 3
    return {
        "baseline": baseline,
        "sources_config": sources_config,
        "framework_path": framework,
        "news_dir": tmp_path / "news",
        "weekly_crisis_dir": tmp_path / "weekly",
        "reports_dir": tmp_path / "reports",
        "state_dir": tmp_path / "state",
        "pipeline_config": PipelineConfig(),
    }


def _summarise_fn(indicators):
    """Build a summarise_week stand-in emitting the given indicators."""

    def _fn(*, week_start, week_end, articles, **kwargs):
        return WeeklyBrief(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            headline=f"{len(articles)} articles this week",
            summary="Deterministic test brief.",
            observed_indicators=[ObservedIndicator(**i) for i in indicators],
        )

    return _fn


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, crisis_description: str, run_id: str) -> PipelineState:
        self.calls.append((crisis_description, run_id))
        return PipelineState(run_id=run_id, crisis_description=crisis_description)


def _run(env, as_of, indicators, runner, **kwargs):
    return run_weekly_update(
        as_of=as_of,
        llm=object(),  # unused by the injected summarise_fn
        summarise_fn=_summarise_fn(indicators),
        pipeline_runner=runner,
        **env,
        **kwargs,
    )


def test_first_week_runs_pipeline_and_writes_artifacts(env):
    runner = RecordingRunner()
    outcome = _run(
        env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], runner
    )

    assert outcome.materiality.material
    assert outcome.pipeline_ran
    assert outcome.run_id == "weekly_20260301"
    assert len(runner.calls) == 1
    crisis_description, run_id = runner.calls[0]
    # The orchestrator received the augmented weekly description.
    assert "Baseline crisis." in crisis_description
    assert "3 articles this week" in crisis_description

    week_dir = env["news_dir"] / "2026-03-01"
    assert (week_dir / "articles.json").exists()
    assert (week_dir / "report.json").exists()
    assert (week_dir / "brief.txt").exists()
    assert (week_dir / "brief.json").exists()
    assert (env["weekly_crisis_dir"] / "2026-03-01.yaml").exists()
    assert outcome.state_path is not None and outcome.state_path.exists()

    summary = json.loads(outcome.summary_json_path.read_text(encoding="utf-8"))
    assert summary["pipeline_ran"] is True
    assert summary["materiality"]["material"] is True
    assert summary["observed_indicators"][0]["name"] == "brent"
    assert outcome.summary_md_path.exists()


def test_unchanged_week_skips_pipeline(env):
    runner = RecordingRunner()
    _run(env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], runner)
    outcome = _run(
        env, date(2026, 3, 15), [{"name": "brent", "value": 102.0}], runner
    )

    assert not outcome.materiality.material
    assert not outcome.pipeline_ran
    assert len(runner.calls) == 1  # only the first week ran
    summary = json.loads(outcome.summary_json_path.read_text(encoding="utf-8"))
    assert summary["pipeline_ran"] is False
    # Deltas are still recorded for auditability.
    assert summary["materiality"]["indicator_deltas"][0]["change_pct"] == 2.0


def test_material_move_triggers_rerun(env):
    runner = RecordingRunner()
    _run(env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], runner)
    outcome = _run(
        env, date(2026, 3, 15), [{"name": "brent", "value": 130.0}], runner
    )

    assert outcome.materiality.material
    assert outcome.pipeline_ran
    assert len(runner.calls) == 2
    assert runner.calls[1][1] == "weekly_20260308"


def test_force_rerun_overrides_immaterial_week(env):
    runner = RecordingRunner()
    _run(env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], runner)
    outcome = _run(
        env,
        date(2026, 3, 15),
        [{"name": "brent", "value": 101.0}],
        runner,
        force_rerun=True,
    )
    assert not outcome.materiality.material
    assert outcome.pipeline_ran
    assert len(runner.calls) == 2


def test_skip_pipeline_builds_brief_only(env):
    runner = RecordingRunner()
    outcome = _run(
        env,
        date(2026, 3, 8),
        [{"name": "brent", "value": 100.0}],
        runner,
        skip_pipeline=True,
    )
    assert outcome.materiality.material
    assert not outcome.pipeline_ran
    assert runner.calls == []
    assert (env["news_dir"] / "2026-03-01" / "brief.json").exists()


def test_zero_article_week_is_immaterial(env):
    runner = RecordingRunner()
    _run(env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], runner)
    FakeSource.articles_to_return = 0
    outcome = _run(
        env, date(2026, 3, 15), [{"name": "brent", "value": 500.0}], runner
    )
    assert not outcome.materiality.material
    assert not outcome.pipeline_ran
    assert len(runner.calls) == 1


def test_pipeline_failure_is_recorded_not_raised(env):
    def _boom(crisis_description: str, run_id: str):
        raise RuntimeError("orchestrator exploded")

    outcome = _run(
        env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], _boom
    )
    assert not outcome.pipeline_ran
    assert outcome.errors and "exploded" in outcome.errors[0]
    # Brief artefacts survive the failure.
    assert (env["news_dir"] / "2026-03-01" / "brief.json").exists()


def test_materiality_threshold_is_configurable(env):
    runner = RecordingRunner()
    _run(env, date(2026, 3, 8), [{"name": "brent", "value": 100.0}], runner)
    outcome = _run(
        env,
        date(2026, 3, 15),
        [{"name": "brent", "value": 102.0}],
        runner,
        materiality_config=MaterialityConfig(indicator_change_threshold_pct=1.0),
    )
    assert outcome.materiality.material
    assert outcome.pipeline_ran


def test_find_previous_brief_picks_latest_before_date(tmp_path: Path):
    news = tmp_path / "news"
    for day, value in [("2026-03-01", 100.0), ("2026-03-08", 110.0)]:
        d = news / day
        d.mkdir(parents=True)
        (d / "brief.json").write_text(
            json.dumps({"observed_indicators": [{"name": "brent", "value": value}]}),
            encoding="utf-8",
        )
        (d / "brief.txt").write_text(f"brief {day}", encoding="utf-8")

    brief_dict, brief_text = find_previous_brief(news, date(2026, 3, 15))
    assert brief_dict["observed_indicators"][0]["value"] == 110.0
    assert brief_text == "brief 2026-03-08"

    # Nothing before the first week.
    assert find_previous_brief(news, date(2026, 3, 1)) == (None, None)
