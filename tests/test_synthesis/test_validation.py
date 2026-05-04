"""Tests for the per-output validation engine."""

from __future__ import annotations

import math

from src.synthesis.validation import (
    ValidationFinding,
    ValidationReport,
    render_validation_markdown,
    validate_outputs,
)


def _result(
    model_id: str,
    outputs: dict,
    *,
    scenario_id: str = "swift_resolution_contained",
    status: str = "completed",
) -> dict:
    """Build a mock state-file dict matching Module 3's contract."""
    return {
        "scenario_id": scenario_id,
        "model_id": model_id,
        "status": status,
        "outputs": outputs,
    }


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def _error_count(report: ValidationReport) -> int:
    return len(report.errors)


def test_bounds_pass_when_value_inside_range():
    results = [_result("poles_jrc", {"oil_price_usd": 95.0})]
    report = validate_outputs(results)
    assert _error_count(report) == 0


def test_bounds_flag_negative_oil_price():
    results = [_result("poles_jrc", {"oil_price_usd": -5.0})]
    report = validate_outputs(results)
    assert _error_count(report) >= 1
    assert any(
        f.variable == "oil_price_usd" and f.rule_kind == "bounds"
        for f in report.errors
    )


def test_bounds_flag_oil_price_above_max():
    results = [_result("poles_jrc", {"oil_price_usd": 5000.0})]
    report = validate_outputs(results)
    assert any(
        f.variable == "oil_price_usd" and "exceeds maximum" in f.message
        for f in report.errors
    )


def test_bounds_flag_extreme_gdp_impact():
    results = [_result("opencge", {"gdp_impact_pct": -200.0})]
    report = validate_outputs(results)
    assert any(
        f.variable == "gdp_impact_pct" and f.rule_kind == "bounds"
        for f in report.errors
    )


# ---------------------------------------------------------------------------
# Non-negative
# ---------------------------------------------------------------------------


def test_non_negative_flag_negative_supply_loss():
    results = [_result("bornstein_krusell_rebelo", {"oil_supply_loss_mbd": -2.0})]
    report = validate_outputs(results)
    assert any(
        f.rule_kind == "non_negative" and f.variable == "oil_supply_loss_mbd"
        for f in report.errors
    )


def test_non_negative_passes_when_zero_or_positive():
    results = [
        _result("ggm", {"qatar_lng_export_loss_pct": 0.0}),
        _result("ggm", {"iran_lng_export_loss_pct": 50.0}),
    ]
    report = validate_outputs(results)
    assert _error_count(report) == 0


# ---------------------------------------------------------------------------
# Finiteness
# ---------------------------------------------------------------------------


def test_nan_flagged_as_finite_error():
    results = [_result("opencge", {"gdp_impact_pct": float("nan")})]
    report = validate_outputs(results)
    assert any(
        f.rule_kind == "finite" and f.variable == "gdp_impact_pct"
        for f in report.errors
    )


def test_inf_flagged_as_finite_error():
    results = [_result("opencge", {"cpi_inflation_pct": math.inf})]
    report = validate_outputs(results)
    assert any(
        f.rule_kind == "finite" and f.variable == "cpi_inflation_pct"
        for f in report.errors
    )


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


def test_relation_peak_at_least_mean_passes():
    results = [
        _result(
            "poles_jrc",
            {"peak_price_change_pct": 80.0, "price_change_pct": 40.0},
        )
    ]
    report = validate_outputs(results)
    assert _error_count(report) == 0


def test_relation_peak_below_mean_flagged():
    # peak < mean (in absolute value) is a clear identity violation.
    results = [
        _result(
            "poles_jrc",
            {"peak_price_change_pct": 10.0, "price_change_pct": 40.0},
        )
    ]
    report = validate_outputs(results)
    assert any(f.rule_kind == "relation" for f in report.errors)


def test_relation_skipped_when_required_var_missing():
    # peak_price_change_pct missing -> rule should silently skip.
    results = [_result("poles_jrc", {"price_change_pct": 40.0})]
    report = validate_outputs(results)
    assert not any(f.rule_kind == "relation" for f in report.errors)


def test_relation_supply_loss_with_zero_price_shock_flagged():
    # 5 mb/d loss + 0% price shock is a directionality error.
    results = [
        _result(
            "poles_jrc",
            {"oil_supply_loss_mbd": 5.0, "oil_price_shock_pct": 0.0},
        )
    ]
    report = validate_outputs(results)
    assert any(
        f.rule_kind == "relation" and "oil_supply_loss_mbd" in (f.variable or "")
        for f in report.errors
    )


def test_relation_supply_loss_zero_does_not_fire():
    # Zero loss should not trigger the directionality rule.
    results = [
        _result(
            "poles_jrc",
            {"oil_supply_loss_mbd": 0.0, "oil_price_shock_pct": 0.0},
        )
    ]
    report = validate_outputs(results)
    assert not any(f.rule_kind == "relation" for f in report.errors)


# ---------------------------------------------------------------------------
# Skipping non-completed results
# ---------------------------------------------------------------------------


def test_skipped_results_are_ignored():
    # FAILED / SKIPPED results contribute no checks even if they
    # carry stale outputs.
    results = [
        _result("opencge", {"gdp_impact_pct": -999.0}, status="failed"),
        _result("pycge", {"oil_price_usd": -1.0}, status="skipped"),
    ]
    report = validate_outputs(results)
    assert report.models_checked == 0
    assert _error_count(report) == 0


def test_completed_results_are_counted():
    results = [
        _result("opencge", {"gdp_impact_pct": -2.0}),
        _result("pycge", {"gdp_impact_pct": -1.5}),
    ]
    report = validate_outputs(results)
    assert report.models_checked == 2


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def test_markdown_rendering_smoke():
    results = [_result("poles_jrc", {"oil_price_usd": -5.0})]
    report = validate_outputs(results, run_id="test_run")
    md = render_validation_markdown(report)
    assert "Output validation" in md
    assert "test_run" in md
    assert "Errors" in md


def test_markdown_clean_report():
    report = validate_outputs([], run_id="empty_run")
    md = render_validation_markdown(report)
    assert "passed" in md.lower() or "Errors:** 0" in md


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


def test_finding_to_dict_round_trip():
    f = ValidationFinding(
        severity="error",
        rule_kind="bounds",
        scenario_id="A",
        model_id="poles_jrc",
        variable="oil_price_usd",
        value=-5.0,
        message="oil_price_usd=-5.0 is below minimum 0",
    )
    d = f.to_dict()
    assert d["severity"] == "error"
    assert d["variable"] == "oil_price_usd"
    assert d["value"] == -5.0


