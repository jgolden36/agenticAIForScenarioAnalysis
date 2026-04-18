"""EIA Open Data API adapter (Government data fallback).

The U.S. Energy Information Administration publishes weekly /
monthly data series (Weekly Petroleum Status Report, Short-Term
Energy Outlook, Natural Gas Weekly, etc.) via a free, key-required
JSON API at:

    https://api.eia.gov/v2/<route>/data/

Although EIA series are not "news articles" in the strict sense, they
are the canonical source of weekly indicators (crude prices, OPEC
spare capacity, LNG export volumes) that we want to feed into the
crisis-update brief alongside text articles. This adapter returns
each weekly observation as a `NewsArticle` whose `description`
encodes the numeric value and unit, so the downstream summariser can
treat it uniformly.

Auth: an API key is required but the registration is free and
instantaneous (https://www.eia.gov/opendata/register.php). Default
env var: ``EIA_API_KEY``. If the key is unset, the adapter raises
`NewsSourceError` rather than silently returning empty.

The default series shipped here cover the indicators most relevant
to the Hormuz case:

    PET.RWTC.W       WTI spot price, weekly
    PET.RBRTE.W      Brent spot price, weekly
    PET.WCRSTUS1.W   US commercial crude stocks, weekly
    NG.RNGWHHD.W     Henry Hub natural gas spot, weekly
    NG.N9132US2.M    US LNG exports, monthly  (closest available)
    STEO.PAPR_WORLD.M World oil supply forecast (STEO), monthly

Override the list via the `series` constructor argument (or the
`series` field in `news_sources.yaml`).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from typing import Any

from src.common.logging import get_logger
from src.news.base import NewsArticle, NewsSource, NewsSourceError

logger = get_logger(__name__)

DEFAULT_SERIES: list[dict[str, str]] = [
    {
        "id": "PET.RWTC.W",
        "label": "WTI crude oil spot price",
        "unit": "USD/bbl",
        "route": "petroleum/pri/spt",
    },
    {
        "id": "PET.RBRTE.W",
        "label": "Brent crude oil spot price",
        "unit": "USD/bbl",
        "route": "petroleum/pri/spt",
    },
    {
        "id": "PET.WCRSTUS1.W",
        "label": "US commercial crude stocks",
        "unit": "kbbl",
        "route": "petroleum/stoc/wstk",
    },
    {
        "id": "NG.RNGWHHD.W",
        "label": "Henry Hub natural gas spot price",
        "unit": "USD/MMBtu",
        "route": "natural-gas/pri/sum",
    },
]


class EIASource(NewsSource):
    name = "eia"
    requires_api_key = True

    BASE_URL = "https://api.eia.gov/v2"

    def __init__(
        self,
        api_key: str | None = None,
        series: list[dict[str, str]] | None = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.api_key = api_key or os.environ.get("EIA_API_KEY")
        self.series = series or DEFAULT_SERIES
        self.timeout = timeout

    def fetch(
        self,
        start: date,
        end: date,
        query: str,  # ignored; series are pre-configured
        max_results: int = 100,
    ) -> list[NewsArticle]:
        if not self.api_key:
            raise NewsSourceError(
                self.name,
                "EIA_API_KEY env var (or api_key in config) is required. "
                "Register a free key at https://www.eia.gov/opendata/register.php",
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
        for spec in self.series:
            url = f"{self.BASE_URL}/{spec['route']}/data/"
            params = {
                "api_key": self.api_key,
                "frequency": "weekly" if spec["id"].endswith(".W") else "monthly",
                "data[0]": "value",
                "facets[series][]": spec["id"],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "sort[0][column]": "period",
                "sort[0][direction]": "asc",
                "length": min(5000, max_results),
            }
            try:
                resp = requests.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                logger.warning("eia: %s failed: %s", spec["id"], exc)
                continue

            if resp.status_code != 200:
                logger.warning(
                    "eia: %s returned HTTP %d (%s)",
                    spec["id"],
                    resp.status_code,
                    resp.text[:120],
                )
                continue

            data = (resp.json() or {}).get("response", {}).get("data", []) or []
            for row in data:
                period = row.get("period")
                value = row.get("value")
                if period is None or value is None:
                    continue
                published = _parse_period(str(period))
                if not published or not (start <= published.date() < end):
                    continue
                articles.append(
                    NewsArticle(
                        source=f"eia:{spec['id']}",
                        title=f"{spec['label']}: {value} {spec['unit']} ({period})",
                        url=f"https://www.eia.gov/opendata/v1/qb.php?sdid={spec['id']}",
                        published_at=published,
                        description=(
                            f"EIA series {spec['id']} ({spec['label']}) "
                            f"reported {value} {spec['unit']} for week ending {period}."
                        ),
                        content="",
                        raw=row,
                    )
                )
                if len(articles) >= max_results:
                    break
            if len(articles) >= max_results:
                break

        logger.info("eia: fetched %d observations for %s..%s", len(articles), start, end)
        return articles


def _parse_period(value: str) -> datetime | None:
    """Parse an EIA period string ('YYYY-MM-DD' or 'YYYY-MM')."""
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
