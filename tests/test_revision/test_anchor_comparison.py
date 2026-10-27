"""Tests for scripts/revision/anchor_comparison.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.revision.anchor_comparison import find_anchors, run


def _write(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_find_anchors_requires_completion_in_every_scenario():
    rows = [
        {"scenario_id": "swift_contained", "model_id": "fed_oil", "status": "completed"},
        {"scenario_id": "prolonged_escalated", "model_id": "fed_oil", "status": "completed"},
        {"scenario_id": "swift_contained", "model_id": "poles_jrc", "status": "completed"},
        {"scenario_id": "prolonged_escalated", "model_id": "poles_jrc", "status": "skipped"},
    ]
    anchors, scenarios = find_anchors(rows)
    assert anchors == ["fed_oil"]
    assert scenarios == ["swift_contained", "prolonged_escalated"]


def test_run_writes_tables_and_figure(tmp_path):
    report = tmp_path / "run-Z"
    _write(report / "csv" / "model_status.csv", ["scenario_id", "model_id", "status"], [
        {"scenario_id": "swift_contained", "model_id": "fed_oil", "status": "completed"},
        {"scenario_id": "prolonged_escalated", "model_id": "fed_oil", "status": "completed"},
        {"scenario_id": "swift_contained", "model_id": "pycge", "status": "completed"},
        {"scenario_id": "prolonged_escalated", "model_id": "pycge", "status": "completed"},
        {"scenario_id": "swift_contained", "model_id": "lngst", "status": "completed"},
        {"scenario_id": "prolonged_escalated", "model_id": "lngst", "status": "skipped"},
    ])
    q_fields = ["scenario_id", "model_id", "output_key", "value_numeric", "value_raw", "is_numeric"]
    _write(report / "csv" / "quantitative_results.csv", q_fields, [
        {"scenario_id": "swift_contained", "model_id": "fed_oil", "output_key": "oil_price_change_pct", "value_numeric": "54.79", "value_raw": "54.79", "is_numeric": "true"},
        {"scenario_id": "prolonged_escalated", "model_id": "fed_oil", "output_key": "oil_price_change_pct", "value_numeric": "51.82", "value_raw": "51.82", "is_numeric": "true"},
        {"scenario_id": "swift_contained", "model_id": "pycge", "output_key": "gdp_impact_pct", "value_numeric": "-0.157", "value_raw": "-0.157", "is_numeric": "true"},
        {"scenario_id": "prolonged_escalated", "model_id": "pycge", "output_key": "gdp_impact_pct", "value_numeric": "-1.0575", "value_raw": "-1.0575", "is_numeric": "true"},
        {"scenario_id": "swift_contained", "model_id": "lngst", "output_key": "ttf_price", "value_numeric": "24.9", "value_raw": "24.9", "is_numeric": "true"},
        {"scenario_id": "swift_contained", "model_id": "pycge", "output_key": "_execution_mode", "value_numeric": "", "value_raw": "analytical_mvp", "is_numeric": "false"},
    ])
    out = tmp_path / "docs"
    summary = run(report, out)
    assert summary["anchors"] == ["fed_oil", "pycge"]
    assert summary["n_values"] == 4
    assert (out / "anchor_comparison_run-Z.csv").exists()
    md = (out / "anchor_comparison_run-Z.md").read_text()
    assert "## `oil_price_change_pct`" in md and "54.79" in md
    assert "| `lngst` |  | A |" in md  # non-anchor portfolio row
    tex = (out / "anchor_comparison_run-Z.tex").read_text()
    assert "\\label{tab:anchor_gdp_impact_pct}" in tex
    payload = json.loads((out / "anchor_comparison_run-Z.json").read_text())
    assert payload["portfolio"]["lngst"] == ["swift_contained"]
