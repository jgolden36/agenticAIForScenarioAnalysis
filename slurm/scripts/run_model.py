#!/usr/bin/env python3
"""SLURM entry point for Module 3: Single Model Execution.

Runs as a SLURM array job. Each array task executes one domain model
for one scenario. The manifest file maps SLURM_ARRAY_TASK_ID to the
specific (scenario, model) pair and its parameter set.
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    get_array_task,
    get_run_id,
    load_manifest,
    log_slurm_context,
    logger,
    save_state,
)

from src.common.types import ModelExecutionStatus
from src.common.wandb_logger import (
    WandbLogger,
    log_model_execution,
    per_task_logging_enabled,
    stage_run,
)
from src.models.registry import build_default_registry


def main() -> None:
    log_slurm_context()
    run_id = get_run_id()
    task = get_array_task()
    task_id = task["task_id"]

    logger.info(f"=== Module 3: Model Execution (run_id={run_id}, task={task_id}) ===")

    # Load execution manifest (CPU and GPU jobs use different manifests)
    manifest_name = os.environ.get("HORMUZ_MANIFEST_NAME", "models")
    manifest = load_manifest(run_id, manifest_name)
    if task_id >= len(manifest):
        logger.warning(f"Task {task_id} exceeds manifest size {len(manifest)}, exiting")
        return

    entry = manifest[task_id]
    scenario_id = entry["scenario_id"]
    model_id = entry["model_id"]
    # Defensive copy + scenario_id injection. dispatch_models.py is the
    # primary injection site, but we belt-and-suspenders here so that a
    # manifest produced by older tooling (or an analyst-edited manifest)
    # still satisfies adapters that need params['scenario_id'].
    params = dict(entry["parameters"])
    params.setdefault("scenario_id", scenario_id)
    resource_class = entry.get("resource_class", "cpu")

    logger.info(
        f"Executing model={model_id} scenario={scenario_id} "
        f"resource_class={resource_class}"
    )

    registry = build_default_registry()
    adapter = registry.get(model_id)

    result = {
        "scenario_id": scenario_id,
        "model_id": model_id,
        "task_id": task_id,
        "node": task["node"],
        "slurm_job_id": task["job_id"],
        "resource_class": resource_class,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Per-task W&B run is opt-out. The synthesis stage aggregates every
    # model result into a master table on its own run regardless, so
    # disabling per-task logging only loses live visibility, not data.
    if per_task_logging_enabled():
        wb_cm = stage_run(
            "models",
            run_name=f"{run_id}/models/{scenario_id}/{model_id}",
            config={
                "scenario_id": scenario_id,
                "model_id": model_id,
                "task_id": task_id,
                "resource_class": resource_class,
                "node": task["node"],
                "adapter_present": adapter is not None,
            },
            tags=["hormuz", "models", scenario_id, model_id, resource_class],
        )
    else:
        wb_cm = nullcontext(WandbLogger(run=None, stage="models", group=run_id))

    with wb_cm as wb:
        if adapter is None:
            result["status"] = ModelExecutionStatus.FAILED.value
            result["error_message"] = f"Model {model_id} not found in registry"
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_state(run_id, f"model_{task_id}", result)
            log_model_execution(wb, result)
            logger.error(result["error_message"])
            return

        t0 = time.monotonic()

        try:
            validation = adapter.validate_inputs(params)
            if not validation.valid:
                result["status"] = ModelExecutionStatus.FAILED.value
                result["error_message"] = (
                    f"Validation failed: {'; '.join(validation.errors)}"
                )
                result["completed_at"] = datetime.now(timezone.utc).isoformat()
                save_state(run_id, f"model_{task_id}", result)
                log_model_execution(wb, result)
                logger.error(result["error_message"])
                return

            native_inputs = adapter.translate_inputs(params)
            output = adapter.execute(native_inputs)

            elapsed = time.monotonic() - t0
            result["status"] = ModelExecutionStatus.COMPLETED.value
            result["outputs"] = output.outputs
            result["runtime_seconds"] = elapsed
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Model {model_id} completed in {elapsed:.1f}s")

        except NotImplementedError as e:
            result["status"] = ModelExecutionStatus.SKIPPED.value
            result["error_message"] = f"Not yet implemented: {e}"
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.warning(f"Model {model_id} skipped: {e}")

        except Exception as e:
            elapsed = time.monotonic() - t0
            result["status"] = ModelExecutionStatus.FAILED.value
            result["error_message"] = f"{type(e).__name__}: {e}"
            result["runtime_seconds"] = elapsed
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.error(f"Model {model_id} failed after {elapsed:.1f}s: {e}")

        save_state(run_id, f"model_{task_id}", result)
        log_model_execution(wb, result)


if __name__ == "__main__":
    main()
