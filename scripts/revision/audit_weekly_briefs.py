#!/usr/bin/env python3
"""Numeric audit of plain-text weekly briefs against the news they summarise (Reviewer 2, point 4).

``src.synthesis.fidelity.audit_brief`` checks the structured
``observed_indicators`` in a ``brief.json``. Batches that saved only
``brief.txt`` have none, so this script audits the prose: every number in each
brief is looked up among the numbers in that week's fetched articles, at the
brief's printed precision.

Read the result as an upper bound on support. A match means the number appears
somewhere in that week's fetched text, not that it describes the same quantity.
A miss means it was not found in the fetched text, which may be truncated by
the news API, so it is not proof of fabrication. Numbers that are decimals,
percentages, dollar amounts or at least 100 are reported separately as
``substantive``, because small integers match almost anything.

Usage::

    python scripts/revision/audit_weekly_briefs.py --briefs-root data/news/comparison_20260701_020011 \
        --articles-root data/news/cache --out-dir docs/revision/runs/backend_comparison_20260701_020011
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.synthesis.fidelity import (  # noqa: E402
    _NUMBER_RE,
    _decimals,
    _is_year_like,
    _to_float,
    close_within_printed_precision,
    flatten_numeric,
)

_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
_DATE_BEFORE_RE = re.compile(rf"{_MONTHS}\.?\s*$")
_DATE_AFTER_RE = re.compile(rf"^(?:\s*[–-]\s*\d{{1,2}})?\s*(?:of\s+)?{_MONTHS}")
_CONTEXT = 40


def article_numbers(articles: list[dict[str, Any]]) -> list[float]:
    numbers: list[float] = []
    for a in articles:
        for key in ("title", "description", "content"):
            for m in _NUMBER_RE.finditer(str(a.get(key) or "")):
                v = _to_float(m.group(0))
                if v is not None:
                    numbers.append(v)
        raw = a.get("raw")
        if isinstance(raw, (dict, list)):
            numbers.extend(flatten_numeric(raw if isinstance(raw, dict) else {"raw": raw}).values())
    return numbers


def brief_tokens(text: str) -> list[dict[str, Any]]:
    """Numbers in the brief, without dates. The first line is the week header."""
    body = text.split("\n", 1)[1] if "\n" in text else text
    tokens = []
    for m in _NUMBER_RE.finditer(body):
        token = m.group(0)
        value = _to_float(token)
        if value is None:
            continue
        before, after = body[max(0, m.start() - 12):m.start()], body[m.end():m.end() + 16]
        if _is_year_like(token, value) or _DATE_BEFORE_RE.search(before) or _DATE_AFTER_RE.search(after):
            continue
        substantive = "." in token or after.startswith("%") or before.endswith("$") or abs(value) >= 100
        context = body[max(0, m.start() - _CONTEXT):m.end() + _CONTEXT].replace("\n", " ")
        tokens.append({"token": token, "value": value, "decimals": _decimals(token), "substantive": substantive, "context": context})
    return tokens


def audit_brief_text(text: str, numbers: list[float]) -> list[dict[str, Any]]:
    rows = []
    for t in brief_tokens(text):
        matched = any(close_within_printed_precision(t["value"], n, t["decimals"]) for n in numbers)
        rows.append({**t, "matched": matched})
    return rows


def _rate(hit: int, n: int) -> float | None:
    return round(hit / n, 4) if n else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--briefs-root", required=True, help="Directory holding <week>/<backend>/brief.txt.")
    p.add_argument("--articles-root", required=True, help="Directory holding <week>__<end>/articles.json.")
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)

    articles_root = Path(args.articles_root)
    per_backend: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    detail: list[dict[str, Any]] = []
    missing_articles: list[str] = []
    for brief in sorted(Path(args.briefs_root).glob("*/*/brief.txt")):
        week, backend = brief.parent.parent.name, brief.parent.name
        candidates = sorted(articles_root.glob(f"{week}__*/articles.json"))
        if not candidates:
            missing_articles.append(week)
            continue
        articles = json.loads(candidates[0].read_text(encoding="utf-8"))
        articles = articles if isinstance(articles, list) else articles.get("articles", [])
        numbers = article_numbers(articles)
        for row in audit_brief_text(brief.read_text(encoding="utf-8", errors="replace"), numbers):
            s = per_backend[backend]
            s["tokens"] += 1
            s["matched"] += row["matched"]
            s["substantive"] += row["substantive"]
            s["substantive_matched"] += row["substantive"] and row["matched"]
            detail.append({"backend": backend, "week": week, **{k: row[k] for k in ("token", "substantive", "matched", "context")}})
        per_backend[backend]["briefs"] += 1

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "weekly_brief_audit_tokens.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["backend", "week", "token", "substantive", "matched", "context"])
        writer.writeheader()
        writer.writerows(detail)
    summary = [{"backend": b, **dict(s), "match_rate": _rate(s["matched"], s["tokens"]),
                "substantive_match_rate": _rate(s["substantive_matched"], s["substantive"])} for b, s in sorted(per_backend.items())]
    (out / "weekly_brief_audit.json").write_text(json.dumps({"summary": summary, "weeks_without_articles": missing_articles}, indent=2), encoding="utf-8")
    lines = ["# Numeric audit of weekly briefs", "",
             "A match means the number appears somewhere in that week's fetched text, so these rates are an upper bound on support. "
             "A miss is not proof of fabrication, since fetched text may be truncated.", "",
             "| backend | briefs | numbers | found in sources | rate | substantive numbers | found | rate |", "|---|---|---|---|---|---|---|---|"]
    for s in summary:
        lines.append(f"| {s['backend']} | {s['briefs']} | {s.get('tokens', 0)} | {s.get('matched', 0)} | {s['match_rate']} | "
                     f"{s.get('substantive', 0)} | {s.get('substantive_matched', 0)} | {s['substantive_match_rate']} |")
    if missing_articles:
        lines += ["", f"Weeks with no article cache, not audited: {', '.join(sorted(set(missing_articles)))}."]
    lines += ["", "Every number with its context, for review: `weekly_brief_audit_tokens.csv`."]
    (out / "weekly_brief_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"audited {sum(s['briefs'] for s in per_backend.values())} briefs, {len(detail)} numbers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
