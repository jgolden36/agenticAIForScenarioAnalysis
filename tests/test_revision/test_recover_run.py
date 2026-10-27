"""Tests for scripts/revision/recover_run_from_outputs.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.revision.recover_run_from_outputs import recover_run, render_report_markdown


def _cell(root: Path, scenario: str, model: str, run_id: str, status: str, outputs=None, task_id=0, extra=None):
    d = root / scenario / model
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id, "scenario_id": scenario, "model_id": model,
        "status": status, "task_id": task_id, "node": "n1", "slurm_job_id": "1",
        "resource_class": "cpu", "started_at": "t0", "completed_at": "t1",
        "runtime_seconds": 0.1, "error_message": None if status == "completed" else "Not yet implemented: stub",
    }
    if extra:
        meta.update(extra)
    (d / "metadata.json").write_text(json.dumps(meta))
    if outputs is not None:
        (d / "output.json").write_text(json.dumps(outputs))


def test_recover_classifies_and_writes_records(tmp_path):
    outputs_root = tmp_path / "outputs"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    report_dir = tmp_path / "docs"

    # Already-present record (survived the collision) -> "present".
    (state_dir / "run-A_model_3.json").write_text(json.dumps({
        "scenario_id": "swift_contained", "model_id": "pycge", "task_id": 3, "status": "completed", "outputs": {"gdp_impact_pct": -0.157},
    }))
    # Overwritten in state, but data/outputs still carries run-A -> "recovered".
    _cell(outputs_root, "swift_contained", "poles_jrc", "run-A", "completed",
          outputs={"peak_price_change_pct": 54.79, "_execution_mode": "analytical_mvp"}, task_id=3,
          extra={"upstream_overrides": [{"name": "x"}]})
    # Skipped cell from this run -> recovered with status skipped, no outputs.
    _cell(outputs_root, "swift_contained", "ggm", "run-A", "skipped", task_id=5)
    # Later run overwrote this cell -> "stale_other_run".
    _cell(outputs_root, "swift_contained", "lngst", "run-B", "completed", outputs={"ttf_price": 24.9})

    report = recover_run(
        "run-A", outputs_root, state_dir, report_dir,
        scenario_ids=["swift_contained"],
        model_ids=["pycge", "poles_jrc", "ggm", "lngst", "nems"],
    )

    assert report["totals"] == {"present": 1, "recovered": 2, "stale_other_run": 1, "missing": 1}
    assert report["by_scenario"]["swift_contained"]["recovered"] == 2
    files = sorted(state_dir.glob("run-A_model_*.json"))
    assert len(files) == 3  # 1 present + 2 recovered
    recovered = [json.loads(p.read_text()) for p in files if "recovered" in p.name]
    by_model = {r["model_id"]: r for r in recovered}
    assert by_model["poles_jrc"]["status"] == "completed"
    assert by_model["poles_jrc"]["outputs"]["peak_price_change_pct"] == 54.79
    assert by_model["poles_jrc"]["implementation_mode"] == "analytical_reduction"
    assert by_model["poles_jrc"]["upstream_overrides"] == [{"name": "x"}]
    assert by_model["poles_jrc"]["recovered"] is True
    assert by_model["ggm"]["status"] == "skipped"
    assert "outputs" not in by_model["ggm"]
    # The recovered filename is tier-qualified so it never collides again.
    assert any("recovered_commodity_swift_contained_poles_jrc" in p.name for p in files)
    assert (report_dir / "recovery_run-A.json").exists()
    md = (report_dir / "recovery_run-A.md").read_text()
    assert "stale_other_run" in md and "lngst" in md and "nems" in md
    assert report["stale_cells"][0]["found_run_id"] == "run-B"


def test_recover_dry_run_writes_nothing(tmp_path):
    outputs_root = tmp_path / "outputs"
    state_dir = tmp_path / "state"
    _cell(outputs_root, "swift_contained", "poles_jrc", "run-A", "completed", outputs={"a": 1})
    report = recover_run("run-A", outputs_root, state_dir, tmp_path / "docs", dry_run=True,
                         scenario_ids=["swift_contained"], model_ids=["poles_jrc"])
    assert report["totals"] == {"recovered": 1}
    assert not state_dir.exists()
    assert not (tmp_path / "docs").exists()
    assert "Recovery report" in render_report_markdown(report)


def test_recover_overwrite_existing_replaces_record(tmp_path):
    outputs_root = tmp_path / "outputs"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "run-A_model_0.json").write_text(json.dumps({
        "scenario_id": "swift_contained", "model_id": "poles_jrc", "task_id": 0, "status": "failed",
    }))
    _cell(outputs_root, "swift_contained", "poles_jrc", "run-A", "completed", outputs={"a": 1})
    report = recover_run("run-A", outputs_root, state_dir, None, overwrite_existing=True,
                         scenario_ids=["swift_contained"], model_ids=["poles_jrc"])
    assert report["totals"] == {"recovered": 1}
    files = list(state_dir.glob("run-A_model_*.json"))
    assert len(files) == 1 and "recovered" in files[0].name
