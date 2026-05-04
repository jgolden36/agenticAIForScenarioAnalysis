#!/usr/bin/env python3
"""SLURM entry point for Module 4: Output Synthesis.

Collects all model execution results, runs consistency checks,
and produces the synthesized analysis report.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    auto_approve_enabled,
    get_pipeline_config_path,
    get_project_root,
    get_run_id,
    load_state,
    log_slurm_context,
    logger,
    resolve_llm_kwargs,
    resolved_llm_metadata,
    save_state,
    state_dir,
)

from src.common.context_budget import budget_snapshot
from src.common.llm import get_llm
from src.common.types import ModelExecutionStatus, Scenario, ValidationStatus
from src.common.wandb_logger import log_synthesis_summary, stage_run
from src.pipeline.config import PipelineConfig
from src.pipeline.state import (
    ModelExecutionResult,
    ScenarioNarrativeState,
)
from src.synthesis.synthesizer import (
    render_scenario_markdown,
    synthesize_by_section,
)


def collect_model_results(run_id: str) -> list[dict]:
    """Gather all model_*.json result files from the state directory."""
    pattern = str(state_dir() / f"{run_id}_model_*.json")
    results = []
    for path in sorted(glob.glob(pattern)):
        with open(path) as f:
            results.append(json.load(f))
    return results


def collect_parameter_results(run_id: str) -> list[dict]:
    """Gather all params_*.json result files from the state directory."""
    pattern = str(state_dir() / f"{run_id}_params_*.json")
    results = []
    for path in sorted(glob.glob(pattern)):
        with open(path) as f:
            results.append(json.load(f))
    return results


def collect_bash_failures(run_id: str) -> list[dict]:
    """Gather bash-layer failure records written by slurm/jobs/_common.sh.

    These cover failures that happened BEFORE the per-stage Python
    script could write its own status (interpreter crash, missing
    conda env, missing module, etc.). Without ingesting them the
    synthesis report cannot account for tasks that disappeared from
    the *_model_*.json or *_params_*.json files entirely.
    """
    pattern = str(state_dir() / f"{run_id}_*_bash_failure_*.json")
    failures = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                failures.append(json.load(f))
        except Exception as exc:
            logger.warning(f"Could not read bash-failure record {path}: {exc}")
    return failures


def summarise_bash_failures(failures: list[dict]) -> dict[str, int]:
    """Group bash-layer failures by their stage tag for the report."""
    counts: dict[str, int] = {}
    for f in failures:
        stage = f.get("stage", "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def reports_dir(run_id: str) -> Path:
    """Return data/reports/<run_id>/, creating it if necessary."""
    d = get_project_root() / "data" / "reports" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_synthesis_artifacts(
    run_id: str,
    synthesis_state: dict,
    per_scenario: list[dict],
) -> None:
    """Write the per-run report files to data/reports/<run_id>/.

    Files written:
    - ``synthesis.json``  — full synthesis state dict
    - ``summary.json``    — counts (completed / skipped / failed) plus
                            per-scenario outcome and consistency-flag counts
    - ``<scenario>.md``   — Markdown rendering of each ScenarioSynthesis
    - ``synthesis.md``    — top-level cross-scenario index linking to each
                            per-scenario file
    """
    out = reports_dir(run_id)

    with open(out / "synthesis.json", "w") as f:
        json.dump(synthesis_state, f, indent=2, default=str)

    summary = {
        "run_id": run_id,
        "completed": synthesis_state.get("completed", 0),
        "skipped": synthesis_state.get("skipped", 0),
        "failed": synthesis_state.get("failed", 0),
        "consistency_flags": len(synthesis_state.get("consistency_flags", []) or []),
        "outcomes_total": len(synthesis_state.get("synthesis_results", []) or []),
        "scenarios": [
            {
                "scenario_id": entry["scenario_id"],
                "label": entry["label"],
                "outcomes": entry["outcome_count"],
                "consistency_flags": entry["consistency_flag_count"],
                "failed_models": entry["failed_models"],
                "completed_models": entry["completed_models"],
                "skipped_models": entry["skipped_models"],
            }
            for entry in per_scenario
        ],
    }
    with open(out / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    index_lines: list[str] = [
        f"# Hormuz pipeline synthesis — run `{run_id}`",
        "",
        f"- Completed model runs: **{summary['completed']}**",
        f"- Skipped model runs:   **{summary['skipped']}**",
        f"- Failed model runs:    **{summary['failed']}**",
        f"- Total synthesized outcomes: **{summary['outcomes_total']}**",
        f"- Cross-model consistency flags: **{summary['consistency_flags']}**",
        "",
        "## Scenarios",
        "",
    ]
    for entry in per_scenario:
        scenario_md_path = out / f"{entry['scenario_id']}.md"
        with open(scenario_md_path, "w") as f:
            f.write(entry["markdown"])
        index_lines.append(
            f"### [{entry['label']}]({entry['scenario_id']}.md)"
        )
        index_lines.append("")
        index_lines.append(
            f"- Outcomes: {entry['outcome_count']}; "
            f"consistency flags: {entry['consistency_flag_count']}; "
            f"completed/skipped/failed: "
            f"{entry['completed_models']} / {entry['skipped_models']} / {entry['failed_models']}"
        )
        index_lines.append("")

    with open(out / "synthesis.md", "w") as f:
        f.write("\n".join(index_lines))

    logger.info(f"Synthesis report written to {out}")


def main() -> None:
    log_slurm_context()
    run_id = get_run_id()

    logger.info(f"=== Module 4: Synthesis (run_id={run_id}) ===")

    # Load scenario state
    scenarios_state = load_state(run_id, "scenarios")
    config = PipelineConfig(**scenarios_state["config"])

    # Collect all model results from array job outputs
    model_results = collect_model_results(run_id)
    param_results = collect_parameter_results(run_id)
    bash_failures = collect_bash_failures(run_id)
    bash_failure_summary = summarise_bash_failures(bash_failures)

    completed = sum(1 for r in model_results if r.get("status") == ModelExecutionStatus.COMPLETED.value)
    skipped = sum(1 for r in model_results if r.get("status") == ModelExecutionStatus.SKIPPED.value)
    failed = sum(1 for r in model_results if r.get("status") == ModelExecutionStatus.FAILED.value)

    logger.info(
        f"Collected {len(model_results)} model results: "
        f"{completed} completed, {skipped} skipped, {failed} failed"
    )
    logger.info(f"Collected {len(param_results)} parameter sets")
    if bash_failures:
        logger.warning(
            f"Collected {len(bash_failures)} bash-layer failure record(s) "
            f"by stage: {bash_failure_summary}"
        )
    else:
        logger.info("No bash-layer failure records found.")

    # Synthesis is the canonical aggregator: even when per-task W&B
    # logging is off, this run captures every model result + parameter
    # set + consistency flag + synthesised outcome. The state files and
    # synthesis report are also uploaded as a W&B Artifact so the
    # auditable provenance chain is reachable from the W&B UI.
    llm_meta = resolved_llm_metadata(config)
    # Snapshot of the LLM context budget that will apply to every
    # per-section call below. Logged once up-front so post-hoc analysis
    # of truncation events has a reliable reference point.
    budget = budget_snapshot()
    logger.info(
        f"LLM context budget: window={budget['context_window']} "
        f"prompt={budget['prompt_budget_tokens']} "
        f"completion={budget['completion_budget_tokens']} "
        f"tiktoken_available={budget['tiktoken_available']}"
    )

    with stage_run(
        "synthesis",
        config={
            "model_results_count": len(model_results),
            "parameter_sets": len(param_results),
            "bash_failures": len(bash_failures),
            "auto_approve": auto_approve_enabled(),
            "context_budget": budget,
            **llm_meta,
        },
        notes="Module 4: cross-model consistency check + section-chunked synthesis",
    ) as wb:
        # Build LLM. Env vars (PIPELINE_LLM_PROVIDER / _MODEL / _BASE_URL)
        # win over the YAML config so the SLURM driver job — which is
        # what actually started the vLLM sidecar — owns the model name.
        llm = get_llm(**resolve_llm_kwargs(config))

        all_flags = []
        all_synthesis = []
        per_scenario_artifacts: list[dict] = []
        # Per-(scenario, section) telemetry — what each LLM call sent
        # in tokens and whether the overflow retry kicked in. Surfaced
        # as a single context_budget_events list on the synthesis state
        # so the W&B run + the synthesis.json report both have the
        # detail downstream consumers need to diagnose silent
        # truncations.
        context_budget_events: list[dict] = []

        for scenario in Scenario:
            scenario_results = [
                ModelExecutionResult(**r)
                for r in model_results
                if r.get("scenario_id") == scenario.value
            ]
            if not scenario_results:
                logger.info(f"No results for scenario {scenario.value}, skipping")
                continue

            # Find narrative
            narrative_data = None
            for n in scenarios_state["scenario_narratives"]:
                if n["scenario_id"] == scenario.value:
                    narrative_data = n
                    break

            if narrative_data is None:
                logger.warning(f"No narrative for scenario {scenario.value}")
                continue

            narrative_state = ScenarioNarrativeState(
                scenario_id=scenario,
                label=narrative_data["label"],
                narrative=narrative_data["narrative"],
                quantitative_assumptions=narrative_data["quantitative_assumptions"],
                consistency_notes=narrative_data.get("consistency_notes", ""),
            )

            # Section-chunked synthesis — one LLM call per
            # (time_horizon, outcome_scope) pair instead of one
            # monolithic per-scenario call. Each call carries only the
            # model outputs routed to that section by
            # src/synthesis/sectioning.py and is wrapped with the
            # overflow retry from src.common.llm so a context-length
            # error halves the prompt and retries once before failing.
            logger.info(
                f"Synthesizing results for scenario {scenario.value} "
                f"(section-chunked, ≤6 LLM calls)..."
            )
            flags, synthesis, section_metrics = synthesize_by_section(
                llm,
                scenario_id=scenario,
                narrative=narrative_state,
                results=scenario_results,
                consistency_config=config.consistency,
            )
            all_flags.extend([f.model_dump() for f in flags])

            # Surface per-section telemetry into the run state.
            for section_key, metrics in section_metrics.items():
                context_budget_events.append({
                    "scenario_id": scenario.value,
                    "time_horizon": section_key.time_horizon.value,
                    "outcome_scope": section_key.outcome_scope.value,
                    **metrics,
                })
                if metrics["status"] == "failed":
                    logger.warning(
                        f"[synthesis] scenario={scenario.value} "
                        f"section={section_key.label()} FAILED "
                        f"(prompt_tokens≈{metrics['prompt_tokens']}, "
                        f"truncations={metrics['truncation_attempts']}, "
                        f"error={metrics.get('error')})"
                    )
                elif metrics["truncation_attempts"] > 0:
                    logger.warning(
                        f"[synthesis] scenario={scenario.value} "
                        f"section={section_key.label()} OK after "
                        f"{metrics['truncation_attempts']} truncation retry(ies) "
                        f"(prompt_tokens≈{metrics['prompt_tokens']})"
                    )
                else:
                    logger.info(
                        f"[synthesis] scenario={scenario.value} "
                        f"section={section_key.label()} {metrics['status']} "
                        f"(models={metrics['model_count']}, "
                        f"prompt_tokens≈{metrics['prompt_tokens']})"
                    )

            scenario_outcome_count = 0
            for section in synthesis.sections:
                for outcome in section.outcomes:
                    scenario_outcome_count += 1
                    all_synthesis.append({
                        "scenario_id": scenario.value,
                        "time_horizon": section.time_horizon.value,
                        "outcome_scope": section.outcome_scope.value,
                        "outcome_variable": outcome.variable,
                        "value": outcome.value,
                        "source_model_id": outcome.source_model_id,
                        "narrative_summary": outcome.narrative,
                    })

            scenario_completed = sum(
                1 for r in scenario_results
                if r.status == ModelExecutionStatus.COMPLETED
            )
            scenario_skipped = sum(
                1 for r in scenario_results
                if r.status == ModelExecutionStatus.SKIPPED
            )
            scenario_failed = sum(
                1 for r in scenario_results
                if r.status == ModelExecutionStatus.FAILED
            )

            per_scenario_artifacts.append({
                "scenario_id": scenario.value,
                "label": narrative_data["label"],
                "markdown": render_scenario_markdown(synthesis),
                "outcome_count": scenario_outcome_count,
                "consistency_flag_count": len(flags),
                "completed_models": scenario_completed,
                "skipped_models": scenario_skipped,
                "failed_models": scenario_failed,
            })

        # Roll the per-section telemetry up so the W&B summary and any
        # post-hoc analysis can answer "which sections needed
        # truncation, which ones failed?" in one query.
        truncations_total = sum(
            ev.get("truncation_attempts", 0) for ev in context_budget_events
        )
        sections_failed = sum(
            1 for ev in context_budget_events if ev.get("status") == "failed"
        )
        sections_truncated = sum(
            1 for ev in context_budget_events if ev.get("truncation_attempts", 0) > 0
        )

        synthesis_state = {
            "run_id": run_id,
            "model_results_count": len(model_results),
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "bash_failures_count": len(bash_failures),
            "bash_failures_by_stage": bash_failure_summary,
            "bash_failures": bash_failures,
            "consistency_flags": all_flags,
            "synthesis_results": all_synthesis,
            "synthesis_validated": auto_approve_enabled(),
            "context_budget": budget,
            "context_budget_events": context_budget_events,
            "context_budget_summary": {
                "section_calls": len(context_budget_events),
                "sections_failed": sections_failed,
                "sections_truncated": sections_truncated,
                "truncation_attempts_total": truncations_total,
            },
        }
        save_state(run_id, "synthesis", synthesis_state)
        write_synthesis_artifacts(run_id, synthesis_state, per_scenario_artifacts)

        # ----- W&B aggregations -----
        log_synthesis_summary(
            wb,
            synthesis_state=synthesis_state,
            model_results=model_results,
            parameter_results=param_results,
        )

        # Upload all run state files (scenarios, parameter sets, model
        # results, synthesis) and any reports as a single W&B Artifact
        # so the full provenance chain is downloadable from the UI.
        sd = state_dir()
        artifact_files = sorted(
            list(sd.glob(f"{run_id}_*.json"))
            + list(sd.glob(f"{run_id}_*.jsonl"))
        )
        # Reports directory is small; include the whole thing for this
        # run if it exists.
        reports_dir = state_dir().parent / "reports" / run_id
        if reports_dir.exists():
            artifact_files.append(reports_dir)
        wb.log_artifact(
            name=f"hormuz-run-{run_id}",
            artifact_type="pipeline-results",
            files=artifact_files,
            description=(
                f"Hormuz pipeline run {run_id}: "
                f"{completed} completed / {skipped} skipped / {failed} failed "
                f"models across {len(scenarios_state['scenario_narratives'])} scenarios."
            ),
            metadata={
                "run_id": run_id,
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
                "consistency_flags": len(all_flags),
                "outcomes": len(all_synthesis),
                "validated": auto_approve_enabled(),
            },
        )

        wb.log_summary(
            {
                "run_id": run_id,
                "completed": completed,
                "skipped": skipped,
                "failed": failed,
                "consistency_flags": len(all_flags),
                "outcomes": len(all_synthesis),
                "validated": auto_approve_enabled(),
            },
        )

        # Optional alert on regression-style failures (no-op on free
        # plans).
        if failed > 0:
            wb.alert(
                title=f"Hormuz {run_id}: {failed} model failure(s)",
                text=(
                    f"{failed} domain models failed on run {run_id}. "
                    f"See synthesis run for the full table."
                ),
                level="WARN",
            )

        if auto_approve_enabled():
            logger.info("Auto-approve enabled — synthesis approved automatically")
        else:
            logger.info(
                "HITL CHECKPOINT: Synthesis needs manual review.\n"
                "Review the state file, then mark as approved."
            )

        logger.info(
            f"Synthesis complete: {len(all_synthesis)} outcomes, "
            f"{len(all_flags)} consistency flags"
        )
        if wb.url:
            logger.info(f"W&B run: {wb.url}")


if __name__ == "__main__":
    main()
