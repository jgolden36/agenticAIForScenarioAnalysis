#!/usr/bin/env python3
"""Build a per-week crisis-description YAML from news + indicators.

Invocation (single week):

    python slurm/scripts/build_weekly_brief.py \
        --week-start 2026-02-15 \
        --week-end   2026-02-22 \
        --sources-config configs/news_sources.yaml \
        --baseline configs/crisis_descriptions/hormuz_2026.yaml \
        --output configs/crisis_descriptions/hormuz_2026_weekly/2026-02-15.yaml \
        --previous-brief data/news/2026-02-08.brief.txt \
        --articles-out data/news/2026-02-15.articles.json \
        --report-out   data/news/2026-02-15.report.json

This script is normally driven by `slurm/jobs/weekly_news_pipeline.job`,
which loops over every week in a date range. It can also be run by
hand for ad-hoc updates.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from slurm.scripts.stage_utils import resolve_llm_kwargs
from src.common.llm import get_llm
from src.common.logging import get_logger
from src.news import (
    NewsAggregator,
    build_source_from_config,
    summarise_week,
    write_updated_crisis_yaml,
)
from src.news.summarizer import render_brief_as_text
from src.pipeline.config import PipelineConfig

logger = get_logger("hormuz.weekly_brief")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_sources_config(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--week-start", required=True, type=_parse_date,
                   help="Inclusive start (YYYY-MM-DD).")
    p.add_argument("--week-end", required=True, type=_parse_date,
                   help="Exclusive end (YYYY-MM-DD).")
    p.add_argument("--baseline", required=True, type=Path,
                   help="Baseline crisis YAML (e.g. configs/crisis_descriptions/hormuz_2026.yaml).")
    p.add_argument("--output", required=True, type=Path,
                   help="Where to write the augmented per-week crisis YAML.")
    p.add_argument("--sources-config", required=True, type=Path,
                   help="YAML config selecting and configuring news sources.")
    p.add_argument("--pipeline-config", default=None, type=Path,
                   help="Pipeline config YAML for LLM settings (default: from env).")
    p.add_argument("--previous-brief", default=None, type=Path,
                   help="Previous week's brief (plain text).")
    p.add_argument("--brief-out", default=None, type=Path,
                   help="Where to write this week's brief as plain text.")
    p.add_argument("--articles-out", default=None, type=Path,
                   help="Where to write the raw fetched articles as JSON.")
    p.add_argument("--report-out", default=None, type=Path,
                   help="Where to write the aggregator FetchReport JSON.")
    p.add_argument("--max-articles-per-source", type=int, default=50)
    p.add_argument("--max-articles-in-prompt", type=int, default=60)
    args = p.parse_args()

    if args.week_end <= args.week_start:
        logger.error("--week-end must be strictly after --week-start")
        return 2

    sources_cfg = _load_sources_config(args.sources_config)
    crisis_cfg = sources_cfg.get("crisis", {})
    crisis_name = crisis_cfg.get("name", "Strait of Hormuz Closure")
    crisis_date = crisis_cfg.get("date", "2026-02")
    query = sources_cfg.get("query") or 'Strait of Hormuz OR Hormuz closure OR Iran oil'

    source_specs = sources_cfg.get("sources") or []
    if not source_specs:
        logger.error(
            "No sources configured. Add at least one entry under "
            "'sources:' in %s",
            args.sources_config,
        )
        return 2

    sources = []
    for spec in source_specs:
        try:
            sources.append(build_source_from_config(spec))
        except Exception as exc:
            logger.warning(
                "Skipping source spec %r (%s); continuing with the others.",
                spec, exc,
            )
    if not sources:
        logger.error("All configured sources failed to initialise; aborting.")
        return 2

    aggregator = NewsAggregator(
        sources=sources,
        per_source_limit=args.max_articles_per_source,
    )
    articles, report = aggregator.fetch_week(
        start=args.week_start,
        end=args.week_end,
        query=query,
    )

    if args.articles_out:
        args.articles_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.articles_out, "w") as f:
            json.dump([a.to_dict() for a in articles], f, indent=2, default=str)
        logger.info("Wrote raw articles: %s", args.articles_out)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report_out, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        logger.info("Wrote fetch report: %s", args.report_out)

    cfg_path = args.pipeline_config
    if cfg_path is None:
        # Mirror stage_utils.get_pipeline_config_path() but with a
        # local fallback so this script also works outside SLURM.
        env = Path("slurm/config/pipeline_cluster.yaml")
        cfg_path = env if env.exists() else Path("configs/model_configs/default.yaml")
    config = PipelineConfig.from_yaml(cfg_path)

    # Build LLM. Env vars (PIPELINE_LLM_PROVIDER / _MODEL / _BASE_URL)
    # win over the YAML config so the SLURM driver job — which is what
    # actually started the vLLM sidecar — owns the model name.
    llm = get_llm(**resolve_llm_kwargs(config))

    with open(args.baseline) as f:
        baseline_data = yaml.safe_load(f) or {}
    baseline_description = baseline_data.get("description", "")

    previous_brief_text: str | None = None
    if args.previous_brief and args.previous_brief.exists():
        previous_brief_text = args.previous_brief.read_text(encoding="utf-8")
        logger.info("Loaded previous brief: %s", args.previous_brief)

    brief = summarise_week(
        llm=llm,
        articles=articles,
        week_start=args.week_start,
        week_end=args.week_end,
        crisis_name=crisis_name,
        crisis_date=crisis_date,
        baseline_description=baseline_description,
        previous_brief=previous_brief_text,
        max_articles_in_prompt=args.max_articles_in_prompt,
    )

    out_path = write_updated_crisis_yaml(
        baseline_path=args.baseline,
        output_path=args.output,
        brief=brief,
        week_start=args.week_start,
        week_end=args.week_end,
    )

    if args.brief_out:
        args.brief_out.parent.mkdir(parents=True, exist_ok=True)
        args.brief_out.write_text(render_brief_as_text(brief), encoding="utf-8")
        logger.info("Wrote brief text: %s", args.brief_out)

    logger.info(
        "Weekly brief built: %d articles -> %d after dedup; sources ok=%s, fail=%s",
        report.total_articles,
        report.deduped_articles,
        list(report.successes),
        list(report.failures),
    )
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
