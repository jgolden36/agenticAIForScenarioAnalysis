#!/usr/bin/env python3
"""Rerun only the runs of a model-comparison batch that did no model work (Reviewer 2, point 5).

A run needs a rerun when its brief failed, or when its brief succeeded but
scenario generation returned no scenarios. The original batch is read, never
changed; reruns get their own batch id and run ids. Runs execute one at a time
because they share ``data/outputs``.

* Brief succeeded: the run resumes at scenario generation from its saved crisis
  YAML, so the news brief is not regenerated.
* Brief failed: the brief is rebuilt from the shared article cache, with the
  latest earlier brief for that backend as context (from this batch when that
  week was also rerun, otherwise from the original batch).

These reruns use the current code, with any ``--completion-cap`` and
``--omit-temperature`` overrides, so they are not like-for-like with the
original batch. Each record in ``runs.json`` states its overrides.

Usage::

    python scripts/revision/rerun_failed_backend_runs.py --source-batch 20260701_020011 --batch-id fill_20261102 \
        --completion-cap anthropic-sonnet-4-6=32000 --completion-cap anthropic-opus-4-8=32000 \
        --omit-temperature anthropic-opus-4-8 --max-parallel 6 [--models tag,tag] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from slurm.scripts.run_model_comparison import (  # noqa: E402
    SCRIPTS,
    _pipeline_ok,
    _run,
    load_dotenv,
    load_roster,
    run_pipeline_for_run,
)
from src.common.logging import get_logger  # noqa: E402

logger = get_logger("hormuz.backend_rerun")


def scenario_count(state_dir: Path, run_id: str) -> int | None:
    path = state_dir / f"{run_id}_scenarios.json"
    if not path.exists():
        return None
    return len(json.loads(path.read_text(encoding="utf-8")).get("scenario_narratives") or [])


def select_failed(runs: list[dict[str, Any]], state_dir: Path) -> list[dict[str, Any]]:
    """Runs that did no model work, oldest week first within each backend."""
    failed = []
    for r in runs:
        if r.get("status") == "brief_failed":
            failed.append({**r, "failure": "brief_failed", "resume": "brief"})
        elif r.get("status") == "ok" and scenario_count(state_dir, r["run_id"]) == 0:
            failed.append({**r, "failure": "zero_scenarios", "resume": "scenarios"})
    return sorted(failed, key=lambda r: (r["tag"], r["week_start"]))


def new_backend_runs(runs: list[dict[str, Any]], tags: list[str]) -> list[dict[str, Any]]:
    """Every week of the source batch for backends that were not part of it."""
    spans = {r["week_start"]: r["week_end"] for r in runs}
    return [{"tag": tag, "week_start": week, "week_end": spans[week], "run_id": None, "failure": "new_backend", "resume": "brief"}
            for tag in tags for week in sorted(spans)]


def previous_brief(tag: str, week_start: str, weeks: list[str], *news_roots: Path) -> Path | None:
    """Latest non-empty brief before ``week_start``, searching the roots in order."""
    for week in sorted((w for w in weeks if w < week_start), reverse=True):
        for root in news_roots:
            path = root / week / tag / "brief.txt"
            if path.exists() and path.stat().st_size > 0:
                return path
    return None


def parse_caps(items: list[str]) -> dict[str, int]:
    caps = {}
    for item in items:
        tag, _, value = item.partition("=")
        caps[tag] = int(value)
    return caps


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source-batch", required=True)
    p.add_argument("--batch-id", required=True)
    p.add_argument("--roster", type=Path, default=PROJECT_ROOT / "configs" / "model_comparison.yaml")
    p.add_argument("--baseline", type=Path, default=PROJECT_ROOT / "configs" / "crisis_descriptions" / "hormuz_2026.yaml")
    p.add_argument("--news-config", type=Path, default=PROJECT_ROOT / "configs" / "news_sources.yaml")
    p.add_argument("--news-cache-dir", type=Path, default=PROJECT_ROOT / "data" / "news" / "cache")
    p.add_argument("--pipeline-config", type=Path, default=PROJECT_ROOT / "slurm" / "config" / "pipeline_cluster.yaml")
    p.add_argument("--completion-cap", action="append", default=[], metavar="TAG=TOKENS")
    p.add_argument("--omit-temperature", action="append", default=[], metavar="TAG")
    p.add_argument("--add-backend", action="append", default=[], metavar="TAG",
                   help="Run this roster backend for every week instead of rerunning failures. "
                        "For backends that were not in the source batch; report them separately.")
    p.add_argument("--models", default=None, help="Comma-separated subset of backend tags.")
    p.add_argument("--max-parallel", type=int, default=6)
    p.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    load_dotenv(args.env_file)
    defaults, roster = load_roster(args.roster)
    by_tag = {m["tag"]: m for m in roster}
    caps = parse_caps(args.completion_cap)
    omit = set(args.omit_temperature)

    data = PROJECT_ROOT / "data"
    state_dir = data / "pipeline_state"
    source_root = data / "reports" / "model_comparison" / args.source_batch
    source = json.loads((source_root / "runs.json").read_text(encoding="utf-8"))
    source = source if isinstance(source, list) else source.get("runs", [])
    unknown = [t for t in args.add_backend if t not in by_tag]
    if unknown:
        logger.error("--add-backend tags not in the roster: %s", ", ".join(unknown))
        return 2
    todo = new_backend_runs(source, args.add_backend) if args.add_backend else select_failed(source, state_dir)
    if args.models:
        wanted = {t.strip() for t in args.models.split(",") if t.strip()}
        todo = [r for r in todo if r["tag"] in wanted]
    weeks = sorted({r["week_start"] for r in source})

    batch_root = data / "reports" / "model_comparison" / args.batch_id
    news_root = data / "news" / f"comparison_{args.batch_id}"
    source_news = data / "news" / f"comparison_{args.source_batch}"
    crisis_base = PROJECT_ROOT / "configs" / "crisis_descriptions" / "hormuz_2026_weekly"
    crisis_root = crisis_base / f"comparison_{args.batch_id}"
    source_crisis = crisis_base / f"comparison_{args.source_batch}"

    logger.info("%d run(s) to rerun from batch %s into %s", len(todo), args.source_batch, args.batch_id)
    for r in todo:
        logger.info("  %s %s %s", r["tag"], r["week_start"], r["failure"])
    if args.dry_run:
        return 0
    batch_root.mkdir(parents=True, exist_ok=True)

    # Resumable: runs already recorded in this batch are not repeated.
    runs_path = batch_root / "runs.json"
    results: list[dict[str, Any]] = json.loads(runs_path.read_text(encoding="utf-8")) if runs_path.exists() else []
    done = {rec["run_id"] for rec in results}
    for r in todo:
        tag, ws, we = r["tag"], r["week_start"], r["week_end"]
        m = by_tag[tag]
        week_tag = ws.replace("-", "")
        run_id = f"cmp_{args.batch_id}_{tag}_{week_tag}"
        if run_id in done:
            logger.info("[%s/%s] already recorded in this batch; skipping.", tag, week_tag)
            continue
        cap = caps.get(tag) or m.get("max_completion_tokens") or defaults.get("max_completion_tokens")
        record: dict[str, Any] = {
            "batch_id": args.batch_id, "source_run_id": r["run_id"], "source_failure": r["failure"], "week_start": ws, "week_end": we,
            "tag": tag, "provider": m["provider"], "model": m["model"], "run_id": run_id, "max_completion_tokens": cap,
            "omit_temperature": tag in omit, "started_at": datetime.now(timezone.utc).isoformat(), "status": "pending",
        }

        env = os.environ.copy()
        env.pop("PIPELINE_LLM_BASE_URL", None)
        env.update({
            "PIPELINE_LLM_PROVIDER": m["provider"], "PIPELINE_LLM_MODEL": m["model"], "HORMUZ_AUTO_APPROVE": "1", "HORMUZ_RUN_ID": run_id,
            "HORMUZ_CONFIG": str(args.pipeline_config), "PYTHONUTF8": "1", "PIPELINE_LLM_MAX_COMPLETION_TOKENS": str(cap),
            "PIPELINE_LLM_CONTEXT_WINDOW": str(m.get("context_window") or defaults.get("context_window")),
            "PIPELINE_LLM_MAX_CONCURRENCY": str(defaults.get("max_concurrency")),
        })
        env.setdefault("WANDB_MODE", "disabled")
        if tag in omit:
            env["PIPELINE_LLM_OMIT_TEMPERATURE"] = "1"

        logger.info("\n--- %s %s (%s) run_id=%s cap=%s ---", tag, ws, r["failure"], run_id, cap)
        if r["resume"] == "scenarios":
            crisis_yaml = source_crisis / tag / f"{ws}.yaml"
            record["brief"] = {"reused_from": str(crisis_yaml)}
        else:
            crisis_yaml = crisis_root / tag / f"{ws}.yaml"
            brief_txt = news_root / ws / tag / "brief.txt"
            crisis_yaml.parent.mkdir(parents=True, exist_ok=True)
            brief_txt.parent.mkdir(parents=True, exist_ok=True)
            brief_args = [str(SCRIPTS / "build_weekly_brief.py"), "--week-start", ws, "--week-end", we, "--baseline", str(args.baseline),
                          "--output", str(crisis_yaml), "--sources-config", str(args.news_config), "--pipeline-config", str(args.pipeline_config),
                          "--articles-in", str(args.news_cache_dir / f"{ws}__{we}" / "articles.json"), "--brief-out", str(brief_txt)]
            prev = previous_brief(tag, ws, weeks, news_root, source_news)
            if prev:
                brief_args += ["--previous-brief", str(prev)]
            t0 = time.monotonic()
            rc, _ = _run(env, brief_args)
            record["brief"] = {"rc": rc, "seconds": time.monotonic() - t0, "previous_brief": str(prev) if prev else None}
            if rc != 0 or not crisis_yaml.exists():
                record["status"] = "brief_failed"
                logger.warning("[%s/%s] brief failed again (rc=%s).", tag, week_tag, rc)
                results.append(record)
                runs_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
                continue

        env["HORMUZ_CRISIS_DESCRIPTION"] = str(crisis_yaml)
        stages = run_pipeline_for_run(env, run_id, export_llm=False, max_parallel=args.max_parallel)
        record["stages"] = stages
        record["status"] = "ok" if _pipeline_ok(stages) else "failed"
        logger.info("[%s/%s] pipeline status=%s (%.0fs)", tag, week_tag, record["status"], stages.get("total_seconds", 0.0))
        results.append(record)
        runs_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info("Rerun batch %s complete: %d/%d ok; manifest %s", args.batch_id, ok, len(results), runs_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
