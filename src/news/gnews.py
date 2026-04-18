"""GNews API adapter.

GNews exposes `/api/v4/search` with `from`/`to` parameters in
ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`). The free tier returns up to 10
articles per request and 100 requests per day. Historical search is
available on the Essential / Pro tiers; the free tier truncates the
window to the last 24 hours and we surface a warning when that
happens.

Auth: API key via the `apikey` query parameter. Default env var:
`GNEWS_API_KEY`.

Docs: https://gnews.io/docs/v4
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timezone
from typing import Any

from src.common.logging import get_logger
from src.news.base import NewsArticle, NewsSource, NewsSourceError

logger = get_logger(__name__)


class GNewsSource(NewsSource):
    name = "gnews"
    requires_api_key = True

    BASE_URL = "https://gnews.io/api/v4/search"
    PAGE_SIZE = 10  # Free-tier hard cap.
    MAX_PAGE_SIZE = 100  # Pro tier.

    def __init__(
        self,
        api_key: str | None = None,
        language: str = "en",
        country: str | None = None,
        in_fields: str = "title,description,content",
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("GNEWS_API_KEY")
        self.language = language
        self.country = country
        self.in_fields = in_fields
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
                "GNEWS_API_KEY env var (or api_key in config) is required.",
            )

        try:
            import requests
        except ImportError as exc:
            raise NewsSourceError(
                self.name,
                "Missing 'requests' dependency. Install with: "
                "pip install -e \".[news]\"",
            ) from exc

        page_size = min(self.MAX_PAGE_SIZE, max_results)
        params = {
            "q": query,
            "lang": self.language,
            "max": page_size,
            "from": _iso(start, time.min),
            "to": _iso(end, time.min),
            "in": self.in_fields,
            "sortby": "publishedAt",
            "apikey": self.api_key,
        }
        if self.country:
            params["country"] = self.country

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise NewsSourceError(self.name, str(exc)) from exc

        if resp.status_code == 403:
            raise NewsSourceError(
                self.name,
                "HTTP 403 (forbidden). The free tier of GNews does not "
                "support historical search; upgrade to Essential/Pro "
                "or use a different source for past weeks.",
            )
        if resp.status_code != 200:
            raise NewsSourceError(
                self.name,
                f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        payload = resp.json()
        articles: list[NewsArticle] = []
        for r in payload.get("articles", []) or []:
            published = _parse_dt(r.get("publishedAt"))
            if published and not (start <= published.date() < end):
                continue
            src = (r.get("source") or {}).get("name") or "gnews"
            articles.append(
                NewsArticle(
                    source=f"gnews:{src}",
                    title=r.get("title", "") or "",
                    url=r.get("url", "") or "",
                    published_at=published or datetime.now(timezone.utc),
                    description=r.get("description", "") or "",
                    content=r.get("content", "") or "",
                    raw=r,
                )
            )
            if len(articles) >= max_results:
                break

        logger.info("gnews: fetched %d articles for %s..%s", len(articles), start, end)
        return articles


def _iso(d: date, t: time) -> str:
    return datetime.combine(d, t, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
