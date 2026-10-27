"""Tests for scripts/revision/effort_metrics.py (run against this repository)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.revision.effort_metrics import (
    adapter_rows,
    count_lines,
    forwarding_rule_rows,
    main,
    named_change_rows,
)

REPO = Path(__file__).resolve().parents[2]


def test_count_lines_skips_comments_and_docstrings(tmp_path):
    p = tmp_path / "m.py"
    p.write_text('"""Doc\nmore doc\n"""\n\n# comment\nx = 1\ny = 2  # trailing\n\n"""one-line doc"""\n')
    assert count_lines(p) == (2, 9)


def test_adapter_rows_cover_registered_models():
    rows = adapter_rows(REPO)
    ids = {r["model_id"] for r in rows}
    for expected in ("poles_jrc", "fed_oil", "pycge", "weap_mena", "temoa", "apsim"):
        assert expected in ids
    row = next(r for r in rows if r["model_id"] == "poles_jrc")
    assert row["code_lines"] > 50 and row["total_lines"] >= row["code_lines"]
    assert row["test_files"] >= 1 and row["test_code_lines"] > 0
    assert row["person_hours"] == ""
    if row["commits"]:
        assert row["first_commit"] <= row["last_commit"]


def test_forwarding_rules_and_named_changes():
    rules = forwarding_rule_rows(REPO)
    by = {r["downstream_model"]: r for r in rules}
    assert "apsim" in by and by["apsim"]["yaml_lines"] > 0 and by["apsim"]["rules"] >= 2
    assert "pycge" in by
    changes = named_change_rows(REPO)
    names = {c["change"] for c in changes}
    assert names == {"infrastructure_collapse_scenario", "apsim_fertilizer_food_bridge"}
    for c in changes:
        assert "person_hours" in c and c["person_hours"] == ""


def test_main_writes_outputs(tmp_path):
    assert main(["--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "effort_metrics.md").exists()
    data = json.loads((tmp_path / "effort_metrics.json").read_text())
    assert data["adapters"] and data["forwarding_rules"] and data["named_changes"]
