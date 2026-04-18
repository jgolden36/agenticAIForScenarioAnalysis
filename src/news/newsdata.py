"""NewsData.io adapter.

NewsData.io exposes two relevant endpoints:

* `/api/1/latest`  - last 48 hours, free tier.
* `/api/1/archive` - historical (paid tier required for >180 days
  back, but recent dates are usually allowed on the free trial).

For the temporal Hormuz workflow we always hit `archive` so we can
back-fill weeks between Feb 15 and April 10. The adapter falls back
to the `latest` endpoint when archive responds 403 or 426 (typical
"upgrade your plan" responses) so the pipeline still has *some* data
for the most recent week.

Auth: API key via the `apikey` query parameter. Read from
`NEWSDATA_API_KEY` env var by default; can be overridden in the
config YAML.

Docs: https://newsdata.io/documentation
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from src.common.logging import get_logger
from src.news.base import NewsArticle, NewsSource, NewsSourceError

logger = get_logger(__name__)


class NewsDataIOSource(NewsSource):
    name = "newsdata.io"
    requires_api_key = True

    BASE_URL = "https://newsdata.io/api/1"
    PAGE_SIZE = 50  # API hard cap on free / starter tiers.

    def __init__(
        self,
        api_key: str | None = None,
        country: str | None = None,
        language: str = "en",
        category: str | None = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("NEWSDATA_API_KEY")
        self.country = country
        self.language = language
        self.category = category
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
                "NEWSDATA_API_KEY env var (or api_key in config) is required.",
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
        params = {
            "apikey": self.api_key,
            "q": query,
            "from_date": start.isoformat(),
            "to_date": (end.isoformat()),
            "language": self.language,
            "size": min(self.PAGE_SIZE, max_results),
        }
        if self.country:
            params["country"] = self.country
        if self.category:
            params["category"] = self.category

        url = f"{self.BASE_URL}/archive"
        next_page: str | None = None
        endpoint_name = "archive"

        while len(articles) < max_results:
            if next_page:
                params["page"] = next_page

            try:
                resp = requests.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                raise NewsSourceError(self.name, str(exc)) from exc

            if resp.status_code in (403, 426) and endpoint_name == "archive":
                # Free-tier accounts often can't hit /archive. Fall back
                # to /latest so at least the most recent week works.
                logger.warning(
                    "newsdata.io /archive returned %s; falling back to /latest",
                    resp.status_code,
                )
                url = f"{self.BASE_URL}/latest"
                endpoint_name = "latest"
                params.pop("from_date", None)
                params.pop("to_date", None)
                next_page = None
                continue

            if resp.status_code != 200:
                raise NewsSourceError(
                    self.name,
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            payload = resp.json()
            results = payload.get("results", []) or []
            for r in results:
                published = self._parse_dt(r.get("pubDate"))
                if endpoint_name == "latest" and published:
                    # When we fall back to /latest we still want to
                    # honour the requested date window.
                    if not (start <= published.date() < end):
                        continue
                articles.append(
                    NewsArticle(
                        source=self.name,
                        title=r.get("title", "") or "",
                        url=r.get("link", "") or "",
                        published_at=published or datetime.now(timezone.utc),
                        description=r.get("description", "") or "",
                        content=r.get("content", "") or "",
                        author=", ".join(r.get("creator") or []) or None,
                        language=r.get("language"),
                        raw=r,
                    )
                )
                if len(articles) >= max_results:
                    break

            next_page = payload.get("nextPage")
            if not next_page:
                break

        logger.info("newsdata.io: fetched %d articles for %s..%s", len(articles), start, end)
        return articles

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            # newsdata.io returns "2026-02-20 14:31:09".
            return datetime.fromisoformat(str(value).replace(" ", "T")).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None
