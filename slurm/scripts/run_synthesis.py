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
    get_run_id,
    load_state,
    log_slurm_context,
    logger,
    save_state,
    state_dir,
)

from src.common.llm import get_llm
from src.common.types import ModelExecutionStatus, Scenario, ValidationStatus
from src.common.wandb_logger import log_synthesis_summary, stage_run
from src.pipeline.config import PipelineConfig
from src.pipeline.state import (
    ModelExecutionResult,
    ScenarioNarrativeState,
)
from src.synthesis.consistency import check_consistency
from src.synthesis.synthesizer import build_synthesizer


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
    with stage_run(
        "synthesis",
        config={
            "model_results_count": len(model_results),
            "parameter_sets": len(param_results),
            "bash_failures": len(bash_failures),
            "auto_approve": auto_approve_enabled(),
            "llm_provider": config.llm.provider,
            "llm_model": config.llm.model,
        },
        notes="Module 4: cross-model consistency check + synthesis",
    ) as wb:
        # Build LLM
        llm = get_llm(
            provider=config.llm.provider,
            model=config.llm.model,
            temperature=config.llm.temperature,
            **config.llm.extra_kwargs,
        )
        synthesizer = build_synthesizer(llm)

        all_flags = []
        all_synthesis = []

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

            # Consistency checks
            logger.info(f"Running consistency checks for scenario {scenario.value}...")
            flags = check_consistency(scenario, scenario_results, config.consistency)
            all_flags.extend([f.model_dump() for f in flags])

            # LLM synthesis
            logger.info(f"Synthesizing results for scenario {scenario.value}...")
            synthesis = synthesizer.invoke({
                "narrative": narrative_state,
                "results": scenario_results,
                "consistency_flags": flags,
            })

            for section in synthesis.sections:
                for outcome in section.outcomes:
                    all_synthesis.append({
                        "scenario_id": scenario.value,
                        "time_horizon": section.time_horizon.value,
                        "outcome_scope": section.outcome_scope.value,
                        "outcome_variable": outcome.variable,
                        "value": outcome.value,
                        "source_model_id": outcome.source_model_id,
                        "narrative_summary": outcome.narrative,
                    })

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
        }
        save_state(run_id, "synthesis", synthesis_state)

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
