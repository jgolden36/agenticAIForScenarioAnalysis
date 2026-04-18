"""NewsAPI.org and NewsAPI.ai adapters.

Two distinct providers share a *very* similar shape, so we expose
both behind one module:

* `NewsAPIOrgSource` (``newsapi.org``) - simpler, the developer tier
  is capped to the last 30 days.
* `NewsAPIAISource`  (``newsapi.ai`` / Event Registry) - richer
  semantic queries; historical search supported on most paid tiers.

Auth env vars:
    NEWSAPI_ORG_API_KEY    -> NewsAPI.org
    NEWSAPI_AI_API_KEY     -> NewsAPI.ai (Event Registry)

Docs:
    https://newsapi.org/docs
    https://newsapi.ai/documentation
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from src.common.logging import get_logger
from src.news.base import NewsArticle, NewsSource, NewsSourceError

logger = get_logger(__name__)


class NewsAPIOrgSource(NewsSource):
    name = "newsapi.org"
    requires_api_key = True

    BASE_URL = "https://newsapi.org/v2/everything"
    PAGE_SIZE = 100  # API max.

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("NEWSAPI_ORG_API_KEY")
        self.language = language
        self.sort_by = sort_by
        self.timeout = timeout

    def fetch(
        self,
        start: date,
        end: date,
        query: str,
        max_results: int = 100,
    ) -> list[NewsArticle]:
        if not self.api_key:
            raise NewsSourceError(
                self.name,
                "NEWSAPI_ORG_API_KEY env var (or api_key in config) is required.",
            )

        try:
            import requests
        except ImportError as exc:
            raise NewsSourceError(
                self.name,
                "Missing 'requests' dependency. Install with: "
                "pip install -e \".[news]\"",
            ) from exc

        articles: list[NewsArticle] = []
        page = 1
        per_page = min(self.PAGE_SIZE, max_results)

        while len(articles) < max_results:
            params = {
                "q": query,
                "from": start.isoformat(),
                "to": end.isoformat(),
                "language": self.language,
                "sortBy": self.sort_by,
                "pageSize": per_page,
                "page": page,
                "apiKey": self.api_key,
            }
            try:
                resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                raise NewsSourceError(self.name, str(exc)) from exc

            if resp.status_code == 426:
                raise NewsSourceError(
                    self.name,
                    "HTTP 426: developer plan only allows the last 30 days. "
                    "Upgrade or use a different source for older weeks.",
                )
            if resp.status_code != 200:
                raise NewsSourceError(
                    self.name,
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            payload = resp.json()
            results = payload.get("articles", []) or []
            if not results:
                break
            for r in results:
                published = _parse_dt(r.get("publishedAt"))
                src = (r.get("source") or {}).get("name") or "newsapi.org"
                articles.append(
                    NewsArticle(
                        source=f"newsapi.org:{src}",
                        title=r.get("title", "") or "",
                        url=r.get("url", "") or "",
                        published_at=published or datetime.now(timezone.utc),
                        description=r.get("description", "") or "",
                        content=r.get("content", "") or "",
                        author=r.get("author"),
                        raw=r,
                    )
                )
                if len(articles) >= max_results:
                    break

            total = int(payload.get("totalResults", 0))
            if page * per_page >= total:
                break
            page += 1

        logger.info("newsapi.org: fetched %d articles for %s..%s", len(articles), start, end)
        return articles


class NewsAPIAISource(NewsSource):
    name = "newsapi.ai"
    requires_api_key = True

    BASE_URL = "https://eventregistry.org/api/v1/article/getArticles"
    PAGE_SIZE = 100

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "eng",
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("NEWSAPI_AI_API_KEY")
        self.language = language
        self.timeout = timeout

    def fetch(
        self,
        start: date,
        end: date,
        query: str,
        max_results: int = 100,
    ) -> list[NewsArticle]:
        if not self.api_key:
            raise NewsSourceError(
                self.name,
                "NEWSAPI_AI_API_KEY env var (or api_key in config) is required.",
            )

        try:
            import requests
        except ImportError as exc:
            raise NewsSourceError(
                self.name,
                "Missing 'requests' dependency. Install with: "
                "pip install -e \".[news]\"",
            ) from exc

        # NewsAPI.ai uses Event Registry's complex query DSL. We
        # construct the simplest possible "all of these keywords"
        # query plus a date range and a language filter.
        body = {
            "action": "getArticles",
            "keyword": query,
            "lang": self.language,
            "dateStart": start.isoformat(),
            "dateEnd": (end.isoformat()),
            "articlesPage": 1,
            "articlesCount": min(self.PAGE_SIZE, max_results),
            "articlesSortBy": "date",
            "resultType": "articles",
            "apiKey": self.api_key,
        }

        try:
            resp = requests.post(self.BASE_URL, json=body, timeout=self.timeout)
        except requests.RequestException as exc:
            raise NewsSourceError(self.name, str(exc)) from exc

        if resp.status_code != 200:
            raise NewsSourceError(
                self.name,
                f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        payload = resp.json().get("articles", {}) or {}
        results = payload.get("results", []) or []
        articles: list[NewsArticle] = []
        for r in results:
            published = _parse_dt(r.get("dateTime") or r.get("date"))
            src = (r.get("source") or {}).get("title") or "newsapi.ai"
            articles.append(
                NewsArticle(
                    source=f"newsapi.ai:{src}",
                    title=r.get("title", "") or "",
                    url=r.get("url", "") or "",
                    published_at=published or datetime.now(timezone.utc),
                    description=(r.get("body", "") or "")[:500],
                    content=r.get("body", "") or "",
                    raw=r,
                )
            )
            if len(articles) >= max_results:
                break

        logger.info("newsapi.ai: fetched %d articles for %s..%s", len(articles), start, end)
        return articles


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
