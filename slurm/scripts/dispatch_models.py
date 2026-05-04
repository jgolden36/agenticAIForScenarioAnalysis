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

from src.common.types import ANALYTICAL_LEVEL_ORDER, AnalyticalLevel
from src.models.registry import build_default_registry, default_config_dir
from src.parameters.model_specs import ALL_MODEL_SPECS
from src.pipeline.upstream_forwarding import (
    compute_downstream_inputs,
    load_mapping,
    merge_into_params,
)


_COMMODITY_LEVELS = {AnalyticalLevel.COMBAT, AnalyticalLevel.COMMODITY}
_COMMODITY_DOWNSTREAM_LEVELS = {AnalyticalLevel.COMMODITY_DOWNSTREAM}
_MACRO_LEVELS = {
    AnalyticalLevel.SHORT_RUN_MACRO,
    AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC,
}


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


def _load_param_entries(run_id: str) -> list[dict]:
    """Read every per-task parameter extraction result for a run."""
    import glob

    pattern = str(state_dir() / f"{run_id}_params_*.json")
    out: list[dict] = []
    for pf in sorted(Path(p) for p in glob.glob(pattern)):
        with open(pf) as f:
            out.append(json.load(f))
    return out


def _resource_class(model_id: str) -> str:
    if model_id in GPU_MODELS:
        return "gpu"
    if model_id in HIGHMEM_MODELS:
        return "highmem"
    return "cpu"


def _build_entry(
    scenario_id: str,
    model_id: str,
    params: dict,
    upstream_overrides: list[dict] | None = None,
) -> dict:
    params = dict(params)
    params.setdefault("scenario_id", scenario_id)
    entry: dict = {
        "scenario_id": scenario_id,
        "model_id": model_id,
        "parameters": params,
        "resource_class": _resource_class(model_id),
    }
    if upstream_overrides:
        entry["_upstream_overrides"] = upstream_overrides
    return entry


def _split_entries_by_resource(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    cpu, gpu = [], []
    for e in entries:
        if e["resource_class"] == "gpu":
            gpu.append(e)
        else:
            cpu.append(e)
    return cpu, gpu


def _save_tier_manifests(
    run_id: str, name: str, entries: list[dict]
) -> dict[str, int]:
    cpu, gpu = _split_entries_by_resource(entries)
    counts = {
        name: len(entries),
        f"{name}_cpu": len(cpu),
        f"{name}_gpu": len(gpu),
    }
    save_manifest(run_id, name, entries)
    save_manifest(run_id, f"{name}_cpu", cpu)
    save_manifest(run_id, f"{name}_gpu", gpu)
    for k, v in counts.items():
        _write_count_sidecar(run_id, k, v)
    return counts


def _model_id_to_level(
    config_dir: Path | None = None,
) -> dict[str, AnalyticalLevel]:
    """Resolve each registered model's analytical level once."""
    registry = build_default_registry(
        config_dir if config_dir is not None and config_dir.exists() else None
    )
    return {a.model_id: a.analytical_level for a in registry.all_adapters()}


def generate_model_manifest(run_id: str, tier: str = "all") -> dict[str, int]:
    """Create manifests for Module 3 model execution array jobs.

    Args:
        run_id: pipeline run id.
        tier:
            - ``"all"``  (legacy): one combined ``models`` manifest with
              every model and no upstream-to-downstream forwarding.
              Kept for backwards compat with callers that don't split
              Stage 3.
            - ``"commodity"``: only combat + commodity tier adapters
              (manifest names ``models_commodity*``).
            - ``"commodity_downstream"``: only commodity-downstream
              adapters (today: SimRLFab, Argonne ABM). Reads completed
              commodity outputs from
              ``data/outputs/<scenario>/<model>/output.json``, runs the
              upstream-to-downstream merge (helium ->
              semiconductors / helium-ABM), persists the override
              records to
              ``data/pipeline_state/<run_id>_commodity_downstream_overrides.json``,
              and embeds them on each manifest entry.
            - ``"macro"``: only short-run + long-run macro adapters
              (manifest names ``models_macro*``). Reads completed
              commodity AND commodity-downstream outputs, runs the
              upstream-to-macro merge, persists override records to
              ``data/pipeline_state/<run_id>_macro_overrides.json``,
              and embeds them on each manifest entry.

    Returns:
        ``{manifest_name: entry_count}`` for the manifests written.
    """
    valid_tiers = ("all", "commodity", "commodity_downstream", "macro")
    if tier not in valid_tiers:
        raise ValueError(
            f"Unknown tier {tier!r}; expected one of {list(valid_tiers)}"
        )

    cfg_dir = default_config_dir()
    level_by_model = _model_id_to_level(cfg_dir)
    param_entries = _load_param_entries(run_id)

    if tier == "all":
        entries = [
            _build_entry(
                ps["scenario_id"],
                ps["model_id"],
                {p["name"]: p["value"] for p in ps["parameters"]},
            )
            for ps in param_entries
        ]
        counts = _save_tier_manifests(run_id, "models", entries)
        logger.info(f"Model manifests (tier=all): {counts}")
        return counts

    if tier == "commodity":
        entries: list[dict] = []
        for ps in param_entries:
            level = level_by_model.get(ps["model_id"])
            if level not in _COMMODITY_LEVELS:
                continue
            entries.append(
                _build_entry(
                    ps["scenario_id"],
                    ps["model_id"],
                    {p["name"]: p["value"] for p in ps["parameters"]},
                )
            )
        counts = _save_tier_manifests(run_id, "models_commodity", entries)
        logger.info(f"Model manifests (tier=commodity): {counts}")
        return counts

    if tier == "commodity_downstream":
        return _generate_downstream_manifest(
            run_id=run_id,
            param_entries=param_entries,
            level_by_model=level_by_model,
            target_levels=_COMMODITY_DOWNSTREAM_LEVELS,
            manifest_name="models_commodity_downstream",
            audit_filename=f"{run_id}_commodity_downstream_overrides.json",
            log_label="commodity-downstream-dispatch",
        )

    # tier == "macro"
    return _generate_downstream_manifest(
        run_id=run_id,
        param_entries=param_entries,
        level_by_model=level_by_model,
        target_levels=_MACRO_LEVELS,
        manifest_name="models_macro",
        audit_filename=f"{run_id}_macro_overrides.json",
        log_label="macro-dispatch",
    )


def _generate_downstream_manifest(
    run_id: str,
    param_entries: list[dict],
    level_by_model: dict[str, AnalyticalLevel],
    target_levels: set[AnalyticalLevel],
    manifest_name: str,
    audit_filename: str,
    log_label: str,
) -> dict[str, int]:
    """Shared body for the commodity_downstream and macro dispatchers.

    Both operate on the same upstream-to-downstream merge mechanism
    (``src/pipeline/upstream_forwarding.py``) -- they just differ in
    which downstream tier they target and which audit file they write.
    Upstream outputs are pulled from ``data/outputs/`` and cover
    every prior phase, so the macro dispatcher naturally sees both
    commodity and commodity_downstream results.
    """
    mapping = load_mapping()
    upstream_results = _load_upstream_outputs(run_id, log_label)
    overrides_audit: dict[str, dict[str, list[dict]]] = {}

    entries: list[dict] = []
    for ps in param_entries:
        level = level_by_model.get(ps["model_id"])
        if level not in target_levels:
            continue

        scenario_id = ps["scenario_id"]
        model_id = ps["model_id"]
        llm_params = {p["name"]: p["value"] for p in ps["parameters"]}

        per_downstream = compute_downstream_inputs(
            scenario_id,
            upstream_results.get(scenario_id, []),
            mapping,
            target_models={model_id},
        )
        computed = per_downstream.get(model_id, [])
        merged, records = merge_into_params(model_id, llm_params, computed)
        record_dicts = [r.to_dict() for r in records]
        if record_dicts:
            overrides_audit.setdefault(scenario_id, {})[model_id] = record_dicts
            logger.info(
                "[%s] %s/%s: %d override(s) from upstream models",
                log_label,
                scenario_id,
                model_id,
                len(record_dicts),
            )
        entries.append(
            _build_entry(
                scenario_id,
                model_id,
                merged,
                upstream_overrides=record_dicts or None,
            )
        )

    if overrides_audit:
        audit_path = state_dir() / audit_filename
        with open(audit_path, "w") as f:
            json.dump(overrides_audit, f, indent=2, default=str)
        logger.info(f"[{log_label}] override audit written: {audit_path}")

    counts = _save_tier_manifests(run_id, manifest_name, entries)
    logger.info(f"Model manifests ({manifest_name}): {counts}")
    return counts


def _load_upstream_outputs(
    run_id: str, log_label: str = "upstream-dispatch"
) -> dict[str, list[dict]]:
    """Load every completed upstream model output, grouped by scenario.

    Reads ``data/outputs/<scenario>/<model>/output.json`` (written by
    ``run_model.py``) and the matching ``metadata.json`` to determine
    each run's status. SKIPPED / FAILED runs are propagated so
    ``compute_downstream_inputs`` can correctly fall back to the next
    upstream source.

    Returns outputs from ALL prior tiers (commodity AND
    commodity_downstream); the merge function is itself level-aware
    via the ``target_models`` filter, so callers don't need to scope
    the outputs to a particular upstream level.
    """
    outputs_root = get_project_root() / "data" / "outputs"
    out: dict[str, list[dict]] = {}
    if not outputs_root.exists():
        logger.warning(
            "[%s] No data/outputs/ directory; downstream shocks will "
            "fall back to LLM-extracted values",
            log_label,
        )
        return out

    for scenario_dir in outputs_root.iterdir():
        if not scenario_dir.is_dir():
            continue
        scenario_id = scenario_dir.name
        for model_dir in scenario_dir.iterdir():
            if not model_dir.is_dir():
                continue
            metadata_path = model_dir / "metadata.json"
            output_path = model_dir / "output.json"
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            status = (metadata.get("status") or "").lower()
            outputs_blob: dict = {}
            if output_path.exists():
                try:
                    with open(output_path) as f:
                        outputs_blob = json.load(f)
                except json.JSONDecodeError:
                    outputs_blob = {}
            out.setdefault(scenario_id, []).append({
                "scenario_id": scenario_id,
                "model_id": model_dir.name,
                "status": status,
                "outputs": outputs_blob if isinstance(outputs_blob, dict) else {},
            })

    total = sum(len(v) for v in out.values())
    logger.info(
        "[%s] Loaded %d upstream outputs across %d scenarios",
        log_label,
        total,
        len(out),
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SLURM array job manifests")
    parser.add_argument("stage", choices=["parameters", "models"],
                        help="Which stage to generate manifests for")
    parser.add_argument("--run-id", default=None,
                        help="Pipeline run ID (default: from env)")
    parser.add_argument(
        "--tier",
        choices=["all", "commodity", "commodity_downstream", "macro"],
        default="all",
        help=(
            "Stage 3 split. 'all' (legacy) emits one combined 'models' "
            "manifest. 'commodity' emits 'models_commodity*' covering "
            "combat + commodity tier adapters. 'commodity_downstream' "
            "emits 'models_commodity_downstream*' for adapters whose "
            "inputs are forwarded from upstream commodity outputs "
            "(today: SimRLFab, Argonne ABM). 'macro' emits "
            "'models_macro*' for the macro tier and runs the upstream-"
            "to-macro merge against completed commodity (and "
            "commodity_downstream) outputs."
        ),
    )
    args = parser.parse_args()

    run_id = args.run_id or get_run_id()

    if args.stage == "parameters":
        count = generate_parameter_manifest(run_id)
        print(f"MANIFEST_COUNT={count}")
        return

    counts = generate_model_manifest(run_id, tier=args.tier)
    if args.tier == "all":
        print(f"MANIFEST_COUNT_ALL={counts['models']}")
        print(f"MANIFEST_COUNT_CPU={counts['models_cpu']}")
        print(f"MANIFEST_COUNT_GPU={counts['models_gpu']}")
    elif args.tier == "commodity":
        print(f"MANIFEST_COUNT_COMMODITY={counts['models_commodity']}")
        print(f"MANIFEST_COUNT_COMMODITY_CPU={counts['models_commodity_cpu']}")
        print(f"MANIFEST_COUNT_COMMODITY_GPU={counts['models_commodity_gpu']}")
    elif args.tier == "commodity_downstream":
        print(
            "MANIFEST_COUNT_COMMODITY_DOWNSTREAM="
            f"{counts['models_commodity_downstream']}"
        )
        print(
            "MANIFEST_COUNT_COMMODITY_DOWNSTREAM_CPU="
            f"{counts['models_commodity_downstream_cpu']}"
        )
        print(
            "MANIFEST_COUNT_COMMODITY_DOWNSTREAM_GPU="
            f"{counts['models_commodity_downstream_gpu']}"
        )
    elif args.tier == "macro":
        print(f"MANIFEST_COUNT_MACRO={counts['models_macro']}")
        print(f"MANIFEST_COUNT_MACRO_CPU={counts['models_macro_cpu']}")
        print(f"MANIFEST_COUNT_MACRO_GPU={counts['models_macro_gpu']}")


if __name__ == "__main__":
    main()
