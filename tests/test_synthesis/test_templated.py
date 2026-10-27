"""Tests for the LLM-free templated synthesis."""

from __future__ import annotations

from datetime import datetime, timezone

from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.state import ModelExecutionResult, ScenarioNarrativeState
from src.synthesis.fidelity import MISMATCH_CATEGORIES, audit_section
from src.synthesis.templated import (
    format_value,
    infer_unit,
    outcome_from_output,
    select_headline_outputs,
    templated_synthesis,
)


def _result(model_id: str, outputs: dict, status=ModelExecutionStatus.COMPLETED, mode="analytical_reduction"):
    now = datetime.now(timezone.utc)
    return ModelExecutionResult(
        scenario_id=Scenario.A, model_id=model_id, status=status, outputs=outputs,
        started_at=now, completed_at=now, runtime_seconds=0.1,
        implementation_mode=mode if status == ModelExecutionStatus.COMPLETED else None,
        error_message=None if status == ModelExecutionStatus.COMPLETED else "Not yet implemented: stub",
    )


def _narrative():
    return ScenarioNarrativeState(scenario_id=Scenario.A, label="Swift Contained", narrative="x")


def test_select_headline_outputs_filters_and_orders():
    outputs = {
        "peak_price_change_pct": 54.8, "supply_loss_mbd": 14.0, "disruption_duration_months": 1.25,
        "_inputs": {"a": 1}, "brent_price_path": [1, 2], "note": "text", "flag": True, "zzz_other": 3,
        "baseline_price_usd_per_bbl": 80.0,
    }
    picked = select_headline_outputs("poles_jrc", outputs, params={"supply_loss_mbd": 14.0})
    keys = [k for k, _ in picked]
    assert keys[0] == "peak_price_change_pct"
    assert "supply_loss_mbd" not in keys  # echoes an input
    assert "disruption_duration_months" not in keys  # echo prefix
    assert "_inputs" not in keys and "brent_price_path" not in keys and "note" not in keys and "flag" not in keys
    assert "zzz_other" in keys and keys.index("baseline_price_usd_per_bbl") < keys.index("zzz_other")
    assert len(select_headline_outputs("poles_jrc", outputs, max_outcomes_per_model=1)) == 1


def test_format_value_and_units():
    assert format_value(54.8) == "54.8" and format_value(3) == "3" and format_value(2.0) == "2.0"
    assert format_value(-0.157) == "-0.157"
    assert infer_unit("gdp_impact_pct") == "percent"
    assert infer_unit("peak_cpi_impact_pp") == "percentage points"
    assert infer_unit("ttf_price") == "USD/MMBtu"
    assert infer_unit("rerouting_cost_multiplier") == "x baseline"
    assert infer_unit("something_odd") is None


def test_outcome_is_verbatim_and_template_prose():
    o = outcome_from_output("fed_oil", "peak_gdp_impact_pct", -1.234, scenario_label="A", implementation_mode="analytical_reduction", n_overrides=2)
    assert o.value == "-1.234" and o.source_model_id == "fed_oil" and o.unit == "percent"
    assert "copied verbatim" in o.narrative and "-1.234" in o.narrative
    assert "2 input(s) replaced" in o.reliability_note and o.fidelity_status == "exact"


def test_templated_synthesis_routes_and_audits_exact():
    results = [
        _result("poles_jrc", {"peak_price_change_pct": 54.8, "peak_price_usd_per_bbl": 123.9, "supply_loss_mbd": 14.0}),
        _result("fed_oil", {"peak_gdp_impact_pct": -1.2, "peak_cpi_impact_pp": 0.9, "_upstream_overrides": [{"name": "oil_price_change_pct"}]}),
        _result("pycge", {"gdp_impact_pct": -0.157, "cpi_inflation_pct": 1.3458, "sectoral_output_pct_change": {"energy": 0.07}}),
        _result("ggm", {}, status=ModelExecutionStatus.SKIPPED),
    ]
    flags, synthesis, metrics = templated_synthesis(Scenario.A, _narrative(), results)
    assert synthesis.scenario_label == "Swift Contained"
    assert synthesis.failed_models == ["ggm"]
    by_label = {f"{s.time_horizon.value}/{s.outcome_scope.value}": s for s in synthesis.sections}
    assert len(by_label) == 6
    micro_sr = by_label["short_run/micro"]
    assert {o.source_model_id for o in micro_sr.outcomes} == {"poles_jrc"}
    assert {o.source_model_id for o in by_label["short_run/macro"].outcomes} == {"fed_oil"}
    assert {o.source_model_id for o in by_label["long_run/macro"].outcomes} == {"pycge"}
    all_outcomes = [o for s in synthesis.sections for o in s.outcomes]
    assert all(o.value and o.narrative for o in all_outcomes)
    fed = next(o for o in all_outcomes if o.source_model_id == "fed_oil")
    assert "1 input(s) replaced" in fed.reliability_note
    # Every templated outcome must audit as exact against its source outputs.
    for section in synthesis.sections:
        if not section.outcomes:
            continue
        audits = audit_section(section, results, [r.model_id for r in results], "swift_contained")
        assert all(a.category == "exact" for a in audits), [(a.variable, a.category) for a in audits]
        assert not any(a.category in MISMATCH_CATEGORIES for a in audits)
    # Routing mirrors the LLM path: commodity models appear in both micro
    # sections and macro CGEs in long-run macro and strategic, so 5 of the
    # 6 sections carry outcomes here (short-run strategic stays empty).
    ok = [m for m in metrics.values() if m["status"] == "ok"]
    assert len(ok) == 5 and all(m["prompt_tokens"] == 0 and m["method"] == "templated" for m in metrics.values())
    assert all(m["status"] in ("ok", "empty") for m in metrics.values())


def test_templated_synthesis_with_no_completed_models():
    results = [_result("ggm", {}, status=ModelExecutionStatus.SKIPPED)]
    flags, synthesis, metrics = templated_synthesis(Scenario.A, _narrative(), results)
    assert all(not s.outcomes for s in synthesis.sections)
    assert all(m["status"] == "empty" for m in metrics.values())
