"""No-LLM APSIM-GTAP fill: inputs come from the run's own records."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from src.models.base import ModelOutput
from src.models.fertilizer.apsim_gtap import APSIMGTAPAdapter

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    sys.path.insert(0, str(ROOT / "slurm" / "scripts"))
    sys.path.insert(0, str(ROOT / "scripts" / "revision"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "revision" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fill = _load("run_apsim_gtap_fill")
merge_mod = _load("merge_refilled_cells")


class FakeAdapter(APSIMGTAPAdapter):
    def __init__(self):
        super().__init__(None)
        self.seen = []

    def execute(self, inputs):
        self.seen.append(inputs)
        return ModelOutput(model_id="apsim_gtap", outputs={"us_gdp_pct": -0.01, "converged": True},
                           metadata={"mode": "julia"})


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _state(tmp_path: Path) -> Path:
    sd = tmp_path / "state"
    sd.mkdir()
    run = "R1"
    _write(sd / f"{run}_params_0.json", {"scenario_id": "swift_contained", "model_id": "world_fertilizer", "status": "completed",
                                          "parameters": [{"name": "middle_east_production_loss_pct", "value": 50.0},
                                                         {"name": "disruption_duration_months", "value": 2.0}]})
    _write(sd / f"{run}_params_1.json", {"scenario_id": "swift_contained", "model_id": "poles_jrc", "status": "completed",
                                          "parameters": [{"name": "supply_loss_mbd", "value": 12.0},
                                                         {"name": "disruption_duration_months", "value": 1.5}]})
    # prolonged_contained has no poles_jrc record -> oil loss falls back to the baseline
    _write(sd / f"{run}_params_2.json", {"scenario_id": "prolonged_contained", "model_id": "world_fertilizer", "status": "completed",
                                          "parameters": [{"name": "middle_east_production_loss_pct", "value": 70.0},
                                                         {"name": "disruption_duration_months", "value": 4.0}]})
    _write(sd / f"{run}_model_commodity_0.json", {"scenario_id": "swift_contained", "model_id": "aisdb", "status": "completed",
                                                   "outputs": {"rerouting_cost_multiplier": 1.25}})
    _write(sd / f"{run}_model_commodity_1.json", {"scenario_id": "swift_contained", "model_id": "pycge", "status": "completed",
                                                   "outputs": {"gdp_impact_pct": -1.0}})
    return sd


def test_fill_takes_run_values_forwards_aisdb_and_flags_fallbacks(tmp_path):
    sd = _state(tmp_path)
    adapter = FakeAdapter()
    summary = fill.run_fill("R1", sd, "F1", tmp_path / "fills", tmp_path / "report", adapter=adapter)
    by = {c["scenario_id"]: c for c in summary["cells"]}
    a = by["swift_contained"]["inputs"]
    assert a["middle_east_fertilizer_production_loss_pct"] == 50.0
    assert a["gulf_oil_supply_loss_mbd"] == 12.0
    assert a["disruption_duration_months"] == 1.5  # poles_jrc before world_fertilizer
    assert a["trade_cost_multiplier"] == 1.25      # forwarded from aisdb
    b = by["prolonged_contained"]["inputs"]
    assert b["gulf_oil_supply_loss_mbd"] == 15.0   # analyst baseline
    assert b["trade_cost_multiplier"] == 1.5       # no aisdb output -> baseline
    kinds = {(p["scenario_id"], p["input"]): p["kind"] for p in summary["inputs_provenance"]}
    assert kinds[("swift_contained", "trade_cost_multiplier")] == "forwarded_model_output"
    assert kinds[("prolonged_contained", "gulf_oil_supply_loss_mbd")] == "analyst_baseline_fallback"
    rec = json.loads((tmp_path / "fills" / "F1_model_fill_swift_contained_apsim_gtap.json").read_text())
    assert rec["status"] == "completed" and rec["implementation_mode"] == "full_upstream"
    assert rec["upstream_overrides"][0]["source_model_id"] == "aisdb"
    assert (tmp_path / "report" / "apsim_gtap_fill.md").exists()


def test_merge_into_copy_leaves_source_untouched(tmp_path):
    sd = _state(tmp_path)
    before = sorted(p.name for p in sd.iterdir())
    fill.run_fill("R1", sd, "F1", tmp_path / "fills", tmp_path / "report", adapter=FakeAdapter())
    result = merge_mod.merge("R1", "F1", sd, tmp_path / "merged", fill_state_dir=tmp_path / "fills", note="added later")
    assert sorted(p.name for p in sd.iterdir()) == before
    assert len(result["added"]) == 2
    added = json.loads((tmp_path / "merged" / "R1_model_refilled_swift_contained_apsim_gtap.json").read_text())
    assert added["refilled_note"] == "added later"


def test_dry_run_executes_nothing(tmp_path):
    sd = _state(tmp_path)
    summary = fill.run_fill("R1", sd, "F1", tmp_path / "fills", tmp_path / "report", dry_run=True)
    assert {c["status"] for c in summary["cells"]} == {"dry_run"}
    assert not list((tmp_path / "fills").glob("*.json"))
