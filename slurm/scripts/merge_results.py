#!/usr/bin/env python3
"""Merge array job results into consolidated state files.

Utility script to collect scattered per-task output files
(params_0.json, params_1.json, ...) into single consolidated files.
Useful for inspection between stages or after pipeline completion.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    get_run_id,
    logger,
    save_state,
    state_dir,
)


def merge_parameters(run_id: str) -> None:
    """Merge all params_*.json files into a single consolidated file."""
    pattern = str(state_dir() / f"{run_id}_params_*.json")
    files = sorted(glob.glob(pattern))

    results = []
    for f in files:
        with open(f) as fh:
            results.append(json.load(fh))

    logger.info(f"Merged {len(results)} parameter sets from {len(files)} files")
    save_state(run_id, "parameters_merged", {
        "parameter_sets": results,
        "count": len(results),
    })


def merge_model_results(run_id: str) -> None:
    """Merge all model_*.json files into a single consolidated file."""
    pattern = str(state_dir() / f"{run_id}_model_*.json")
    files = sorted(glob.glob(pattern))

    results = []
    for f in files:
        with open(f) as fh:
            results.append(json.load(fh))

    completed = sum(1 for r in results if r.get("status") == "completed")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        f"Merged {len(results)} model results: "
        f"{completed} completed, {skipped} skipped, {failed} failed"
    )
    save_state(run_id, "models_merged", {
        "execution_results": results,
        "count": len(results),
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge SLURM array job results")
    parser.add_argument("stage", choices=["parameters", "models", "all"],
                        help="Which results to merge")
    parser.add_argument("--run-id", default=None, help="Pipeline run ID")
    args = parser.parse_args()

    run_id = args.run_id or get_run_id()

    if args.stage in ("parameters", "all"):
        merge_parameters(run_id)
    if args.stage in ("models", "all"):
        merge_model_results(run_id)


if __name__ == "__main__":
    main()
