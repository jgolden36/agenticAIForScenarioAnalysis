#!/usr/bin/env python3
"""SLURM entry point for Module 2: Parameter Extraction.

Runs as a SLURM array job. Each array task extracts parameters for one
(scenario, model_spec) pair. The manifest file maps SLURM_ARRAY_TASK_ID
to the specific pair to process.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    auto_approve_enabled,
    get_array_task,
    get_pipeline_config_path,
    get_run_id,
    load_manifest,
    load_state,
    log_slurm_context,
    logger,
    save_state,
)

from src.common.llm import get_llm
from src.common.types import ConfidenceLevel, Scenario, ValidationStatus
from src.common.wandb_logger import (
    WandbLogger,
    log_parameter_extraction,
    per_task_logging_enabled,
    stage_run,
)
from src.parameters.extractor import build_parameter_extractor
from src.parameters.model_specs import ALL_MODEL_SPECS
from src.pipeline.config import PipelineConfig
from src.scenarios.schemas import QuantitativeAssumption, ScenarioNarrative


def main() -> None:
    log_slurm_context()
    run_id = get_run_id()
    task = get_array_task()
    task_id = task["task_id"]

    logger.info(f"=== Module 2: Parameter Extraction (run_id={run_id}, task={task_id}) ===")

    # Load manifest to determine which (scenario, model) pair this task handles
    manifest = load_manifest(run_id, "parameters")
    if task_id >= len(manifest):
        logger.warning(f"Task {task_id} exceeds manifest size {len(manifest)}, exiting")
        return

    entry = manifest[task_id]
    scenario_id_str = entry["scenario_id"]
    model_id = entry["model_id"]
    logger.info(f"Extracting parameters for scenario={scenario_id_str}, model={model_id}")

    # Load scenario state from Module 1
    scenarios_state = load_state(run_id, "scenarios")
    config = PipelineConfig(**scenarios_state["config"])

    narrative_data = None
    for n in scenarios_state["scenario_narratives"]:
        if n["scenario_id"] == scenario_id_str:
            narrative_data = n
            break

    if narrative_data is None:
        logger.error(f"No narrative found for scenario {scenario_id_str}")
        return

    if model_id not in ALL_MODEL_SPECS:
        logger.error(f"Unknown model spec: {model_id}")
        return

    # Per-task W&B run is opt-out (HORMUZ_WANDB_LOG_PER_TASK=0). The
    # synthesis stage will still aggregate every parameter set into a
    # single table on its own W&B run, so disabling per-task logging
    # only loses live progress visibility, not final artefacts.
    wb: WandbLogger
    if per_task_logging_enabled():
        wb_cm = stage_run(
            "parameters",
            run_name=f"{run_id}/parameters/{scenario_id_str}/{model_id}",
            config={
                "scenario_id": scenario_id_str,
                "model_id": model_id,
                "task_id": task_id,
                "llm_provider": config.llm.provider,
                "llm_model": config.llm.model,
            },
            tags=["hormuz", "parameters", scenario_id_str, model_id],
        )
    else:
        # Null context manager: stage_run already returns a no-op
        # WandbLogger when wandb is unavailable, but we want to skip
        # init() entirely when per-task logging is opted out so we
        # don't even hit the network/disk.
        from contextlib import nullcontext
        wb_cm = nullcontext(WandbLogger(run=None, stage="parameters", group=run_id))

    with wb_cm as wb:
        # Build LLM and extractor
        llm = get_llm(
            provider=config.llm.provider,
            model=config.llm.model,
            temperature=config.llm.temperature,
            **config.llm.extra_kwargs,
        )
        extractor = build_parameter_extractor(llm)

        scenario_obj = ScenarioNarrative(
            scenario_id=Scenario(scenario_id_str),
            label=narrative_data["label"],
            description="",
            narrative_timeline=narrative_data["narrative"],
            quantitative_assumptions=[
                QuantitativeAssumption(variable=k, value=str(v))
                for k, v in narrative_data["quantitative_assumptions"].items()
            ],
        )

        model_spec = ALL_MODEL_SPECS[model_id]
        t0 = time.monotonic()
        extraction = extractor.invoke({
            "scenario": scenario_obj,
            "model_spec": model_spec,
        })
        runtime_seconds = time.monotonic() - t0

        param_list = [
            {
                "name": p.name,
                "value": p.value,
                "unit": p.unit,
                "confidence": (
                    p.confidence.value
                    if hasattr(p.confidence, "value")
                    else p.confidence
                ),
                "extraction_note": p.extraction_note,
            }
            for p in extraction.parameters
        ]
        param_set = {
            "scenario_id": scenario_id_str,
            "model_id": model_id,
            "parameters": param_list,
            "validation_status": (
                ValidationStatus.APPROVED.value
                if auto_approve_enabled()
                else ValidationStatus.PENDING.value
            ),
        }

        # Each array task saves its own result; they are merged before Module 3
        save_state(run_id, f"params_{task_id}", param_set)
        logger.info(
            f"Extracted {len(param_set['parameters'])} parameters "
            f"for {scenario_id_str}/{model_id} in {runtime_seconds:.1f}s"
        )

        log_parameter_extraction(
            wb,
            scenario_id=scenario_id_str,
            model_id=model_id,
            parameters=param_list,
            runtime_seconds=runtime_seconds,
        )


if __name__ == "__main__":
    main()
