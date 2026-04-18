"""Weekly news summariser + crisis-description rewriter.

This module is the bridge between fetched articles (raw text) and the
crisis-description YAML that Module 1 (scenario generation) consumes.
The flow per week is:

    fetch articles  ->  summarise_week  ->  WeeklyBrief
                                            |
                                            v
                                  write_updated_crisis_yaml
                                            |
                                            v
                          configs/crisis_descriptions/<id>.yaml

We do NOT mutate the original `hormuz_2026.yaml` baseline. Instead we
read it, append a "Recent developments" block holding the LLM's
summary, and write a new file whose path the SLURM driver hands to
the rest of the pipeline via env var.

This deliberately leaves the structural fields (key actors,
commodities affected, timeline_context) intact: those are slow-moving
context. The LLM only changes the `description` field and adds a
`recent_developments` field that downstream prompts surface.
"""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.news.base import NewsArticle

logger = get_logger(__name__)


SUMMARISER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an analyst maintaining a living crisis brief for the "
            "{crisis_name} ({crisis_date}). Each week you are given the "
            "raw article and indicator headlines published in the past 7 "
            "days, plus the brief from the previous week. You produce an "
            "updated brief in the same style.\n\n"
            "Hard rules:\n"
            " - Stay strictly factual. If the articles do not support a "
            "   claim, do not include it.\n"
            " - Quantify whenever possible (oil prices, vessel counts, "
            "   troop movements, casualties, days of disruption).\n"
            " - Surface contradictions between sources rather than "
            "   silently picking one side.\n"
            " - Note explicitly which scenario branches (swift vs. "
            "   prolonged closure; contained vs. escalated conflict) the "
            "   week's evidence supports or weakens.\n"
            " - Never fabricate numbers or events. If coverage is thin, "
            "   say so in `coverage_gaps`.\n",
        ),
        (
            "human",
            "Crisis description (baseline):\n{baseline_description}\n\n"
            "Previous week's brief (may be empty for the first week):\n"
            "{previous_brief}\n\n"
            "Week of {week_start} -- {week_end}.\n"
            "Articles and indicators ({n_articles} total, most recent first):\n"
            "{article_lines}\n\n"
            "Produce the structured weekly brief.",
        ),
    ]
)


class WeeklyBrief(BaseModel):
    """Structured brief used to rewrite the crisis description."""

    week_start: str = Field(..., description="ISO date, inclusive.")
    week_end: str = Field(..., description="ISO date, exclusive.")
    headline: str = Field(
        ..., description="One-sentence summary of the week's developments."
    )
    summary: str = Field(
        ...,
        description=(
            "3-6 paragraph factual summary covering military, oil, LNG, "
            "shipping, and humanitarian developments. Quantitative."
        ),
    )
    key_indicators: list[str] = Field(
        default_factory=list,
        description=(
            "Bullet list of measurable indicators with values and units, "
            "e.g. 'Brent spot price: $112/bbl (+8% w/w)'."
        ),
    )
    scenario_signals: list[str] = Field(
        default_factory=list,
        description=(
            "Per scenario (A/B/C/D) note whether the week's evidence "
            "raised or lowered probability and why."
        ),
    )
    new_actors_or_commodities: list[str] = Field(
        default_factory=list,
        description=(
            "Actors / commodities that appeared in the week's articles "
            "but are missing from the baseline description."
        ),
    )
    coverage_gaps: list[str] = Field(
        default_factory=list,
        description="Topics where coverage is thin or contradictory.",
    )


def summarise_week(
    llm: BaseChatModel,
    articles: list[NewsArticle],
    week_start: date,
    week_end: date,
    crisis_name: str,
    crisis_date: str,
    baseline_description: str,
    previous_brief: str | None = None,
    max_articles_in_prompt: int = 60,
) -> WeeklyBrief:
    """Run the LLM summariser over a week's articles.

    Returns a structured `WeeklyBrief`. Articles beyond
    `max_articles_in_prompt` are dropped from the prompt to keep token
    usage bounded; the full list is still persisted alongside the
    brief for provenance.
    """
    if not articles:
        logger.warning(
            "No articles for %s..%s; emitting an empty brief.", week_start, week_end
        )
        return WeeklyBrief(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            headline="No new articles or indicators retrieved this week.",
            summary=(
                "All configured news sources returned zero usable articles "
                "for this week. The crisis description is unchanged from "
                "the previous brief."
            ),
            coverage_gaps=["No upstream data available for this week."],
        )

    capped = articles[:max_articles_in_prompt]
    article_lines = "\n".join(a.to_brief_line() for a in capped)
    if len(articles) > max_articles_in_prompt:
        article_lines += (
            f"\n... (+{len(articles) - max_articles_in_prompt} more articles "
            "omitted from prompt; persisted in week artefacts)"
        )

    structured_llm = llm.with_structured_output(WeeklyBrief)
    chain = SUMMARISER_PROMPT | structured_llm

    brief = chain.invoke(
        {
            "crisis_name": crisis_name,
            "crisis_date": crisis_date,
            "baseline_description": baseline_description.strip(),
            "previous_brief": (previous_brief or "(no previous brief)").strip(),
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "n_articles": len(articles),
            "article_lines": article_lines,
        }
    )
    # Defensive: structured-output schemas occasionally drop the date
    # fields when the model misformats; backfill.
    brief.week_start = brief.week_start or week_start.isoformat()
    brief.week_end = brief.week_end or week_end.isoformat()
    return brief


def write_updated_crisis_yaml(
    baseline_path: Path,
    output_path: Path,
    brief: WeeklyBrief,
    week_start: date,
    week_end: date,
) -> Path:
    """Write a per-week crisis YAML augmented with the weekly brief.

    The baseline file is loaded, deep-copied, and extended with:

    * `description`           - prefixed with the week's headline so the
                                LLM sees it first when generating
                                scenarios.
    * `recent_developments`   - structured block of headline / summary
                                / indicators / scenario signals.
    * `as_of`                 - the week_end date (ISO).
    * `weekly_briefs`         - append-only list of every brief built
                                so far, so a week N run can show the
                                full evolution from week 1.

    The baseline file itself is never modified.
    """
    with open(baseline_path) as f:
        baseline = yaml.safe_load(f) or {}

    updated = copy.deepcopy(baseline)
    base_desc = (updated.get("description") or "").strip()

    week_suffix = (
        f"\n\n[Update for week {week_start.isoformat()}..{week_end.isoformat()}]\n"
        f"{brief.headline}\n"
        f"{brief.summary}\n"
    )
    updated["description"] = base_desc + week_suffix
    updated["as_of"] = week_end.isoformat()
    updated["recent_developments"] = {
        "week_start": brief.week_start,
        "week_end": brief.week_end,
        "headline": brief.headline,
        "summary": brief.summary,
        "key_indicators": brief.key_indicators,
        "scenario_signals": brief.scenario_signals,
        "new_actors_or_commodities": brief.new_actors_or_commodities,
        "coverage_gaps": brief.coverage_gaps,
    }
    history = list(updated.get("weekly_briefs") or [])
    history.append(updated["recent_developments"])
    updated["weekly_briefs"] = history

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.safe_dump(updated, f, sort_keys=False, allow_unicode=True)

    logger.info("Wrote weekly crisis YAML: %s", output_path)
    return output_path


def render_brief_as_text(brief: WeeklyBrief) -> str:
    """Render a brief as the plain-text input for the next week's summariser."""
    lines = [
        f"Week {brief.week_start}..{brief.week_end}",
        f"Headline: {brief.headline}",
        "",
        brief.summary,
        "",
        "Key indicators:",
        *(f"  - {x}" for x in brief.key_indicators),
        "",
        "Scenario signals:",
        *(f"  - {x}" for x in brief.scenario_signals),
        "",
        "New actors/commodities: " + (", ".join(brief.new_actors_or_commodities) or "none"),
        "Coverage gaps: " + (", ".join(brief.coverage_gaps) or "none"),
    ]
    return "\n".join(lines)
