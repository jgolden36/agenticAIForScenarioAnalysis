"""Tests for the Stage 3 dispatcher's upstream-output loading.

Regression tests for two revision findings on run 20260504_222710:

* ``_load_upstream_outputs`` read every ``data/outputs/<scenario>/<model>/``
  entry regardless of which run wrote it, so a downstream tier could
  inherit a stale upstream value whenever the current run's upstream
  model was skipped or failed.
* Parameter-extraction records with ``status: failed`` must not be
  dispatched to ``run_model.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts import dispatch_models  # noqa: E402


def _write_cell(root: Path, scenario: str, model: str, run_id: str, status="completed", outputs=None):
    d = root / "data" / "outputs" / scenario / model
    d.mkdir(parents=True, exist_ok=True)
    (d / "metadata.json").write_text(json.dumps({
        "run_id": run_id,
        "scenario_id": scenario,
        "model_id": model,
        "status": status,
    }))
    if outputs is not None:
        (d / "output.json").write_text(json.dumps(outputs))


@pytest.fixture
def outputs_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch_models, "get_project_root", lambda: tmp_path)
    _write_cell(tmp_path, "swift_contained", "poles_jrc", "run-A", outputs={"peak_price_change_pct": 54.79})
    _write_cell(tmp_path, "swift_contained", "lngst", "run-OLD", outputs={"ttf_price": 24.9})
    _write_cell(tmp_path, "swift_contained", "ggm", "run-A", status="skipped")
    return tmp_path


def test_load_upstream_outputs_filters_other_run_ids(outputs_tree):
    out = dispatch_models._load_upstream_outputs("run-A", "test")
    models = {e["model_id"] for e in out["swift_contained"]}
    assert models == {"poles_jrc", "ggm"}
    assert all(e["run_id"] == "run-A" for e in out["swift_contained"])
    stale = out["_stale_upstream_ignored"]
    assert len(stale) == 1
    assert "lngst" in stale[0]["entry"]
    assert "run-OLD" in stale[0]["entry"]


def test_load_upstream_outputs_allow_stale_restores_old_behaviour(outputs_tree):
    out = dispatch_models._load_upstream_outputs("run-A", "test", allow_stale=True)
    models = {e["model_id"] for e in out["swift_contained"]}
    assert models == {"poles_jrc", "lngst", "ggm"}
    assert "_stale_upstream_ignored" not in out


def test_load_upstream_outputs_missing_root_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch_models, "get_project_root", lambda: tmp_path)
    assert dispatch_models._load_upstream_outputs("run-A", "test") == {}


def test_load_param_entries_skips_failed_records(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch_models, "state_dir", lambda: tmp_path)
    (tmp_path / "run-A_params_0.json").write_text(json.dumps({
        "scenario_id": "swift_contained", "model_id": "poles_jrc",
        "status": "completed",
        "parameters": [{"name": "supply_loss_mbd", "value": 5.0}],
    }))
    (tmp_path / "run-A_params_1.json").write_text(json.dumps({
        "scenario_id": "swift_contained", "model_id": "cwatm",
        "status": "failed", "error_message": "LengthFinishReasonError: ...",
        "parameters": [],
    }))
    # Legacy record without a status key is treated as completed.
    (tmp_path / "run-A_params_2.json").write_text(json.dumps({
        "scenario_id": "swift_contained", "model_id": "mam",
        "parameters": [{"name": "oil_price_path", "value": [80.0]}],
    }))
    entries = dispatch_models._load_param_entries("run-A")
    assert {e["model_id"] for e in entries} == {"poles_jrc", "mam"}
