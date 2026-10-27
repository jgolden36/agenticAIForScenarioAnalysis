"""Tests for scripts/revision/compare_runs.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.revision.compare_runs import classify, compare, main, resolve_report_dir


def _report(root: Path, name: str, quant: list[tuple[str, str, str, float | str, bool]], status: list[tuple[str, str, str]]) -> Path:
    d = root / name / "csv"
    d.mkdir(parents=True)
    with open(d / "quantitative_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario_id", "model_id", "output_key", "value_numeric", "value_raw", "is_numeric"])
        for sid, mid, key, val, numeric in quant:
            w.writerow([sid, mid, key, val if numeric else "", val, "true" if numeric else "false"])
    with open(d / "model_status.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scenario_id", "model_id", "status"])
        w.writerows(status)
    return root / name


def test_classify():
    assert classify(1.0, 1.0, 0.5) == "identical"
    assert classify(100.0, 100.3, 0.5) == "within_tolerance"
    assert classify(100.0, 120.0, 0.5) == "differs"
    assert classify(None, 1.0, 0.5) == "only_in_b" and classify(1.0, None, 0.5) == "only_in_a"
    assert classify(0.0, 0.0, 0.5) == "identical"


def test_compare_groups_inputs_and_flags_determinism(tmp_path):
    a = _report(tmp_path, "run_a", [
        ("s", "poles_jrc", "_inputs.supply_loss_mbd", 14.0, True),
        ("s", "poles_jrc", "peak_price_change_pct", 54.8, True),
        ("s", "pycge", "_applied_shocks.oil", 54.79, True),
        ("s", "pycge", "gdp_impact_pct", -0.157, True),
        ("s", "pycge", "regime", "short_run", False),
        ("s", "fed_oil", "peak_gdp_impact_pct", -1.0, True),
    ], [("s", "poles_jrc", "completed"), ("s", "pycge", "completed"), ("s", "fed_oil", "completed"), ("s", "ggm", "skipped")])
    b = _report(tmp_path, "run_b", [
        ("s", "poles_jrc", "_inputs.supply_loss_mbd", 14.0, True),
        ("s", "poles_jrc", "peak_price_change_pct", 54.8, True),
        ("s", "pycge", "_applied_shocks.oil", 50.0, True),
        ("s", "pycge", "gdp_impact_pct", -0.14, True),
        ("s", "fed_oil", "peak_gdp_impact_pct", -1.0, True),
        ("s", "fed_oil", "extra_key", 2.0, True),
    ], [("s", "poles_jrc", "completed"), ("s", "pycge", "completed"), ("s", "fed_oil", "completed"), ("s", "ggm", "failed")])
    result = compare(a, b, label_a="A", label_b="B")
    s = result["summary"]
    assert s["output_keys"] == 4 and s["input_keys"] == 2
    assert s["output_categories"] == {"identical": 2, "differs": 1, "only_in_b": 1}
    assert s["input_categories"] == {"identical": 1, "differs": 1}
    assert s["cells_with_identical_inputs"] == 1 and s["determinism_violations"] == []
    assert s["status_pairs"] == {"completed->completed": 3, "skipped->failed": 1}
    cells = {(c["scenario_id"], c["model_id"]): c for c in result["cells"]}
    assert cells[("s", "poles_jrc")]["inputs_identical"] is True and cells[("s", "poles_jrc")]["outputs_identical"] == 1
    assert cells[("s", "pycge")]["inputs_identical"] is False and cells[("s", "pycge")]["outputs_differs"] == 1
    assert cells[("s", "fed_oil")]["inputs_identical"] is None
    assert s["largest_output_differences"][0]["output_key"] == "gdp_impact_pct"


def test_determinism_violation_detected(tmp_path):
    a = _report(tmp_path, "a", [("s", "m", "_inputs.x", 1.0, True), ("s", "m", "y", 2.0, True)], [("s", "m", "completed")])
    b = _report(tmp_path, "b", [("s", "m", "_inputs.x", 1.0, True), ("s", "m", "y", 3.0, True)], [("s", "m", "completed")])
    assert compare(a, b, label_a="a", label_b="b")["summary"]["determinism_violations"] == [("s", "m")]


def test_main_writes_files_and_resolves_run_ids(tmp_path):
    repo = tmp_path / "repo"
    _report(repo / "data" / "reports", "r1", [("s", "m", "y", 2.0, True)], [("s", "m", "completed")])
    _report(repo / "data", "r2", [("s", "m", "y", 2.5, True)], [("s", "m", "completed")])
    assert resolve_report_dir("r1", repo) == repo / "data" / "reports" / "r1"
    assert resolve_report_dir("r2", repo) == repo / "data" / "r2"
    out = tmp_path / "out"
    rc = main(["--a", str(repo / "data" / "reports" / "r1"), "--b", str(repo / "data" / "r2"), "--label-a", "x", "--label-b", "y", "--out-dir", str(out)])
    assert rc == 0
    assert (out / "compare_x_vs_y.md").exists() and (out / "compare_x_vs_y_cells.csv").exists()
    summary = json.loads((out / "compare_x_vs_y.json").read_text())
    assert summary["output_categories"] == {"differs": 1}
