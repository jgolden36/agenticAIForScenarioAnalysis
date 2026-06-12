"""News and government-data ingestion for temporal pipeline reruns.

This subpackage powers the iterative re-analysis workflow: at each
historical week of the crisis, we fetch articles and government
indicators from a configurable set of sources, summarise them with the
pipeline LLM, and emit an updated crisis-description YAML that
re-drives Module 1 (scenario generation). The result is a series of
per-week scenario / model / synthesis runs that show how the framework
adapts as new information arrives.

Public entry points:

    NewsArticle              - canonical article dataclass
    NewsSource               - abstract base for any source adapter
    NewsAggregator           - fan-out over many sources with dedup
    build_source_from_config - factory used by the SLURM brief builder
    summarise_week           - LLM summariser that produces a brief
    write_updated_crisis_yaml- materialise the per-week crisis YAML
    assess_materiality       - decide whether a week warrants a rerun
    run_weekly_update        - one-shot local automatic update cycle
                               (also: ``python -m src.news.updater``)

Adapters live in their own modules so they only import their HTTP
client when actually used (avoids hard requests/feedparser deps when
the pipeline runs without the [news] extra installed).
"""

from __future__ import annotations

from src.news.aggregator import NewsAggregator, build_source_from_config
from src.news.base import NewsArticle, NewsSource, NewsSourceError
from src.news.materiality import (
    MaterialityAssessment,
    MaterialityConfig,
    assess_materiality,
)
from src.news.summarizer import (
    ObservedIndicator,
    WeeklyBrief,
    summarise_week,
    write_updated_crisis_yaml,
)
from src.news.updater import WeeklyUpdateOutcome, run_weekly_update

__all__ = [
    "NewsArticle",
    "NewsSource",
    "NewsSourceError",
    "NewsAggregator",
    "build_source_from_config",
    "summarise_week",
    "write_updated_crisis_yaml",
    "ObservedIndicator",
    "WeeklyBrief",
    "MaterialityAssessment",
    "MaterialityConfig",
    "assess_materiality",
    "WeeklyUpdateOutcome",
    "run_weekly_update",
]
