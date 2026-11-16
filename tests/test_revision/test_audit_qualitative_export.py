"""The commentary audit must surface a percent value restated x100, as happened with -15.7."""

from __future__ import annotations

from pathlib import Path

from scripts.revision.audit_qualitative_export import audit_export, audit_section, render, split_sections
from src.synthesis.fidelity import flatten_numeric

SCENARIO_FILE = """# Scenario

## `poles_jrc`  _(commodity: oil)_

Oil peaks at 54.79% above baseline.

## `pycge`  _(commodity: macroeconomic)_

The model predicts a 15.7% decline in global GDP. Consumption falls 6.9% over 5 days. CPI rises 1.3458 in 2026.
"""


def test_split_sections_by_model() -> None:
    sections = split_sections(SCENARIO_FILE)
    assert list(sections) == ["poles_jrc", "pycge"]
    assert sections["poles_jrc"] == "Oil peaks at 54.79% above baseline."


def test_audit_section_classifies_each_token() -> None:
    outputs = flatten_numeric({"gdp_impact_pct": -0.157, "consumption_impact_pct": -0.6953, "cpi_inflation_pct": 1.3458})
    rows = audit_section(split_sections(SCENARIO_FILE)["pycge"], outputs)
    assert {r["token"]: r["relation"] for r in rows} == {"15.7": "x100", "6.9": "unmatched", "5": "unmatched", "1.3458": "exact"}
    assert "global GDP" in next(r["sentence"] for r in rows if r["token"] == "15.7")


def test_audit_section_prefers_the_most_faithful_reading() -> None:
    # 5.0 is both exactly one output and x100 of another.
    assert audit_section("Value 5.0 here.", {"a": 0.05, "b": 5.0})[0]["relation"] == "exact"


def test_audit_export_covers_only_scenarios_with_a_file(tmp_path: Path) -> None:
    (tmp_path / "swift_contained.md").write_text(SCENARIO_FILE, encoding="utf-8")
    outputs = {"swift_contained": {"poles_jrc": {"peak_price_change_pct": 54.79}, "pycge": None}, "no_file": {"pycge": {"x": 1.0}}}
    rows = audit_export(tmp_path, outputs)
    assert {r["scenario_id"] for r in rows} == {"swift_contained"}
    # A section whose model has no recorded output has nothing to match.
    assert all(r["relation"] == "unmatched" for r in rows if r["model_id"] == "pycge")
    assert "54.79" in [r["token"] for r in rows if r["relation"] == "exact"]


def test_render_lists_x100_rows_for_reading() -> None:
    rows = [{"scenario_id": "a", "model_id": "pycge", "token": "15.7", "relation": "x100", "sentence": "A 15.7% decline."}]
    text = render("run", rows)
    assert "| a | pycge | 15.7 | A 15.7% decline. |" in text
