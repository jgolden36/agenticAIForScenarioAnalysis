"""Tests for per-model output persistence in slurm/scripts/run_model.py.

Regression-tests the fix for "the code is not generating outputs in the
outputs directory": the SLURM model executor now writes
``data/outputs/<scenario>/<model>/{output.json, metadata.json}`` for
every COMPLETED / FAILED / SKIPPED task.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts import run_model
from src.common.types import ModelExecutionStatus


@pytest.fixture
def fake_project_root(tmp_path, monkeypatch):
    """Redirect run_model's project root to a tmp dir for the test."""
    monkeypatch.setattr(run_model, "get_project_root", lambda: tmp_path)
    return tmp_path


def _result(status: str, with_outputs: bool = False) -> dict:
    base = {
        "scenario_id": "swift_contained",
        "model_id": "osemosys",
        "task_id": 7,
        "status": status,
        "started_at": "2026-04-22T00:00:00+00:00",
        "completed_at": "2026-04-22T00:01:00+00:00",
        "runtime_seconds": 60.0,
        "node": "tesla1",
        "slurm_job_id": "22897",
        "resource_class": "cpu",
        "error_message": None,
    }
    if with_outputs:
        base["outputs"] = {"NewCapacity": [1.0, 2.0, 3.0], "TotalDiscountedCost": 42.5}
    if status == ModelExecutionStatus.FAILED.value:
        base["error_message"] = "Validation failed: 'x' must be positive"
    return base


def test_persist_completed_writes_output_and_metadata(fake_project_root):
    """COMPLETED runs write both output.json and metadata.json."""
    res = _result(ModelExecutionStatus.COMPLETED.value, with_outputs=True)
    run_model._persist_per_model_outputs("run-001", "swift_contained", "osemosys", res)

    target = fake_project_root / "data" / "outputs" / "swift_contained" / "osemosys"
    assert (target / "output.json").exists()
    assert (target / "metadata.json").exists()

    output = json.loads((target / "output.json").read_text())
    assert output["TotalDiscountedCost"] == 42.5

    meta = json.loads((target / "metadata.json").read_text())
    assert meta["status"] == ModelExecutionStatus.COMPLETED.value
    assert meta["run_id"] == "run-001"
    assert meta["model_id"] == "osemosys"
    assert meta["scenario_id"] == "swift_contained"


def test_persist_failed_writes_only_metadata(fake_project_root):
    """FAILED runs still write metadata.json so failures are auditable."""
    res = _result(ModelExecutionStatus.FAILED.value)
    run_model._persist_per_model_outputs("run-002", "swift_contained", "osemosys", res)

    target = fake_project_root / "data" / "outputs" / "swift_contained" / "osemosys"
    assert (target / "metadata.json").exists()
    assert not (target / "output.json").exists()

    meta = json.loads((target / "metadata.json").read_text())
    assert meta["status"] == ModelExecutionStatus.FAILED.value
    assert "must be positive" in meta["error_message"]


def test_persist_skipped_writes_only_metadata(fake_project_root):
    """SKIPPED (NotImplementedError) runs also surface metadata only."""
    res = _result(ModelExecutionStatus.SKIPPED.value)
    res["error_message"] = "Not yet implemented: vendor the upstream code"
    run_model._persist_per_model_outputs("run-003", "swift_contained", "world_helium_model", res)

    target = (
        fake_project_root
        / "data"
        / "outputs"
        / "swift_contained"
        / "world_helium_model"
    )
    assert (target / "metadata.json").exists()
    assert not (target / "output.json").exists()

    meta = json.loads((target / "metadata.json").read_text())
    assert meta["status"] == ModelExecutionStatus.SKIPPED.value
    assert "Not yet implemented" in meta["error_message"]


def test_persist_overwrites_previous_run(fake_project_root):
    """Re-running the same (scenario, model) overwrites the prior output."""
    res1 = _result(ModelExecutionStatus.COMPLETED.value, with_outputs=True)
    run_model._persist_per_model_outputs("run-A", "swift_contained", "osemosys", res1)

    res2 = _result(ModelExecutionStatus.COMPLETED.value, with_outputs=True)
    res2["outputs"] = {"NewCapacity": [9.9]}
    run_model._persist_per_model_outputs("run-B", "swift_contained", "osemosys", res2)

    target = fake_project_root / "data" / "outputs" / "swift_contained" / "osemosys"
    output = json.loads((target / "output.json").read_text())
    assert output == {"NewCapacity": [9.9]}
    meta = json.loads((target / "metadata.json").read_text())
    assert meta["run_id"] == "run-B"
