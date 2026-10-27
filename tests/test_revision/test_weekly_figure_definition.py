"""Tests for the weekly-evolution filters and figure_definition.json."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.visualize_weekly_evolution import figure_definition, filter_long_form, main  # noqa: E402


def _week(root: Path, tag: str, rows: list[dict]) -> None:
    d = root / f"weekly_{tag}" / "csv"
    d.mkdir(parents=True)
    with open(d / "synthesis_outcomes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "time_horizon", "outcome_scope", "outcome_variable", "value", "source_model_id", "narrative_summary"])
        w.writeheader()
        w.writerows(rows)
    with open(d / "model_status.csv", "w", newline="") as f:
        f.write("scenario_id,model_id,status\nswift_contained,poles_jrc,completed\n")


def test_filter_and_definition():
    long_form = {"synthesis": [
        {"week": "20260301", "scenario_id": "swift_contained", "time_horizon": "short_run", "outcome_scope": "micro", "outcome_variable": "peak_price_change_pct", "value": 54.8, "source_model_id": "poles_jrc"},
        {"week": "20260301", "scenario_id": "prolonged_contained", "time_horizon": "short_run", "outcome_scope": "micro", "outcome_variable": "peak_price_change_pct", "value": 60.5, "source_model_id": "poles_jrc"},
        {"week": "20260301", "scenario_id": "swift_contained", "time_horizon": "short_run", "outcome_scope": "macro", "outcome_variable": "gdp_impact_pct", "value": -0.1, "source_model_id": "pycge"},
    ], "quantitative": [
        {"week": "20260301", "scenario_id": "swift_contained", "model_id": "aisdb", "output_key": "effective_fleet_capacity_loss_pct", "value": 40.0},
    ], "status": [], "flags": []}
    filtered = filter_long_form(long_form, variables="peak_price_change_pct", scenarios="swift_contained")
    assert len(filtered["synthesis"]) == 1 and filtered["quantitative"] == []
    d = figure_definition(filtered, [("20260301", Path("x"))], "peak_price_change_pct", "swift_contained")
    assert d["weeks_plotted"] == ["20260301"]
    series = d["panels"]["micro/short_run"]["series"]["peak_price_change_pct"]
    assert series == {"scenarios": ["swift_contained"], "weeks": ["20260301"], "source_models": ["poles_jrc"], "n_points": 1}
    assert "No averaging" in d["aggregation"]


def test_main_writes_figure_definition(tmp_path):
    reports = tmp_path / "reports"
    rows = [{"scenario_id": "swift_contained", "time_horizon": "short_run", "outcome_scope": "micro",
             "outcome_variable": "peak_price_change_pct", "value": "54.8", "source_model_id": "poles_jrc", "narrative_summary": ""}]
    _week(reports, "20260301", rows)
    _week(reports, "20260308", rows)
    out = tmp_path / "evo"
    rc = main(["--batch-id", "t", "--reports-root", str(reports), "--output-dir", str(out), "--scenarios", "swift_contained"])
    assert rc == 0
    d = json.loads((out / "figures" / "figure_definition.json").read_text())
    assert d["weeks_found"] == ["2026-03-01", "2026-03-08"]
    assert d["filters"]["scenarios"] == ["swift_contained"]
    assert "micro/short_run" in d["panels"]
