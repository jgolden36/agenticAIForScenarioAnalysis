#!/usr/bin/env python3
"""Generate manifest files that drive SLURM array jobs.

Called between pipeline stages to determine what work needs dispatching.
Produces JSON manifests that map SLURM_ARRAY_TASK_ID to specific
(scenario, model, parameters) tuples.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    get_project_root,
    get_run_id,
    load_state,
    logger,
    save_manifest,
    state_dir,
)

from src.models.registry import build_default_registry
from src.parameters.model_specs import ALL_MODEL_SPECS


def _build_routing_sets() -> tuple[set[str], set[str]]:
    """Derive GPU and high-memory model id sets from the live registry.

    The registry is the single source of truth: each adapter declares
    `ResourceRequirements.requires_gpu` and `memory_gb`. Hard-coding
    membership lists (the previous approach) drifted from reality
    (e.g. "futures_forecasting" did not match the actual model id
    "futures") and silently mis-routed work.
    """
    config_dir = get_project_root() / "configs" / "model_configs"
    registry = build_default_registry(
        config_dir if config_dir.exists() else None
    )
    gpu_ids = {a.model_id for a in registry.get_gpu_models()}
    highmem_ids = {
        a.model_id
        for a in registry.all_adapters()
        if a.resource_requirements.memory_gb >= 64
    }
    logger.info(
        f"Routing sets from registry: {len(gpu_ids)} GPU model(s), "
        f"{len(highmem_ids)} high-memory model(s)"
    )
    return gpu_ids, highmem_ids


GPU_MODELS, HIGHMEM_MODELS = _build_routing_sets()


def _write_count_sidecar(run_id: str, name: str, count: int) -> None:
    """Persist a per-stage entry count so submit_pipeline.sh can shrink
    the SLURM array bound to exactly the manifest size.
    """
    sidecar_dir = state_dir() / "manifests"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    out = sidecar_dir / f"{run_id}_{name}_count.txt"
    with open(out, "w") as f:
        f.write(f"{count}\n")
    logger.info(f"Manifest count sidecar written: {out} -> {count}")


def generate_parameter_manifest(run_id: str) -> int:
    """Create a manifest for Module 2 parameter extraction array jobs.

    Each entry is one (scenario_id, model_id) pair.
    Returns the number of entries (= max SLURM array index + 1).
    """
    scenarios_state = load_state(run_id, "scenarios")
    narratives = scenarios_state["scenario_narratives"]

    entries = []
    for narrative in narratives:
        for model_id in ALL_MODEL_SPECS:
            entries.append({
                "scenario_id": narrative["scenario_id"],
                "model_id": model_id,
            })

    save_manifest(run_id, "parameters", entries)
    _write_count_sidecar(run_id, "parameters", len(entries))
    logger.info(f"Parameter manifest: {len(entries)} entries "
                f"({len(narratives)} scenarios × {len(ALL_MODEL_SPECS)} models)")
    return len(entries)


def generate_model_manifest(run_id: str) -> dict[str, int]:
    """Create manifests for Module 3 model execution array jobs.

    Reads the extracted parameters and creates three manifests:
    - models: all model executions combined (for single-partition submission)
    - models_cpu: CPU-only models
    - models_gpu: GPU-requiring models

    Returns dict of manifest_name -> entry_count.
    """
    # Collect all parameter extraction results
    import glob
    pattern = str(state_dir() / f"{run_id}_params_*.json")
    param_files = sorted(Path(p) for p in glob.glob(pattern))

    all_entries = []
    cpu_entries = []
    gpu_entries = []

    for pf in param_files:
        with open(pf) as f:
            ps = json.load(f)

        model_id = ps["model_id"]
        params = {p["name"]: p["value"] for p in ps["parameters"]}
        # Inject scenario_id (canonical Scenario enum value) into the
        # adapter-facing params dict. Adapters that scenario-route on
        # this key (NEMS, MAM, ...) would otherwise raise a validation
        # failure of "Missing required parameter: 'scenario_id'" because
        # the LLM's parameter extraction does not necessarily produce it.
        # An LLM-extracted scenario_id, if present, is preserved.
        params.setdefault("scenario_id", ps["scenario_id"])

        if model_id in GPU_MODELS:
            resource_class = "gpu"
        elif model_id in HIGHMEM_MODELS:
            resource_class = "highmem"
        else:
            resource_class = "cpu"

        entry = {
            "scenario_id": ps["scenario_id"],
            "model_id": model_id,
            "parameters": params,
            "resource_class": resource_class,
        }
        all_entries.append(entry)

        if resource_class == "gpu":
            gpu_entries.append(entry)
        else:
            cpu_entries.append(entry)

    save_manifest(run_id, "models", all_entries)
    save_manifest(run_id, "models_cpu", cpu_entries)
    save_manifest(run_id, "models_gpu", gpu_entries)

    counts = {
        "models": len(all_entries),
        "models_cpu": len(cpu_entries),
        "models_gpu": len(gpu_entries),
    }
    for name, count in counts.items():
        _write_count_sidecar(run_id, name, count)
    logger.info(f"Model manifests: {counts}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SLURM array job manifests")
    parser.add_argument("stage", choices=["parameters", "models"],
                        help="Which stage to generate manifests for")
    parser.add_argument("--run-id", default=None,
                        help="Pipeline run ID (default: from env)")
    args = parser.parse_args()

    run_id = args.run_id or get_run_id()

    if args.stage == "parameters":
        count = generate_parameter_manifest(run_id)
        print(f"MANIFEST_COUNT={count}")
    elif args.stage == "models":
        counts = generate_model_manifest(run_id)
        print(f"MANIFEST_COUNT_ALL={counts['models']}")
        print(f"MANIFEST_COUNT_CPU={counts['models_cpu']}")
        print(f"MANIFEST_COUNT_GPU={counts['models_gpu']}")


if __name__ == "__main__":
    main()
