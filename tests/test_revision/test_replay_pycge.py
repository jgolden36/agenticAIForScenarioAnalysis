"""Tests for scripts/revision/replay_pycge_scenario_a.py."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import pytest

from scripts.revision.replay_pycge_scenario_a import (
    fraction_percent_hypothesis,
    recorded_inputs,
    render_markdown,
    replay_at_commit,
    replay_working_tree,
    run,
)

REPO = Path(__file__).resolve().parents[2]


def _report(root: Path, rows: list[tuple[str, str, str, str, str]]) -> Path:
    d = root / "rep" / "csv"
    d.mkdir(parents=True)
    with open(d / "quantitative_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario_id", "model_id", "output_key", "value_numeric", "value_raw", "is_numeric"])
        for sid, mid, key, num, raw in rows:
            w.writerow([sid, mid, key, num, raw, "true" if num else "false"])
    return root / "rep"


def _rows():
    return [
        ("swift_contained", "pycge", "_applied_shocks.oil", "54.79", "54.79"),
        ("swift_contained", "pycge", "_applied_shocks.lng", "25.0", "25.0"),
        ("swift_contained", "pycge", "_applied_shocks.fertilizer", "0.0", "0.0"),
        ("swift_contained", "pycge", "_inputs.duration_months", "0.4166666666666667", "0.4166666666666667"),
        ("swift_contained", "pycge", "_inputs.regime", "", "short_run"),
        ("swift_contained", "pycge", "gdp_impact_pct", "-0.157", "-0.157"),
    ]


def test_recorded_inputs(tmp_path):
    rep = _report(tmp_path, _rows())
    inp = recorded_inputs(rep, "swift_contained")
    assert inp["shocks"] == {"oil": 54.79, "lng": 25.0, "fertilizer": 0.0}
    assert inp["duration_months"] == pytest.approx(0.4166666666666667) and inp["regime"] == "short_run"
    assert inp["recorded_outputs"]["gdp_impact_pct"] == -0.157
    with pytest.raises(ValueError):
        recorded_inputs(rep, "prolonged_contained")


def test_working_tree_replay_matches_recorded_run(tmp_path):
    rep = _report(tmp_path, _rows())
    inp = recorded_inputs(rep, "swift_contained")
    wt = replay_working_tree(inp)
    assert wt["commit"] == "working_tree"
    assert wt["outputs"]["gdp_impact_pct"] == pytest.approx(-0.157, abs=1e-3)
    h = fraction_percent_hypothesis(wt["outputs"]["gdp_impact_pct"], -15.7)
    assert h["reproduces_manuscript_value"] is True and h["ratio_manuscript_over_kernel"] == pytest.approx(100.0, rel=1e-2)
    assert fraction_percent_hypothesis(-0.157, -3.0)["reproduces_manuscript_value"] is False


def _git_ok() -> bool:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).returncode == 0
    except OSError:
        return False


@pytest.mark.skipif(not _git_ok(), reason="git not available")
def test_replay_at_head_commit_via_worktree(tmp_path):
    rep = _report(tmp_path, _rows())
    inp = recorded_inputs(rep, "swift_contained")
    res = replay_at_commit(REPO, "HEAD", inp)
    assert res.get("error") is None, res
    assert res["sha"] and res["date"] and res["outputs"]["gdp_impact_pct"] == pytest.approx(-0.157, abs=1e-3)
    worktrees = subprocess.run(["git", "worktree", "list"], cwd=REPO, capture_output=True, text=True).stdout
    assert "pycge_replay_" not in worktrees  # temporary worktree removed
    bad = replay_at_commit(REPO, "0000000", inp)
    assert bad.get("error")


@pytest.mark.skipif(not _git_ok(), reason="git not available")
def test_run_and_render(tmp_path):
    rep = _report(tmp_path, _rows())
    result = run(REPO, rep, "swift_contained", ["HEAD"], -15.7)
    assert [r["commit"] for r in result["code_states"]] == ["HEAD", "working_tree"]
    assert all(r["matches_recorded_run"] for r in result["code_states"])
    assert "fraction-vs-percent rescaling hypothesis supported" in result["conclusion"]
    md = render_markdown(result)
    assert "| working_tree |" in md and "-15.7" in md
