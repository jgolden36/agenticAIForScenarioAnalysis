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


# ---------------------------------------------------------------------------
# Upstream-override divergence flags (Algorithm 1, step 11)
# ---------------------------------------------------------------------------


from src.synthesis.consistency import check_upstream_overrides


def test_upstream_override_flag_emitted_above_threshold():
    """Macro models record _upstream_overrides; large LLM-vs-upstream
    deviations should surface as ConsistencyFlag entries."""
    results = [
        _make_result(
            "opencge",
            {
                "gdp_impact_pct": -3.0,
                "_upstream_overrides": [
                    {
                        "name": "oil_price_shock_pct",
                        "target_key": None,
                        "llm_value": 100.0,
                        "computed_value": 30.0,
                        "source_model_id": "poles_jrc",
                        "source_field": "peak_price_change_pct",
                        "transform": "identity",
                        "deviation_pct": 107.7,
                    }
                ],
            },
        )
    ]
    flags = check_upstream_overrides(Scenario.A, results, threshold_pct=50.0)
    assert len(flags) == 1
    assert flags[0].model_a_id == "opencge"
    assert flags[0].model_b_id == "poles_jrc"
    assert flags[0].variable == "oil_price_shock_pct"
    assert flags[0].deviation_pct == 107.7


def test_upstream_override_no_flag_when_llm_value_was_none():
    """No comparison possible when LLM did not extract a value."""
    results = [
        _make_result(
            "opencge",
            {
                "_upstream_overrides": [
                    {
                        "name": "commodity_price_shocks",
                        "target_key": "helium",
                        "llm_value": None,
                        "computed_value": 200.0,
                        "source_model_id": "world_helium_model",
                        "source_field": "price_change_pct",
                        "transform": "identity",
                        "deviation_pct": None,
                    }
                ],
            },
        )
    ]
    flags = check_upstream_overrides(Scenario.A, results, threshold_pct=50.0)
    assert flags == []


def test_upstream_override_no_flag_below_threshold():
    """Small disagreements do not surface."""
    results = [
        _make_result(
            "pycge",
            {
                "_upstream_overrides": [
                    {
                        "name": "oil_price_shock_pct",
                        "target_key": None,
                        "llm_value": 30.0,
                        "computed_value": 33.0,
                        "source_model_id": "poles_jrc",
                        "source_field": "peak_price_change_pct",
                        "transform": "identity",
                        "deviation_pct": 9.5,
                    }
                ],
            },
        )
    ]
    flags = check_upstream_overrides(Scenario.A, results, threshold_pct=50.0)
    assert flags == []


def test_check_consistency_includes_upstream_override_flags():
    """check_consistency should fold upstream-override flags into its output."""
    results = [
        _make_result(
            "opencge",
            {
                "_upstream_overrides": [
                    {
                        "name": "oil_price_shock_pct",
                        "target_key": None,
                        "llm_value": 100.0,
                        "computed_value": 20.0,
                        "source_model_id": "poles_jrc",
                        "source_field": "peak_price_change_pct",
                        "transform": "identity",
                        "deviation_pct": 133.3,
                    }
                ],
            },
        )
    ]
    flags = check_consistency(Scenario.A, results)
    assert any(
        f.model_a_id == "opencge"
        and f.model_b_id == "poles_jrc"
        and f.variable == "oil_price_shock_pct"
        for f in flags
    )


# ---------------------------------------------------------------------------
# Cross-source disagreement (combine policies)
# ---------------------------------------------------------------------------

from src.synthesis.consistency import check_cross_source_disagreement


def _override_with_candidates(deviation_pct, candidates):
    return {
        "name": "rerouting_cost_multiplier",
        "target_key": None,
        "llm_value": 1.2,
        "computed_value": 1.5,
        "source_model_id": "aisdb+ais_project",
        "source_field": "rerouting_cost_multiplier",
        "transform": "combine:mean",
        "deviation_pct": 22.0,
        "combine": "mean",
        "candidate_sources": candidates,
        "cross_source_deviation_pct": deviation_pct,
    }


def test_cross_source_disagreement_flag_above_threshold():
    candidates = [
        {
            "source_model": "aisdb",
            "source_field": "rerouting_cost_multiplier",
            "value": 1.0,
        },
        {
            "source_model": "ais_project",
            "source_field": "rerouting_cost_multiplier",
            "value": 2.0,
        },
    ]
    results = [
        _make_result(
            "poles_jrc",
            {"_upstream_overrides": [_override_with_candidates(66.7, candidates)]},
        )
    ]
    flags = check_cross_source_disagreement(
        Scenario.A, results, threshold_pct=30.0
    )
    assert len(flags) == 1
    assert flags[0].model_a_id == "poles_jrc"
    assert flags[0].value_a == 1.0
    assert flags[0].value_b == 2.0
    assert "aisdb" in flags[0].message and "ais_project" in flags[0].message


def test_cross_source_no_flag_below_threshold():
    candidates = [
        {"source_model": "aisdb", "source_field": "x", "value": 1.4},
        {"source_model": "ais_project", "source_field": "x", "value": 1.5},
    ]
    results = [
        _make_result(
            "poles_jrc",
            {"_upstream_overrides": [_override_with_candidates(6.9, candidates)]},
        )
    ]
    assert (
        check_cross_source_disagreement(Scenario.A, results, threshold_pct=30.0)
        == []
    )


def test_cross_source_no_flag_with_single_candidate():
    candidates = [
        {"source_model": "aisdb", "source_field": "x", "value": 1.4},
    ]
    results = [
        _make_result(
            "poles_jrc",
            {"_upstream_overrides": [_override_with_candidates(None, candidates)]},
        )
    ]
    assert (
        check_cross_source_disagreement(Scenario.A, results, threshold_pct=30.0)
        == []
    )


def test_check_consistency_includes_cross_source_flags():
    candidates = [
        {"source_model": "aisdb", "source_field": "x", "value": 1.0},
        {"source_model": "ais_project", "source_field": "x", "value": 2.0},
    ]
    results = [
        _make_result(
            "poles_jrc",
            {"_upstream_overrides": [_override_with_candidates(66.7, candidates)]},
        )
    ]
    flags = check_consistency(Scenario.A, results)
    assert any("Upstream sources disagree" in f.message for f in flags)
