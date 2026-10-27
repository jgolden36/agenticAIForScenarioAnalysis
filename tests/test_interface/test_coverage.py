"""Tests for the coverage ledger (src/interface/coverage.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.common.types import AnalyticalLevel
from src.interface.coverage import (
    CELL_CODES,
    build_ledger,
    classify_execution,
    classify_not_dispatched,
    ledger_from_report_csv,
    ledger_from_state_dir,
    render_latex,
    render_markdown,
    summarize,
    write_all,
)


# Error messages observed in run 20260504_222710 / 20260504_032106.
@pytest.mark.parametrize("status,msg,expected", [
    ("completed", None, "completed"),
    ("failed", "Validation failed: Provide either 'price_schedule' (12 rows) or ...", "validation_failed"),
    ("failed", "Input validation failed: x", "validation_failed"),
    ("failed", "Execution timed out after 3600s", "timeout"),
    ("failed", "JVMNotFoundException: No JVM shared library file (libjvm.so) found.", "runtime_or_license_missing"),
    ("failed", "FileNotFoundError: Dynare .mod file not found: Models/Oil/...", "missing_data_or_binary"),
    ("failed", "ValidationError: {\"errors\": {\"Z\": [\"Not a valid list.\"]}}", "runtime_error"),
    ("failed", "Model foo not found in registry", "not_registered"),
    ("skipped", "Not yet implemented: TEMOA baseline DB not found: Models/Energy/TEMOA/data_files/utopia.sqlite. Vendor a baseline SQLite or override TEMOAConfig.baseline_db_path.", "missing_data_or_binary"),
    ("skipped", "Not yet implemented: MIRAGRODEP requires the 'gams' executable on PATH (GAMS + a CONOPT/PATH licence).", "runtime_or_license_missing"),
    ("skipped", "Not yet implemented: OSeMOSYS baseline_data_dir not found: data/osemosys/baseline. Provide a baseline dataset.", "missing_data_or_binary"),
    ("skipped", "Not yet implemented: GTAPAdapter.execute is not yet implemented. Real integration requires: (1) a licensed GTAP database", "stub"),
    ("skipped", "Not yet implemented: GGMAdapter.execute() requires a GGMConfig. Prerequisites: 1. GAMS installation", "missing_config"),
    ("skipped", "Not yet implemented: MPSGEJLAdapter.execute() is not yet implemented. Provide a JuliaConfig", "missing_config"),
    ("skipped", "Not yet implemented: MAgPIE source tree not found. Pass magpie_root to the adapter constructor", "missing_data_or_binary"),
    ("skipped", "Not yet implemented: AIS_project adapter is a stub. Real implementation requires", "stub"),
    ("skipped", "Not yet implemented: WEAPAdapter.execute() requires a WEAPConfig. To integrate WEAP-MENA", "missing_config"),
    ("skipped", "Not yet implemented: FedOilAdapter.execute() is not yet implemented. Integration requires:", "stub"),
    ("skipped", "Model not yet implemented: something unusual", "not_implemented_other"),
])
def test_classify_execution(status, msg, expected):
    assert classify_execution(status, msg) == expected


def test_classify_not_dispatched():
    assert classify_not_dispatched("failed", True, None) == ("not_dispatched", "parameter_extraction_failed")
    assert classify_not_dispatched("missing", None, None) == ("not_dispatched", "parameter_extraction_missing")
    assert classify_not_dispatched("completed", False, None) == ("not_dispatched", "not_in_manifest")
    assert classify_not_dispatched("completed", True, "completed") == ("no_record", "record_overwritten")
    assert classify_not_dispatched("completed", None, None) == ("no_record", "record_missing")


def _ledger_fixture():
    scenarios = ["swift_contained", "prolonged_escalated"]
    models = ["poles_jrc", "fed_oil", "cwatm", "ggm"]
    levels = {"poles_jrc": AnalyticalLevel.COMMODITY, "fed_oil": AnalyticalLevel.SHORT_RUN_MACRO,
              "cwatm": AnalyticalLevel.COMMODITY, "ggm": AnalyticalLevel.COMMODITY}
    systems = {"poles_jrc": "oil", "fed_oil": "oil", "cwatm": "water", "ggm": "lng"}
    params = {
        ("swift_contained", "poles_jrc"): {"status": "completed", "parameters": [{"name": "x", "value": 1}]},
        ("swift_contained", "fed_oil"): {"status": "completed", "parameters": [{"name": "x", "value": 1}]},
        ("swift_contained", "cwatm"): {"status": "failed", "error_message": "LengthFinishReasonError", "parameters": []},
        ("swift_contained", "ggm"): {"status": "completed", "parameters": [{"name": "x", "value": 1}]},
        ("prolonged_escalated", "poles_jrc"): {"parameters": [{"name": "x", "value": 1}]},  # legacy record
        ("prolonged_escalated", "fed_oil"): {"parameters": [{"name": "x", "value": 1}]},
        ("prolonged_escalated", "ggm"): {"parameters": [{"name": "x", "value": 1}]},
        # cwatm in D: no params record at all.
    }
    model_records = {
        ("swift_contained", "poles_jrc"): {"status": "completed", "task_id": 61, "manifest_name": "models_commodity",
                                            "outputs": {"peak_price_change_pct": 54.79, "_execution_mode": "analytical_mvp"}},
        ("swift_contained", "fed_oil"): {"status": "completed", "task_id": 2, "implementation_mode": "analytical_reduction",
                                          "outputs": {"_upstream_overrides": [{"source_model_id": "poles_jrc", "name": "oil_price_change_pct",
                                                                               "source_field": "peak_price_change_pct", "llm_value": 0.0, "computed_value": 54.79}]}},
        ("swift_contained", "ggm"): {"status": "skipped", "error_message": "Not yet implemented: GGMAdapter.execute() requires a GGMConfig."},
        # D: poles_jrc record overwritten (outputs index says it ran); fed_oil completed citing poles_jrc -> stale.
        ("prolonged_escalated", "fed_oil"): {"status": "completed", "task_id": 7, "implementation_mode": "analytical_reduction",
                                              "outputs": {"_upstream_overrides": [{"source_model_id": "poles_jrc", "name": "oil_price_change_pct"}]}},
        ("prolonged_escalated", "ggm"): {"status": "failed", "error_message": "JVMNotFoundException: no JVM"},
    }
    manifest = {("swift_contained", "poles_jrc"), ("swift_contained", "fed_oil"), ("swift_contained", "ggm"),
                ("prolonged_escalated", "poles_jrc"), ("prolonged_escalated", "fed_oil"), ("prolonged_escalated", "ggm")}
    outputs_index = {("prolonged_escalated", "poles_jrc"): "completed"}
    return build_ledger(scenarios, models, param_records=params, model_records=model_records,
                        manifest_cells=manifest, outputs_status_index=outputs_index,
                        systems_by_model=systems, levels_by_model=levels)


def test_build_ledger_classifies_every_cell():
    cells = _ledger_fixture()
    by = {(c.scenario_id, c.model_id): c for c in cells}
    assert len(cells) == 8

    c = by[("swift_contained", "poles_jrc")]
    assert c.exec_status == "completed" and c.implementation_mode == "analytical_reduction"
    assert c.implementation_mode_evidence == "output_marker"
    assert c.cell_code == "R" and c.tier == "commodity"

    c = by[("swift_contained", "fed_oil")]
    assert c.implementation_mode_evidence == "recorded"
    assert c.upstream_sources[0].source_model_id == "poles_jrc"
    assert c.upstream_sources[0].source_ran_in_run is True
    assert c.stale_upstream is False

    c = by[("swift_contained", "cwatm")]
    assert (c.exec_status, c.skip_class) == ("not_dispatched", "parameter_extraction_failed")
    assert c.param_error == "LengthFinishReasonError"
    assert c.cell_code == CELL_CODES["parameter_extraction_failed"]

    c = by[("swift_contained", "ggm")]
    assert (c.exec_status, c.skip_class) == ("skipped", "missing_config")

    c = by[("prolonged_escalated", "poles_jrc")]
    assert (c.exec_status, c.skip_class) == ("no_record", "record_overwritten")
    assert c.outputs_status_this_run == "completed"

    c = by[("prolonged_escalated", "fed_oil")]
    assert c.stale_upstream is True
    assert c.upstream_sources[0].source_ran_in_run is False

    c = by[("prolonged_escalated", "cwatm")]
    assert (c.exec_status, c.skip_class) == ("not_dispatched", "parameter_extraction_missing")

    c = by[("prolonged_escalated", "ggm")]
    assert c.skip_class == "runtime_or_license_missing"


def test_summary_and_renderers(tmp_path):
    cells = _ledger_fixture()
    s = summarize(cells)
    assert s["grid_cells"] == 8 and s["completed_cells"] == 3
    assert s["all_scenario_models"] == ["fed_oil"]
    assert s["by_scenario"]["prolonged_escalated"]["by_skip_class"]["record_overwritten"] == 1
    assert s["stale_upstream_cells"] == [{"scenario_id": "prolonged_escalated", "model_id": "fed_oil", "sources_not_run": ["poles_jrc"]}]

    assert s["scenarios"] == ["swift_contained", "prolonged_escalated"]  # canonical A..E order
    md = render_markdown(cells, "run-X", s)
    assert "| model | system | A | D |" in md
    assert "| `fed_oil` | oil | `R` | `R` |" in md
    assert "record_overwritten: 1" in md
    tex = render_latex(cells, "run-X")
    assert "\\begin{tabular}{llcc}" in tex and "\\texttt{fed\\_oil} & oil & R & R" in tex

    paths = write_all(cells, "run-X", tmp_path)
    assert all(p.exists() for p in paths.values())
    rows = list(csv.DictReader(open(paths["csv"])))
    assert len(rows) == 8
    d_fed = next(r for r in rows if r["scenario_id"] == "prolonged_escalated" and r["model_id"] == "fed_oil")
    assert d_fed["upstream_sources"] == "poles_jrc(not run)" and d_fed["stale_upstream"] == "True"
    payload = json.loads(paths["json"].read_text())
    assert payload["summary"]["completed_cells"] == 3


def test_ledger_from_state_dir(tmp_path):
    sd = tmp_path / "state"
    (sd / "manifests").mkdir(parents=True)
    (sd / "run-S_scenarios.json").write_text(json.dumps({"scenario_narratives": [{"scenario_id": "swift_contained"}]}))
    (sd / "run-S_params_0.json").write_text(json.dumps({"scenario_id": "swift_contained", "model_id": "poles_jrc", "status": "completed", "parameters": [{"name": "x", "value": 1}]}))
    (sd / "run-S_params_1.json").write_text(json.dumps({"scenario_id": "swift_contained", "model_id": "fed_oil", "status": "completed", "parameters": [{"name": "x", "value": 1}]}))
    (sd / "manifests" / "run-S_models_commodity.json").write_text(json.dumps([{"scenario_id": "swift_contained", "model_id": "poles_jrc"}]))
    (sd / "manifests" / "run-S_models_macro.json").write_text(json.dumps([{"scenario_id": "swift_contained", "model_id": "fed_oil"}]))
    (sd / "run-S_model_macro_0.json").write_text(json.dumps({"scenario_id": "swift_contained", "model_id": "fed_oil", "status": "completed", "outputs": {}, "metadata": {"mode": "analytical_mvp"}, "implementation_mode": "analytical_reduction"}))
    outputs = tmp_path / "outputs" / "swift_contained" / "poles_jrc"
    outputs.mkdir(parents=True)
    (outputs / "metadata.json").write_text(json.dumps({"run_id": "run-S", "status": "completed"}))

    cells = ledger_from_state_dir("run-S", sd, tmp_path / "outputs", model_ids=["poles_jrc", "fed_oil", "ggm"])
    by = {c.model_id: c for c in cells}
    assert by["fed_oil"].exec_status == "completed" and by["fed_oil"].implementation_mode == "analytical_reduction"
    assert by["poles_jrc"].skip_class == "record_overwritten"
    assert by["ggm"].skip_class == "parameter_extraction_missing"


def test_ledger_from_report_csv(tmp_path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    with open(csv_dir / "model_status.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_id", "status", "task_id", "error_message"])
        w.writeheader()
        w.writerow({"scenario_id": "swift_contained", "model_id": "fed_oil", "status": "completed", "task_id": 2, "error_message": ""})
        w.writerow({"scenario_id": "swift_contained", "model_id": "ggm", "status": "skipped", "task_id": 70,
                    "error_message": "Not yet implemented: GGMAdapter.execute() requires a GGMConfig."})
    with open(csv_dir / "consistency_flags.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_a_id", "model_b_id", "variable", "value_a", "value_b", "tolerance_pct", "deviation_pct", "message"])
        w.writeheader()
        w.writerow({"scenario_id": "swift_contained", "model_a_id": "fed_oil", "model_b_id": "poles_jrc",
                    "variable": "oil_price_change_pct", "value_a": "0.0", "value_b": "54.79", "tolerance_pct": "50", "deviation_pct": "200",
                    "message": "LLM-extracted vs upstream-computed disagreement on fed_oil input oil_price_change_pct"})
    with open(csv_dir / "quantitative_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_id", "output_key", "value_numeric", "value_raw", "is_numeric"])
        w.writeheader()
        w.writerow({"scenario_id": "swift_contained", "model_id": "fed_oil", "output_key": "peak_gdp_impact_pct", "value_numeric": "-0.6", "value_raw": "-0.6", "is_numeric": "true"})
        w.writerow({"scenario_id": "swift_contained", "model_id": "pycge", "output_key": "_execution_mode", "value_numeric": "", "value_raw": "analytical_mvp", "is_numeric": "false"})
    with open(csv_dir / "model_status.csv", "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_id", "status", "task_id", "error_message"])
        w.writerow({"scenario_id": "swift_contained", "model_id": "pycge", "status": "completed", "task_id": 9, "error_message": ""})
    cells = ledger_from_report_csv("run-C", csv_dir, model_ids=["fed_oil", "ggm", "poles_jrc", "pycge"])
    by = {c.model_id: c for c in cells}
    assert by["fed_oil"].exec_status == "completed"
    # No marker in the CSVs and (in this test) no adapter declaration is
    # asserted; the evidence field says which it was.
    assert by["fed_oil"].implementation_mode_evidence in ("adapter_declared", "none")
    assert by["pycge"].implementation_mode == "analytical_reduction"
    assert by["pycge"].implementation_mode_evidence == "output_marker"
    assert by["fed_oil"].upstream_sources[0].source_model_id == "poles_jrc"
    assert by["fed_oil"].stale_upstream is True  # poles_jrc has no row in this scenario
    assert by["fed_oil"].upstream_evidence == "flags_only"
    assert by["ggm"].skip_class == "missing_config"
    assert by["poles_jrc"].skip_class == "record_missing"
