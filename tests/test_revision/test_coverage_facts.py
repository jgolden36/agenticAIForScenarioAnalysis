"""Tests for scripts/revision/coverage_facts.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.revision.coverage_facts import SCENARIO_ORDER, build_facts, main, model_facts, water_linkage_facts

COLS = ["scenario_id", "model_id", "exec_status", "skip_class", "implementation_mode", "upstream_sources", "upstream_evidence", "error_message"]


def _cells(spec: dict[tuple[str, str], dict]) -> list[dict[str, str]]:
    rows = []
    for (sid, mid), extra in spec.items():
        row = {c: "" for c in COLS}
        row.update({"scenario_id": sid, "model_id": mid, **extra})
        rows.append(row)
    return rows


def _ledger():
    return _cells({
        ("swift_contained", "cwatm"): {"exec_status": "no_record", "skip_class": "record_missing"},
        ("swift_escalated", "cwatm"): {"exec_status": "completed", "skip_class": "completed", "implementation_mode": "analytical_reduction"},
        ("infrastructure_collapse", "cwatm"): {"exec_status": "completed", "skip_class": "completed", "implementation_mode": "analytical_reduction"},
        ("infrastructure_collapse", "pycge"): {"exec_status": "completed", "skip_class": "completed", "upstream_sources": "poles_jrc;cwatm", "upstream_evidence": "full"},
        ("infrastructure_collapse", "mpsge_jl"): {"exec_status": "completed", "skip_class": "completed", "upstream_sources": "poles_jrc", "upstream_evidence": "full"},
        ("prolonged_contained", "world_helium_model"): {"exec_status": "completed", "skip_class": "completed", "implementation_mode": "analytical_reduction"},
        ("swift_escalated", "world_helium_model"): {"exec_status": "completed", "skip_class": "completed", "implementation_mode": "analytical_reduction"},
        ("swift_contained", "ggm"): {"exec_status": "skipped", "skip_class": "missing_config"},
        ("prolonged_contained", "ggm"): {"exec_status": "failed", "skip_class": "runtime_error", "error_message": "boom"},
    })


def test_model_facts_statement():
    f = model_facts(_ledger(), "cwatm")
    assert f["completed"] == ["swift_escalated", "infrastructure_collapse"]
    assert f["no_record"] == ["swift_contained", "prolonged_contained", "prolonged_escalated"]
    assert f["statement"] == "`cwatm` completed in CE (analytical_reduction); no surviving record in ABD."
    g = model_facts(_ledger(), "ggm")
    assert "skipped in A" in g["statement"] and "failed in B" in g["statement"]
    assert set(model_facts(_ledger(), "nope")["detail"]) == set(SCENARIO_ORDER)


def test_water_linkage_detects_cge_fed_by_cwatm():
    w = water_linkage_facts(_ledger())
    assert w["water_model_status"]["cwatm"] == "completed" and w["water_model_status"]["weap_mena"] == "absent"
    assert w["macro_cge_water_fed"] == {"pycge": True, "mpsge_jl": False, "opencge": False}
    assert "pycge" in w["statement"] and "model-computed" in w["statement"]
    no_cge = [c for c in _ledger() if c["model_id"] != "pycge"]
    assert "no macro CGE record lists it" in water_linkage_facts(no_cge)["statement"]
    unconfirmed = [dict(c, upstream_sources="poles_jrc(not run);cwatm(not run)") if c["model_id"] == "pycge" else c for c in _ledger()]
    w2 = water_linkage_facts(unconfirmed)
    assert w2["macro_cge_water_fed"]["pycge"] is False and w2["macro_cge_water_fed_unconfirmed"]["pycge"] is True
    assert "cannot be confirmed" in w2["statement"]
    no_water = [c for c in no_cge if c["model_id"] != "cwatm"]
    assert "no water model has a completed record" in water_linkage_facts(no_water)["statement"]


def test_build_facts_and_main(tmp_path):
    facts = build_facts(_ledger(), "r", ["cwatm", "world_helium_model"])
    assert facts["linkage_statements"]["helium"].endswith("scenarios BC.")
    assert facts["linkage_statements"]["fertilizer"].endswith("scenarios none.")
    assert "1 of 9 cells" in facts["caveat"]
    path = tmp_path / "coverage_ledger.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(_ledger())
    out = tmp_path / "docs"
    assert main(["--ledger", str(path), "--run-id", "r", "--models", "cwatm", "--out-dir", str(out)]) == 0
    data = json.loads((out / "coverage_facts_r.json").read_text())
    assert data["models"][0]["model_id"] == "cwatm"
    assert (out / "coverage_facts_r.md").read_text().startswith("# Coverage facts for run `r`")
