"""Tests for scripts/revision/build_all.py argument plumbing (step mains are stubbed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.revision.anchor_comparison as anchor_mod
import scripts.revision.checkpoint_report as checkpoint_mod
import scripts.revision.compare_runs as compare_mod
import scripts.revision.coverage_facts as facts_mod
import scripts.revision.effort_metrics as effort_mod
import scripts.revision.model_licenses as licenses_mod
import scripts.revision.replay_pycge_scenario_a as replay_mod
import scripts.revision.software_versions as versions_mod
import slurm.scripts.build_coverage_ledger as ledger_mod
import slurm.scripts.build_model_inventory as inventory_mod
import slurm.scripts.run_deterministic_baseline as baseline_mod
import slurm.scripts.run_fidelity_audit as fidelity_mod
from scripts.revision.build_all import STEP_NAMES, main, parse_skip

MODULES = {
    "coverage_ledger": ledger_mod, "model_inventory": inventory_mod, "fidelity_audit": fidelity_mod,
    "anchor_comparison": anchor_mod, "checkpoint_report": checkpoint_mod, "coverage_facts": facts_mod,
    "pycge_replay": replay_mod, "effort_metrics": effort_mod, "software_versions": versions_mod,
    "model_licenses": licenses_mod, "deterministic_baseline": baseline_mod, "compare_runs": compare_mod,
}


def _stub_all(monkeypatch, failing: set[str] = frozenset()) -> dict[str, list[list[str]]]:
    calls: dict[str, list[list[str]]] = {name: [] for name in MODULES}

    def make(name):
        def _main(argv):
            calls[name].append(list(argv))
            return 1 if name in failing else 0
        return _main

    for name, mod in MODULES.items():
        monkeypatch.setattr(mod, "main", make(name))
    return calls


def test_parse_skip_validates_names():
    assert parse_skip(None) == frozenset()
    assert parse_skip("pycge_replay, effort_metrics") == {"pycge_replay", "effort_metrics"}
    with pytest.raises(ValueError, match="bogus"):
        parse_skip("bogus")
    assert set(STEP_NAMES) >= {"coverage_ledger", "software_versions", "copy_baseline_summary"}


def test_forwards_runtime_dir_pip_freeze_and_skips(monkeypatch, tmp_path):
    calls = _stub_all(monkeypatch)
    out = tmp_path / "out"
    rc = main(["--run-id", "r1", "--report-dir", str(tmp_path / "rep"), "--state-dir", str(tmp_path / "state"),
               "--out-dir", str(out), "--runtime-dir", str(tmp_path / "logs"), "--pip-freeze", str(tmp_path / "pf.txt"),
               "--skip", "pycge_replay,effort_metrics"])
    assert rc == 0
    sv = calls["software_versions"][0]
    assert sv[sv.index("--runtime-dir") + 1] == str(tmp_path / "logs")
    assert sv[sv.index("--pip-freeze") + 1] == str(tmp_path / "pf.txt")
    assert calls["pycge_replay"] == [] and calls["effort_metrics"] == []
    # No state files -> the ledger falls back to the report directory.
    assert "--from-report-dir" in calls["coverage_ledger"][0]
    report = json.loads((out / "build_all_report.json").read_text())
    by_step = {r["step"]: r for r in report}
    assert by_step["pycge_replay"]["skipped"] is True and by_step["pycge_replay"]["ok"] is True
    assert "deterministic_baseline" not in by_step  # no --baseline given


def test_unknown_skip_name_is_a_usage_error(monkeypatch, tmp_path):
    _stub_all(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        main(["--run-id", "r1", "--report-dir", str(tmp_path), "--out-dir", str(tmp_path / "o"), "--skip", "bogus"])
    assert exc.value.code == 2


def test_failing_step_sets_exit_code(monkeypatch, tmp_path):
    _stub_all(monkeypatch, failing={"fidelity_audit"})
    out = tmp_path / "out"
    rc = main(["--run-id", "r1", "--report-dir", str(tmp_path), "--out-dir", str(out)])
    assert rc == 1
    report = {r["step"]: r for r in json.loads((out / "build_all_report.json").read_text())}
    assert report["fidelity_audit"]["ok"] is False and report["coverage_ledger"]["ok"] is True


def test_baseline_arguments_are_threaded(monkeypatch, tmp_path):
    calls = _stub_all(monkeypatch)
    state = tmp_path / "state"
    state.mkdir()
    (state / "r1_scenarios.json").write_text("{}")
    root = tmp_path / "bl_root"
    report_dir = tmp_path / "rep"
    rc = main(["--run-id", "r1", "--report-dir", str(report_dir), "--state-dir", str(state), "--out-dir", str(tmp_path / "out"),
               "--baseline", "configs/baselines/hormuz_2026_analyst.yaml", "--baseline-run-id", "bl_x",
               "--baseline-output-root", str(root)])
    assert rc == 0
    assert "--state-dir" in calls["coverage_ledger"][0]  # state files present
    bl = calls["deterministic_baseline"][0]
    assert bl[bl.index("--output-root") + 1] == str(root) and bl[bl.index("--run-id") + 1] == "bl_x"
    cmp = calls["compare_runs"][0]
    assert cmp[cmp.index("--a") + 1] == str(report_dir)
    assert cmp[cmp.index("--b") + 1] == str(root / "data" / "reports" / "bl_x")
    ledger_calls = calls["coverage_ledger"]
    assert any("bl_x" in c for c in ledger_calls[1]) and "--no-figure" in ledger_calls[1]
