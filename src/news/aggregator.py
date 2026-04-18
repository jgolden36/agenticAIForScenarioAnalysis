"""News aggregator: fan out a query across many sources and dedup.

The aggregator is intentionally permissive: a single source failing
(missing API key, rate limited, paid-tier endpoint) is recorded but
does not cause the whole fetch to fail. The resulting `FetchReport`
records which sources succeeded, which raised, and how many articles
each contributed -- this report is logged into the per-week brief
JSON for full provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.common.logging import get_logger
from src.news.base import NewsArticle, NewsSource, NewsSourceError

logger = get_logger(__name__)


_REGISTRY: dict[str, type[NewsSource]] = {}


def register(name: str, cls: type[NewsSource]) -> None:
    """Register a NewsSource subclass under a short name."""
    _REGISTRY[name.lower()] = cls


def _autoregister() -> None:
    """Lazy-import all built-in adapters so YAML configs can name them.

    Imports are local to this function so users can install only the
    [news] extra they actually want to use without crashing the
    registry on a missing dependency.
    """
    try:
        from src.news.newsdata import NewsDataIOSource
        register("newsdata.io", NewsDataIOSource)
        register("newsdata", NewsDataIOSource)
    except ImportError:
        pass
    try:
        from src.news.gnews import GNewsSource
        register("gnews", GNewsSource)
    except ImportError:
        pass
    try:
        from src.news.newsapi import NewsAPIAISource, NewsAPIOrgSource
        register("newsapi.org", NewsAPIOrgSource)
        register("newsapi.ai", NewsAPIAISource)
    except ImportError:
        pass
    try:
        from src.news.eia import EIASource
        register("eia", EIASource)
    except ImportError:
        pass


_autoregister()


def build_source_from_config(spec: dict[str, Any]) -> NewsSource:
    """Construct a NewsSource from a YAML config entry.

    The YAML entry must include a `name` field naming a registered
    adapter; remaining fields are passed as keyword arguments. Example:

        - name: gnews
          language: en
          country: us
    """
    name = spec.get("name")
    if not name:
        raise ValueError("News source spec missing required 'name' field.")
    cls = _REGISTRY.get(str(name).lower())
    if not cls:
        raise ValueError(
            f"Unknown news source {name!r}. Registered: {sorted(_REGISTRY)}"
        )
    kwargs = {k: v for k, v in spec.items() if k != "name"}
    return cls(**kwargs)


@dataclass
class FetchReport:
    """Per-week summary of which sources contributed what."""

    week_start: date
    week_end: date
    query: str
    successes: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    total_articles: int = 0
    deduped_articles: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "query": self.query,
            "successes": self.successes,
            "failures": self.failures,
            "total_articles": self.total_articles,
            "deduped_articles": self.deduped_articles,
        }


@dataclass
class NewsAggregator:
    """Fan out a query to multiple sources and merge the results.

    Args:
        sources: Configured NewsSource adapters to query in order.
        per_source_limit: Soft cap on articles per source per week.
            Keeps the brief tractable when a single feed is verbose.
    """

    sources: list[NewsSource]
    per_source_limit: int = 50

    def fetch_week(
        self,
        start: date,
        end: date,
        query: str,
    ) -> tuple[list[NewsArticle], FetchReport]:
        report = FetchReport(week_start=start, week_end=end, query=query)
        merged: dict[str, NewsArticle] = {}

        for source in self.sources:
            try:
                articles = source.fetch(
                    start=start, end=end, query=query, max_results=self.per_source_limit
                )
            except NewsSourceError as exc:
                logger.warning("source %s failed: %s", source.name, exc.message)
                report.failures[source.name] = exc.message
                continue
            except Exception as exc:  # defensive: never crash the run
                logger.exception("source %s raised unexpected: %s", source.name, exc)
                report.failures[source.name] = f"Unexpected: {exc!s}"
                continue

            report.successes[source.name] = len(articles)
            report.total_articles += len(articles)
            for art in articles:
                key = art.fingerprint()
                if key not in merged:
                    merged[key] = art

        # Stable ordering by date desc so the summariser sees the most
        # recent items first (LLMs weight earlier-context tokens more
        # heavily, which here is what we want).
        deduped = sorted(
            merged.values(),
            key=lambda a: a.published_at,
            reverse=True,
        )
        report.deduped_articles = len(deduped)
        logger.info(
            "aggregated %d articles (%d after dedup) for %s..%s",
            report.total_articles,
            report.deduped_articles,
            start,
            end,
        )
        return deduped, report
