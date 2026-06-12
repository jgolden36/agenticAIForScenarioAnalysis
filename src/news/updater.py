"""Automatic news-driven re-analysis driver (Module 6, local runtime).

Completes the temporal update loop for machines that are not a SLURM
cluster: one call (or one cron entry) fetches the most recent week of
news + government indicators, rewrites the crisis description, decides
whether the new information is *material*, and -- only if it is --
reruns the full Algorithm 1 pipeline (Modules 1-4) through the
imperative orchestrator under an isolated ``weekly_<date>`` run id.

    python -m src.news.updater --auto-approve            # last 7 days
    python -m src.news.updater --as-of 2026-04-10 --force

Relationship to the SLURM driver
--------------------------------
``slurm/jobs/weekly_news_pipeline.job`` backfills a historical date
range on the cluster, re-running every week unconditionally. This
module is its always-on local counterpart: it processes ONE week per
invocation, persists the same artefact layout (``data/news/<date>/``,
``configs/crisis_descriptions/<id>_weekly/<date>.yaml``), and adds the
materiality gate so an unattended schedule does not burn an LLM +
model-portfolio run on a week where nothing happened.

Human-in-the-loop note
----------------------
The pipeline's three analyst checkpoints are mandatory by design. In
interactive runs they surface through the CLI review interface; with
``--auto-approve`` (required for unattended schedules) they are
auto-approved exactly as the SLURM stage scripts do, and the analyst
reviews the persisted artefacts (weekly YAML, update summary, synthesis
report) after the fact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

from src.common.logging import get_logger
from src.news.aggregator import FetchReport, NewsAggregator, build_source_from_config
from src.news.materiality import (
    MaterialityAssessment,
    MaterialityConfig,
    assess_materiality,
)
from src.news.summarizer import (
    WeeklyBrief,
    render_brief_as_text,
    summarise_week,
    write_updated_crisis_yaml,
)
from src.pipeline.config import PipelineConfig

logger = get_logger(__name__)

_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass
class WeeklyUpdateOutcome:
    """Everything one weekly update produced, for callers and the CLI."""

    week_start: date
    week_end: date
    n_articles: int
    brief: WeeklyBrief
    materiality: MaterialityAssessment
    pipeline_ran: bool
    run_id: str | None = None
    crisis_yaml_path: Path | None = None
    articles_path: Path | None = None
    report_path: Path | None = None
    brief_text_path: Path | None = None
    brief_json_path: Path | None = None
    state_path: Path | None = None
    summary_json_path: Path | None = None
    summary_md_path: Path | None = None
    errors: list[str] = field(default_factory=list)


def find_previous_brief(
    news_dir: Path, before: date
) -> tuple[dict[str, Any] | None, str | None]:
    """Locate the most recent persisted brief strictly before ``before``.

    Returns ``(brief_dict, brief_text)`` -- the dict feeds the
    materiality comparison, the text threads into the summariser prompt
    as previous-week context. Either may be ``None`` independently.
    """
    if not news_dir.is_dir():
        return None, None
    candidates = sorted(
        (
            d
            for d in news_dir.iterdir()
            if d.is_dir() and _DATE_DIR_RE.match(d.name) and d.name < before.isoformat()
        ),
        key=lambda d: d.name,
        reverse=True,
    )
    for d in candidates:
        brief_dict: dict[str, Any] | None = None
        brief_text: str | None = None
        json_path = d / "brief.json"
        if json_path.exists():
            try:
                brief_dict = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Unreadable previous brief %s: %s", json_path, exc)
        txt_path = d / "brief.txt"
        if txt_path.exists():
            try:
                brief_text = txt_path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Unreadable previous brief %s: %s", txt_path, exc)
        if brief_dict is not None or brief_text is not None:
            logger.info("Previous brief found under %s", d)
            return brief_dict, brief_text
    return None, None


def _build_sources(sources_cfg: dict[str, Any]) -> list:
    sources = []
    for spec in sources_cfg.get("sources") or []:
        try:
            sources.append(build_source_from_config(spec))
        except Exception as exc:
            logger.warning("Skipping source spec %r (%s)", spec, exc)
    return sources


def _default_pipeline_runner(
    config: PipelineConfig,
    framework_path: Path,
    auto_approve: bool,
) -> Callable[[str, str], Any]:
    """Build the production pipeline runner (Modules 1-4 via orchestrator).

    Imports are deferred so that brief-only usage (and tests that
    inject a stub runner) work on installs without the full LangGraph /
    orchestrator dependency chain.
    """

    def _run(crisis_description: str, run_id: str) -> Any:
        from src.interface.review import (
            AutoApproveReviewInterface,
            CLIReviewInterface,
        )
        from src.pipeline.orchestrator import PipelineOrchestrator
        from src.pipeline.state import PipelineState
        from src.scenarios.framework import ScenarioFramework

        with open(framework_path) as f:
            framework = ScenarioFramework(**(yaml.safe_load(f) or {}))

        review = (
            AutoApproveReviewInterface() if auto_approve else CLIReviewInterface()
        )
        if auto_approve:
            logger.warning(
                "Auto-approve enabled: the three analyst checkpoints are "
                "approved automatically. Review the persisted artefacts "
                "(weekly YAML, update summary, synthesis) after the run."
            )
        orchestrator = PipelineOrchestrator(config=config, review_interface=review)
        state = PipelineState(run_id=run_id, crisis_description=crisis_description)
        return orchestrator.run(crisis_description, framework=framework, state=state)

    return _run


def _run_health(state: Any) -> dict[str, Any]:
    """Summarise a PipelineState's execution results for the update summary."""
    if state is None:
        return {}
    status_counts: dict[str, int] = {}
    for r in getattr(state, "execution_results", []) or []:
        status = getattr(r.status, "value", str(r.status))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "scenarios": len(getattr(state, "scenario_narratives", []) or []),
        "model_runs_by_status": status_counts,
        "consistency_flags": len(getattr(state, "consistency_flags", []) or []),
        "synthesis_results": len(getattr(state, "synthesis_results", []) or []),
    }


def _write_update_summary(
    outcome: WeeklyUpdateOutcome,
    report: FetchReport | None,
    run_health: dict[str, Any],
    summary_dir: Path,
) -> tuple[Path, Path]:
    """Persist the auditable JSON + Markdown record of this update."""
    summary_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "week_start": outcome.week_start.isoformat(),
        "week_end": outcome.week_end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_articles": outcome.n_articles,
        "fetch_report": report.to_dict() if report else None,
        "headline": outcome.brief.headline,
        "observed_indicators": [
            i.model_dump() for i in outcome.brief.observed_indicators
        ],
        "materiality": outcome.materiality.to_dict(),
        "pipeline_ran": outcome.pipeline_ran,
        "run_id": outcome.run_id,
        "crisis_yaml": str(outcome.crisis_yaml_path) if outcome.crisis_yaml_path else None,
        "state_file": str(outcome.state_path) if outcome.state_path else None,
        "run_health": run_health,
        "errors": outcome.errors,
    }
    json_path = summary_dir / "update_summary.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# Weekly update {outcome.week_start.isoformat()} .. {outcome.week_end.isoformat()}",
        "",
        f"**Headline:** {outcome.brief.headline}",
        "",
        f"**Articles fetched (post-dedup):** {outcome.n_articles}",
        "",
        "## Materiality decision",
        "",
        f"**{'MATERIAL -- pipeline rerun' if outcome.materiality.material else 'Immaterial -- rerun skipped'}**"
        + (" (forced)" if outcome.pipeline_ran and not outcome.materiality.material else ""),
        "",
        *(f"- {r}" for r in outcome.materiality.reasons),
    ]
    if outcome.materiality.indicator_deltas:
        lines += [
            "",
            "## Indicator deltas (week over week)",
            "",
            "| Indicator | Previous | Current | Change | Material |",
            "|---|---|---|---|---|",
        ]
        for d in outcome.materiality.indicator_deltas:
            change = f"{d.change_pct:+.1f}%" if d.change_pct is not None else "n/a"
            lines.append(
                f"| {d.name} | {d.previous} | {d.current} | {change} | "
                f"{'yes' if d.material else 'no'} |"
            )
    if outcome.pipeline_ran:
        lines += [
            "",
            "## Pipeline run",
            "",
            f"- Run id: `{outcome.run_id}`",
            f"- Crisis YAML: `{outcome.crisis_yaml_path}`",
            f"- State file: `{outcome.state_path}`",
        ]
        if run_health:
            lines.append(f"- Scenarios: {run_health.get('scenarios')}")
            lines.append(
                f"- Model runs by status: {run_health.get('model_runs_by_status')}"
            )
            lines.append(
                f"- Consistency flags: {run_health.get('consistency_flags')}"
            )
    if outcome.errors:
        lines += ["", "## Errors", "", *(f"- {e}" for e in outcome.errors)]
    md_path = summary_dir / "update_summary.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run_weekly_update(
    as_of: date | None = None,
    window_days: int = 7,
    baseline: Path | None = None,
    sources_config: Path | None = None,
    framework_path: Path | None = None,
    pipeline_config: PipelineConfig | None = None,
    news_dir: Path | None = None,
    weekly_crisis_dir: Path | None = None,
    reports_dir: Path | None = None,
    state_dir: Path | None = None,
    force_rerun: bool = False,
    skip_pipeline: bool = False,
    auto_approve: bool = False,
    materiality_config: MaterialityConfig | None = None,
    llm: Any = None,
    summarise_fn: Callable[..., WeeklyBrief] = summarise_week,
    pipeline_runner: Callable[[str, str], Any] | None = None,
    max_articles_per_source: int = 50,
    max_articles_in_prompt: int = 60,
) -> WeeklyUpdateOutcome:
    """Run one automatic news-driven update cycle.

    Fetch -> summarise -> rewrite crisis YAML -> materiality gate ->
    (optionally) rerun Modules 1-4 -> write the auditable update
    summary. Artefacts use the same layout as the SLURM weekly driver
    so the cross-week visualisation tooling picks them up unchanged.

    Args:
        as_of: End of the news window, exclusive (default: today, i.e.
            "the last ``window_days`` days").
        window_days: Length of the news window.
        baseline / sources_config / framework_path: Config files;
            default to the Hormuz 2026 set under ``configs/``.
        pipeline_config: ``PipelineConfig`` for both the summariser LLM
            and the orchestrator; defaults to ``PipelineConfig()``.
        force_rerun: Rerun the pipeline even when immaterial.
        skip_pipeline: Build the brief + YAML but never rerun (brief-only
            mode, mirrors ``HORMUZ_WEEKLY_SKIP_PIPELINE=1`` on SLURM).
        auto_approve: Auto-approve the three analyst checkpoints
            (required for unattended schedules; reviewed post-hoc).
        materiality_config: Thresholds for the rerun decision.
        llm / summarise_fn / pipeline_runner: Injection points for
            tests and alternative runtimes. ``pipeline_runner`` takes
            ``(crisis_description, run_id)`` and returns a
            ``PipelineState``-like object.

    Returns:
        :class:`WeeklyUpdateOutcome` describing what happened and where
        every artefact was written.
    """
    root = _project_root()
    baseline = baseline or root / "configs" / "crisis_descriptions" / "hormuz_2026.yaml"
    sources_config = sources_config or root / "configs" / "news_sources.yaml"
    framework_path = (
        framework_path or root / "configs" / "scenario_frameworks" / "hormuz_2026.yaml"
    )
    news_dir = news_dir or root / "data" / "news"
    weekly_crisis_dir = (
        weekly_crisis_dir or root / "configs" / "crisis_descriptions" / "hormuz_2026_weekly"
    )
    reports_dir = reports_dir or root / "data" / "reports"
    state_dir = state_dir or root / "data" / "pipeline_state"
    config = pipeline_config or PipelineConfig()

    week_end = as_of or date.today()
    week_start = week_end - timedelta(days=window_days)
    week_dir = news_dir / week_start.isoformat()
    week_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Fetch the week's news + indicators.
    # ------------------------------------------------------------------
    with open(sources_config) as f:
        sources_cfg = yaml.safe_load(f) or {}
    crisis_cfg = sources_cfg.get("crisis", {})
    query = sources_cfg.get("query") or "Strait of Hormuz OR Hormuz closure OR Iran oil"

    sources = _build_sources(sources_cfg)
    if not sources:
        raise RuntimeError(
            f"No usable news sources configured in {sources_config}; "
            "cannot run the automatic update."
        )
    aggregator = NewsAggregator(sources=sources, per_source_limit=max_articles_per_source)
    articles, report = aggregator.fetch_week(start=week_start, end=week_end, query=query)

    articles_path = week_dir / "articles.json"
    articles_path.write_text(
        json.dumps([a.to_dict() for a in articles], indent=2, default=str),
        encoding="utf-8",
    )
    report_path = week_dir / "report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # 2. Summarise into a structured WeeklyBrief.
    # ------------------------------------------------------------------
    previous_brief_dict, previous_brief_text = find_previous_brief(news_dir, week_start)

    with open(baseline) as f:
        baseline_data = yaml.safe_load(f) or {}

    if llm is None:
        from src.common.llm import get_llm

        llm = get_llm(
            provider=config.llm.provider,
            model=config.llm.model,
            temperature=config.llm.temperature,
            **config.llm.extra_kwargs,
        )

    brief = summarise_fn(
        llm=llm,
        articles=articles,
        week_start=week_start,
        week_end=week_end,
        crisis_name=crisis_cfg.get("name", "Strait of Hormuz Closure"),
        crisis_date=crisis_cfg.get("date", "2026-02"),
        baseline_description=baseline_data.get("description", ""),
        previous_brief=previous_brief_text,
        max_articles_in_prompt=max_articles_in_prompt,
    )

    brief_text_path = week_dir / "brief.txt"
    brief_text_path.write_text(render_brief_as_text(brief), encoding="utf-8")
    brief_json_path = week_dir / "brief.json"
    brief_json_path.write_text(brief.model_dump_json(indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # 3. Rewrite the crisis description YAML for this week.
    # ------------------------------------------------------------------
    crisis_yaml_path = weekly_crisis_dir / f"{week_start.isoformat()}.yaml"
    write_updated_crisis_yaml(
        baseline_path=baseline,
        output_path=crisis_yaml_path,
        brief=brief,
        week_start=week_start,
        week_end=week_end,
    )

    # ------------------------------------------------------------------
    # 4. Materiality gate.
    # ------------------------------------------------------------------
    materiality = assess_materiality(
        current_brief=brief,
        previous_brief=previous_brief_dict,
        n_articles=len(articles),
        config=materiality_config,
    )

    outcome = WeeklyUpdateOutcome(
        week_start=week_start,
        week_end=week_end,
        n_articles=len(articles),
        brief=brief,
        materiality=materiality,
        pipeline_ran=False,
        crisis_yaml_path=crisis_yaml_path,
        articles_path=articles_path,
        report_path=report_path,
        brief_text_path=brief_text_path,
        brief_json_path=brief_json_path,
    )

    should_run = (materiality.material or force_rerun) and not skip_pipeline
    run_health: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 5. Rerun Modules 1-4 when warranted.
    # ------------------------------------------------------------------
    if should_run:
        run_id = f"weekly_{week_start.strftime('%Y%m%d')}"
        outcome.run_id = run_id
        with open(crisis_yaml_path) as f:
            weekly_data = yaml.safe_load(f) or {}
        crisis_description = weekly_data.get(
            "description", yaml.safe_dump(weekly_data)
        )
        runner = pipeline_runner or _default_pipeline_runner(
            config, framework_path, auto_approve
        )
        try:
            state = runner(crisis_description, run_id)
            outcome.pipeline_ran = True
            run_health = _run_health(state)
            if state is not None and hasattr(state, "model_dump_json"):
                state_dir.mkdir(parents=True, exist_ok=True)
                state_path = state_dir / f"{run_id}_state.json"
                state_path.write_text(
                    state.model_dump_json(indent=2), encoding="utf-8"
                )
                outcome.state_path = state_path
        except Exception as exc:  # keep the brief artefacts even on failure
            logger.exception("Weekly pipeline rerun failed: %s", exc)
            outcome.errors.append(f"Pipeline rerun failed: {exc}")
    elif skip_pipeline:
        logger.info("skip_pipeline set: brief-only mode, no rerun.")
    else:
        logger.info("Immaterial week: pipeline rerun skipped (use force_rerun to override).")

    # ------------------------------------------------------------------
    # 6. Persist the auditable update summary.
    # ------------------------------------------------------------------
    summary_dir = reports_dir / f"weekly_{week_start.strftime('%Y%m%d')}"
    outcome.summary_json_path, outcome.summary_md_path = _write_update_summary(
        outcome, report, run_health, summary_dir
    )
    logger.info(
        "Weekly update complete: material=%s pipeline_ran=%s summary=%s",
        materiality.material,
        outcome.pipeline_ran,
        outcome.summary_md_path,
    )
    return outcome


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Automatic news-driven re-analysis (one week per invocation)."
    )
    p.add_argument("--as-of", type=_parse_date, default=None,
                   help="End of the news window, exclusive (default: today).")
    p.add_argument("--window-days", type=int, default=7)
    p.add_argument("--baseline", type=Path, default=None)
    p.add_argument("--sources-config", type=Path, default=None)
    p.add_argument("--framework", type=Path, default=None)
    p.add_argument("--pipeline-config", type=Path, default=None,
                   help="PipelineConfig YAML (default: built-in defaults).")
    p.add_argument("--indicator-threshold-pct", type=float, default=10.0,
                   help="Materiality threshold for indicator moves.")
    p.add_argument("--force", action="store_true",
                   help="Rerun the pipeline even when the week is immaterial.")
    p.add_argument("--skip-pipeline", action="store_true",
                   help="Brief-only mode: fetch + summarise but never rerun.")
    p.add_argument("--auto-approve", action="store_true",
                   help="Auto-approve analyst checkpoints (unattended mode; "
                        "review artefacts post-hoc).")
    args = p.parse_args(argv)

    config = (
        PipelineConfig.from_yaml(args.pipeline_config)
        if args.pipeline_config
        else PipelineConfig()
    )
    outcome = run_weekly_update(
        as_of=args.as_of,
        window_days=args.window_days,
        baseline=args.baseline,
        sources_config=args.sources_config,
        framework_path=args.framework,
        pipeline_config=config,
        force_rerun=args.force,
        skip_pipeline=args.skip_pipeline,
        auto_approve=args.auto_approve,
        materiality_config=MaterialityConfig(
            indicator_change_threshold_pct=args.indicator_threshold_pct
        ),
    )
    print(
        json.dumps(
            {
                "week_start": outcome.week_start.isoformat(),
                "week_end": outcome.week_end.isoformat(),
                "n_articles": outcome.n_articles,
                "material": outcome.materiality.material,
                "pipeline_ran": outcome.pipeline_ran,
                "run_id": outcome.run_id,
                "summary": str(outcome.summary_md_path),
            },
            indent=2,
        )
    )
    return 0 if not outcome.errors else 1


if __name__ == "__main__":
    sys.exit(main())
