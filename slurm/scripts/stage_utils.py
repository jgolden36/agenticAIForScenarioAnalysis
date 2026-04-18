"""Shared utilities for SLURM stage scripts.

Handles state persistence, manifest I/O, logging, and cluster
configuration for the pipeline stages running as SLURM jobs.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("hormuz.slurm")


def get_project_root() -> Path:
    """Resolve project root from SLURM_SUBMIT_DIR or cwd."""
    return Path(os.environ.get("SLURM_SUBMIT_DIR", Path(__file__).resolve().parents[2]))


def load_cluster_config(path: Path | None = None) -> dict:
    """Load cluster.yaml configuration."""
    if path is None:
        path = get_project_root() / "slurm" / "config" / "cluster.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def state_dir() -> Path:
    """Return the pipeline state directory, creating it if necessary."""
    root = get_project_root()
    d = root / "data" / "pipeline_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def manifests_dir() -> Path:
    """Return the manifests directory, creating it if necessary."""
    d = state_dir() / "manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_state(run_id: str, stage: str, data: Any) -> Path:
    """Persist stage output as JSON for downstream SLURM jobs to consume.

    Files are named {run_id}_{stage}.json so each stage can find
    its predecessors' outputs.
    """
    out = state_dir() / f"{run_id}_{stage}.json"
    with open(out, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"State saved: {out}")
    return out


def load_state(run_id: str, stage: str) -> Any:
    """Load persisted state from a previous stage."""
    path = state_dir() / f"{run_id}_{stage}.json"
    if not path.exists():
        raise FileNotFoundError(f"No state file for run={run_id}, stage={stage}: {path}")
    with open(path) as f:
        return json.load(f)


def save_manifest(run_id: str, name: str, entries: list[dict]) -> Path:
    """Write a manifest file used to drive SLURM array jobs.

    Each entry becomes one line in the manifest. The SLURM_ARRAY_TASK_ID
    indexes into this list to determine what work a given array element does.
    """
    out = manifests_dir() / f"{run_id}_{name}.json"
    with open(out, "w") as f:
        json.dump(entries, f, indent=2, default=str)
    logger.info(f"Manifest saved: {out} ({len(entries)} entries)")
    return out


def load_manifest(run_id: str, name: str) -> list[dict]:
    """Load a manifest file."""
    path = manifests_dir() / f"{run_id}_{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"No manifest for run={run_id}, name={name}: {path}")
    with open(path) as f:
        return json.load(f)


def get_array_task() -> dict:
    """Read the SLURM array task context from environment variables."""
    return {
        "task_id": int(os.environ.get("SLURM_ARRAY_TASK_ID", 0)),
        "task_count": int(os.environ.get("SLURM_ARRAY_TASK_COUNT", 1)),
        "job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "array_job_id": os.environ.get("SLURM_ARRAY_JOB_ID", "local"),
        "node": os.environ.get("SLURMD_NODENAME", "local"),
    }


def get_run_id() -> str:
    """Get the pipeline run ID from environment or generate one."""
    return os.environ.get("HORMUZ_RUN_ID", datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))


def get_pipeline_config_path() -> Path:
    """Resolve the pipeline config YAML to use."""
    env = os.environ.get("HORMUZ_CONFIG")
    if env:
        return Path(env)
    cluster_cfg = get_project_root() / "slurm" / "config" / "pipeline_cluster.yaml"
    if cluster_cfg.exists():
        return cluster_cfg
    return get_project_root() / "configs" / "model_configs" / "default.yaml"


def log_slurm_context() -> None:
    """Log SLURM job context for diagnostics."""
    fields = [
        "SLURM_JOB_ID", "SLURM_JOB_NAME", "SLURM_ARRAY_JOB_ID",
        "SLURM_ARRAY_TASK_ID", "SLURMD_NODENAME", "SLURM_GPUS_ON_NODE",
        "SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE",
    ]
    ctx = {k: os.environ.get(k, "N/A") for k in fields}
    logger.info(f"SLURM context: {json.dumps(ctx, indent=2)}")


def auto_approve_enabled() -> bool:
    """Check whether HITL checkpoints should be auto-approved."""
    if os.environ.get("HORMUZ_AUTO_APPROVE", "").lower() in ("1", "true", "yes"):
        return True
    try:
        cfg = load_cluster_config()
        return cfg.get("pipeline_overrides", {}).get("auto_approve_checkpoints", False)
    except Exception:
        return False
