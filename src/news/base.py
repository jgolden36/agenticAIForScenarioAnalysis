"""Abstract base classes for news / government-data source adapters.

A `NewsSource` adapter implements `fetch(start, end, query)` and
returns a list of `NewsArticle` records. Adapters are intentionally
stateless and side-effect free apart from the network call; the
aggregator handles deduplication, retry, and persistence.

Design notes
------------
* `NewsArticle` is deliberately small and JSON-serialisable so the
  fetched payload can be persisted alongside the per-run state files
  under `data/pipeline_state/news/<run_id>/articles.json`. This keeps
  full provenance from synthesis -> brief -> raw articles.
* All adapters surface failures via `NewsSourceError` rather than the
  underlying HTTP exception, so the SLURM driver can fall back to the
  next configured source without leaking provider-specific traceback
  noise into the run log.
* Date inputs are `datetime.date` (UTC, inclusive of `start`,
  exclusive of `end`) to match the standard "weekly bucket" semantics
  used by the temporal job.
"""

from __future__ import annotations

import abc
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


class NewsSourceError(RuntimeError):
    """Raised when a news/data source cannot be queried.

    Includes the source name so the aggregator can record per-source
    failures into the run log without losing track of which provider
    misbehaved.
    """

    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"[{source}] {message}")
        self.source = source
        self.message = message


@dataclass
class NewsArticle:
    """A single article or government-report record.

    Fields kept minimal so adapters can populate them from very
    different upstream schemas (NewsAPI's `urlToImage`, EIA's series
    metadata, GNews' `source.name`, ...).
    """

    source: str
    title: str
    url: str
    published_at: datetime
    description: str = ""
    content: str = ""
    author: str | None = None
    language: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Return a stable hash used by the aggregator for dedup.

        Two articles are considered duplicates if they share the same
        canonicalised URL OR the same (title, publication date) tuple.
        We hash both signals and let the aggregator key on either.
        """
        url_key = (self.url or "").strip().lower().rstrip("/")
        title_key = " ".join((self.title or "").lower().split())
        date_key = self.published_at.date().isoformat() if self.published_at else ""
        digest = hashlib.sha1(
            f"{url_key}|{title_key}|{date_key}".encode("utf-8"),
        )
        return digest.hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly serialisation for state persistence."""
        d = asdict(self)
        d["published_at"] = (
            self.published_at.isoformat() if self.published_at else None
        )
        return d

    def to_brief_line(self, max_chars: int = 280) -> str:
        """One-line digest used inside summariser prompts."""
        body = (self.description or self.content or "").strip()
        if len(body) > max_chars:
            body = body[: max_chars - 1].rsplit(" ", 1)[0] + "..."
        when = self.published_at.date().isoformat() if self.published_at else "?"
        return f"[{when}] ({self.source}) {self.title.strip()} -- {body}"


class NewsSource(abc.ABC):
    """Abstract source adapter.

    Concrete adapters override `fetch` and the `name` property. The
    `requires_api_key` class attribute documents whether the source
    needs a key from the environment; the SLURM driver uses this to
    decide whether to enable the source in the first place.
    """

    name: str = "abstract"
    requires_api_key: bool = True

    def __init__(self, **kwargs: Any) -> None:
        self.config: dict[str, Any] = kwargs

    @abc.abstractmethod
    def fetch(
        self,
        start: date,
        end: date,
        query: str,
        max_results: int = 100,
    ) -> list[NewsArticle]:
        """Fetch articles published between [start, end).

        Args:
            start: Inclusive start date (UTC).
            end: Exclusive end date (UTC).
            query: Boolean query string. Adapters that do not natively
                support boolean operators should pass it through and
                let the upstream API do best-effort matching.
            max_results: Soft upper bound on the number of articles to
                request. Adapters may return fewer (e.g. the API has a
                page-size cap) but should not return more.
        """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
