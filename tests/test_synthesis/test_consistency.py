"""Tests for cross-model consistency checking."""

from src.common.types import ModelExecutionStatus, Scenario
from src.pipeline.config import ConsistencyConfig
from src.pipeline.state import ModelExecutionResult
from src.synthesis.consistency import check_consistency


def _make_result(model_id: str, outputs: dict) -> ModelExecutionResult:
    """Helper to create a mock execution result."""
    return ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id=model_id,
        status=ModelExecutionStatus.COMPLETED,
        outputs=outputs,
    )


def test_no_flags_when_models_agree():
    """No flags when model outputs are within tolerance."""
    results = [
        _make_result("bornstein_krusell_rebelo", {"oil_price_usd": 100.0}),
        _make_result("poles_jrc", {"oil_price_usd": 105.0}),
    ]
    flags = check_consistency(Scenario.A, results)
    assert len(flags) == 0


def test_flag_when_models_disagree():
    """Flag raised when models exceed tolerance."""
    results = [
        _make_result("bornstein_krusell_rebelo", {"oil_price_usd": 100.0}),
        _make_result("poles_jrc", {"oil_price_usd": 200.0}),
    ]
    config = ConsistencyConfig(price_tolerance_pct=20.0)
    flags = check_consistency(Scenario.A, results, config)
    assert len(flags) == 1
    assert flags[0].model_a_id == "bornstein_krusell_rebelo"
    assert flags[0].model_b_id == "poles_jrc"
    assert flags[0].deviation_pct > 20.0


def test_no_flags_when_models_missing():
    """No flags when one model in a pair is missing."""
    results = [
        _make_result("bornstein_krusell_rebelo", {"oil_price_usd": 100.0}),
    ]
    flags = check_consistency(Scenario.A, results)
    assert len(flags) == 0


def test_no_flags_when_variable_missing():
    """No flags when the compared variable is not in outputs."""
    results = [
        _make_result("bornstein_krusell_rebelo", {"some_other_var": 100.0}),
        _make_result("poles_jrc", {"some_other_var": 200.0}),
    ]
    flags = check_consistency(Scenario.A, results)
    assert len(flags) == 0


def test_multiple_consistency_rules():
    """Test that multiple rules are checked independently."""
    results = [
        _make_result("bornstein_krusell_rebelo", {"oil_price_usd": 100.0}),
        _make_result("poles_jrc", {"oil_price_usd": 300.0}),
        _make_result("opencge", {"gdp_impact_pct": -2.0}),
        _make_result("pycge", {"gdp_impact_pct": -8.0}),
    ]
    flags = check_consistency(Scenario.A, results)
    assert len(flags) == 2
