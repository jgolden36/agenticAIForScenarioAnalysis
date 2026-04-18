#!/usr/bin/env python3
"""Check the status of a pipeline run.

Scans the state directory for a given run_id and reports which
stages have completed, how many model results exist, and any errors.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import get_run_id, state_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Check pipeline run status")
    parser.add_argument("--run-id", default=None, help="Pipeline run ID")
    args = parser.parse_args()

    run_id = args.run_id or get_run_id()
    sd = state_dir()

    print(f"Pipeline Run: {run_id}")
    print(f"State dir:    {sd}")
    print("=" * 60)

    # Stage 1: Scenarios
    scenarios_file = sd / f"{run_id}_scenarios.json"
    if scenarios_file.exists():
        with open(scenarios_file) as f:
            data = json.load(f)
        n = len(data.get("scenario_narratives", []))
        validated = data.get("scenarios_validated", False)
        print(f"Stage 1 (Scenarios):    {n} generated, validated={validated}")
    else:
        print("Stage 1 (Scenarios):    NOT STARTED")

    # Stage 2: Parameters
    param_files = glob.glob(str(sd / f"{run_id}_params_*.json"))
    if param_files:
        print(f"Stage 2 (Parameters):   {len(param_files)} extraction results")
    else:
        print("Stage 2 (Parameters):   NOT STARTED")

    # Stage 3: Models
    model_files = glob.glob(str(sd / f"{run_id}_model_*.json"))
    if model_files:
        statuses = {"completed": 0, "skipped": 0, "failed": 0}
        for mf in model_files:
            with open(mf) as f:
                r = json.load(f)
            s = r.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1
        print(
            f"Stage 3 (Models):       {len(model_files)} results — "
            f"{statuses.get('completed', 0)} completed, "
            f"{statuses.get('skipped', 0)} skipped, "
            f"{statuses.get('failed', 0)} failed"
        )
    else:
        print("Stage 3 (Models):       NOT STARTED")

    # Stage 4: Synthesis
    synthesis_file = sd / f"{run_id}_synthesis.json"
    if synthesis_file.exists():
        with open(synthesis_file) as f:
            data = json.load(f)
        n_synth = len(data.get("synthesis_results", []))
        n_flags = len(data.get("consistency_flags", []))
        validated = data.get("synthesis_validated", False)
        print(
            f"Stage 4 (Synthesis):    {n_synth} outcomes, "
            f"{n_flags} consistency flags, validated={validated}"
        )
    else:
        print("Stage 4 (Synthesis):    NOT STARTED")

    # Manifests
    print()
    manifest_dir = sd / "manifests"
    if manifest_dir.exists():
        manifests = list(manifest_dir.glob(f"{run_id}_*.json"))
        for m in manifests:
            with open(m) as f:
                entries = json.load(f)
            print(f"Manifest {m.stem}: {len(entries)} entries")


if __name__ == "__main__":
    main()
