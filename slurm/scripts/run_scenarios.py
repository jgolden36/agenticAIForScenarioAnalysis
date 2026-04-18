#!/usr/bin/env python3
"""SLURM entry point for Module 1: Scenario Generation.

Generates scenario narratives via LLM and persists them for the next stage.
If auto-approve is enabled, the HITL checkpoint is skipped.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    auto_approve_enabled,
    get_pipeline_config_path,
    get_project_root,
    get_run_id,
    log_slurm_context,
    logger,
    save_state,
)

import yaml
from src.common.llm import get_llm
from src.common.types import ValidationStatus
from src.common.wandb_logger import log_scenario_narratives, stage_run
from src.pipeline.config import PipelineConfig
from src.scenarios.framework import ScenarioFramework
from src.scenarios.generator import build_scenario_generator


def main() -> None:
    log_slurm_context()
    run_id = get_run_id()
    root = get_project_root()

    logger.info(f"=== Module 1: Scenario Generation (run_id={run_id}) ===")

    config = PipelineConfig.from_yaml(get_pipeline_config_path())

    # Crisis description: honour HORMUZ_CRISIS_DESCRIPTION when set
    # (used by the weekly news-driven pipeline to feed an updated,
    # per-week YAML produced by build_weekly_brief.py). Falls back to
    # the baseline Hormuz 2026 file otherwise.
    env_crisis = os.environ.get("HORMUZ_CRISIS_DESCRIPTION")
    if env_crisis:
        crisis_path = Path(env_crisis)
        if not crisis_path.is_absolute():
            crisis_path = root / crisis_path
        logger.info(f"Using crisis description from env: {crisis_path}")
    else:
        crisis_path = root / "configs" / "crisis_descriptions" / "hormuz_2026.yaml"
    with open(crisis_path) as f:
        crisis_data = yaml.safe_load(f)
    crisis_description = crisis_data.get("description", yaml.dump(crisis_data))

    # Load scenario framework
    framework_path = root / "configs" / "scenario_frameworks" / "hormuz_2026.yaml"
    with open(framework_path) as f:
        framework_data = yaml.safe_load(f)
    framework = ScenarioFramework(**framework_data)

    # Open a W&B run for this stage. The context manager finishes the
    # run cleanly even on exception; logging is a no-op when wandb is
    # unavailable / disabled (see src/common/wandb_logger.py).
    with stage_run(
        "scenarios",
        config={
            "num_scenarios": config.num_scenarios,
            "llm_provider": config.llm.provider,
            "llm_model": config.llm.model,
            "llm_temperature": config.llm.temperature,
            "framework_focal_issue": framework_data.get("focal_issue"),
        },
        notes="Module 1: scenario generation",
    ) as wb:
        # Build LLM and generator
        llm = get_llm(
            provider=config.llm.provider,
            model=config.llm.model,
            temperature=config.llm.temperature,
            **config.llm.extra_kwargs,
        )
        generator = build_scenario_generator(llm)

        # Generate scenarios
        logger.info("Generating scenario narratives...")
        scenario_set = generator.invoke({
            "crisis_description": crisis_description,
            "framework": framework,
            "num_scenarios": config.num_scenarios,
        })

        narratives = []
        for s in scenario_set.scenarios:
            n = {
                "scenario_id": s.scenario_id.value,
                "label": s.label,
                "narrative": s.narrative_timeline,
                "quantitative_assumptions": {
                    a.variable: a.value for a in s.quantitative_assumptions
                },
                "consistency_notes": s.consistency_notes,
                "validation_status": ValidationStatus.PENDING.value,
            }
            if auto_approve_enabled():
                n["validation_status"] = ValidationStatus.APPROVED.value
            narratives.append(n)

        logger.info(f"Generated {len(narratives)} scenario narratives")

        state = {
            "run_id": run_id,
            "config": config.model_dump(),
            "crisis_description": crisis_description,
            "framework": framework_data,
            "scenario_narratives": narratives,
            "scenarios_validated": auto_approve_enabled(),
        }
        save_state(run_id, "scenarios", state)

        # Push narratives + summary metrics to W&B.
        log_scenario_narratives(wb, narratives)
        wb.log_summary(
            {
                "run_id": run_id,
                "auto_approve": auto_approve_enabled(),
                "scenarios_url": str(
                    root / "data" / "pipeline_state" / f"{run_id}_scenarios.json"
                ),
            }
        )

        if auto_approve_enabled():
            logger.info("Auto-approve enabled — scenarios approved automatically")
        else:
            logger.info(
                "HITL CHECKPOINT: Scenarios need manual review.\n"
                "Review the state file, update validation_status to 'approved',\n"
                "then submit the next stage."
            )


if __name__ == "__main__":
    main()
