"""Selecting what to rerun from a comparison batch must match what actually failed."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("slurm.scripts.run_model_comparison")

from scripts.revision.rerun_failed_backend_runs import new_backend_runs, parse_caps, previous_brief, select_failed  # noqa: E402
from src.news.base import NewsArticle  # noqa: E402
from src.news.summarizer import WeeklyBrief  # noqa: E402


def test_select_failed_finds_brief_failures_and_empty_scenarios(tmp_path: Path) -> None:
    (tmp_path / "empty_scenarios.json").write_text(json.dumps({"scenario_narratives": []}), encoding="utf-8")
    (tmp_path / "good_scenarios.json").write_text(json.dumps({"scenario_narratives": [{}] * 5}), encoding="utf-8")
    runs = [
        {"run_id": "good", "status": "ok", "tag": "b", "week_start": "2026-02-15"},
        {"run_id": "empty", "status": "ok", "tag": "b", "week_start": "2026-02-22"},
        {"run_id": "nobrief", "status": "brief_failed", "tag": "a", "week_start": "2026-02-15"},
    ]
    selected = select_failed(runs, tmp_path)
    assert [(r["run_id"], r["failure"], r["resume"]) for r in selected] == [
        ("nobrief", "brief_failed", "brief"),
        ("empty", "zero_scenarios", "scenarios"),
    ]


def test_previous_brief_prefers_latest_week_then_first_root(tmp_path: Path) -> None:
    new, old = tmp_path / "new", tmp_path / "old"
    weeks = ["2026-02-15", "2026-02-22", "2026-03-01"]
    for root, week, text in ((old, "2026-02-15", "old"), (old, "2026-02-22", "old"), (new, "2026-02-22", "new"), (old, "2026-03-01", "future")):
        path = root / week / "tag" / "brief.txt"
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
    assert previous_brief("tag", "2026-03-01", weeks, new, old) == new / "2026-02-22" / "tag" / "brief.txt"
    assert previous_brief("tag", "2026-02-22", weeks, new, old) == old / "2026-02-15" / "tag" / "brief.txt"
    assert previous_brief("tag", "2026-02-15", weeks, new, old) is None


def test_previous_brief_skips_empty_files(tmp_path: Path) -> None:
    path = tmp_path / "2026-02-15" / "tag" / "brief.txt"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    assert previous_brief("tag", "2026-02-22", ["2026-02-15", "2026-02-22"], tmp_path) is None


def test_brief_script_accepts_every_flag_the_rerun_passes() -> None:
    """The rerun failed once on a flag the brief script no longer had."""
    root = Path(__file__).resolve().parents[2]
    source = (root / "scripts" / "revision" / "rerun_failed_backend_runs.py").read_text(encoding="utf-8")
    block = source[source.index("brief_args = ["):source.index("prev = previous_brief")]
    flags = set(re.findall(r'"(--[a-z-]+)"', block))
    assert "--articles-in" in flags
    helptext = subprocess.run([sys.executable, str(root / "slurm" / "scripts" / "build_weekly_brief.py"), "--help"],
                              capture_output=True, text=True, check=True).stdout
    accepted = set(re.findall(r"--[a-z-]+", helptext))
    assert flags <= accepted


def test_cached_articles_round_trip() -> None:
    """Saved articles must load back, including a missing publication date."""
    article = NewsArticle(source="eia", title="t", url="u", published_at=datetime(2026, 2, 15, 12, 0), raw={"v": 1.5})
    assert NewsArticle.from_dict(article.to_dict()) == article
    undated = NewsArticle.from_dict({"source": "s", "title": "t", "url": "u", "published_at": None, "extra": "ignored"})
    assert undated.published_at is None


def test_new_backend_runs_cover_every_week_once() -> None:
    runs = [{"week_start": w, "week_end": e, "tag": t} for t in ("a", "b") for w, e in (("2026-02-22", "2026-03-01"), ("2026-02-15", "2026-02-22"))]
    todo = new_backend_runs(runs, ["new"])
    assert [(r["tag"], r["week_start"], r["week_end"], r["resume"]) for r in todo] == [
        ("new", "2026-02-15", "2026-02-22", "brief"),
        ("new", "2026-02-22", "2026-03-01", "brief"),
    ]


@pytest.mark.parametrize("field", ["key_indicators", "scenario_signals", "new_actors_or_commodities", "coverage_gaps"])
def test_weekly_brief_splits_list_field_returned_as_text(field: str) -> None:
    base = {"week_start": "2026-02-22", "week_end": "2026-03-01", "headline": "h", "summary": "s"}
    text = "- Brent spot: $112/bbl (+8% w/w); stated\n\n* Second item\nThird item"
    assert getattr(WeeklyBrief(**base, **{field: text}), field) == ["Brent spot: $112/bbl (+8% w/w); stated", "Second item", "Third item"]
    assert getattr(WeeklyBrief(**base, **{field: ["kept", "as list"]}), field) == ["kept", "as list"]


def test_parse_caps() -> None:
    assert parse_caps(["anthropic-sonnet-4-6=32000", "anthropic-opus-4-8=32000"]) == {"anthropic-sonnet-4-6": 32000, "anthropic-opus-4-8": 32000}
