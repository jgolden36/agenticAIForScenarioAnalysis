"""Tests for uncertainty interpretation in Module 4 synthesis.

Covers:

* ``_attach_uncertainty_to_outcomes`` matches each ``SynthesizedOutcome``
  to its source model's ``UncertaintyReport`` estimates.
* ``_format_uncertainty_table`` renders all bands without inventing
  numbers.
* ``_aggregate_uncertainty_method`` collapses a list of results into
  one method label (``native | perturbation | mixed | none``).
* The full ``synthesize_by_section`` path attaches the LLM-authored
  ``UncertaintyInterpretation`` and the per-outcome ``uncertainty``
  band when results carry UQ data.
"""

from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableLambda

from src.common.types import (
    AnalyticalLevel,
    CommoditySystem,
    ModelExecutionStatus,
    OutcomeScope,
    Scenario,
    TimeHorizon,
)
from src.pipeline.state import (
    ModelExecutionResult,
    ScenarioNarrativeState,
)
from src.synthesis import sectioning
from src.synthesis.schemas import (
    ScenarioSynthesis,
    ScopedSynthesis,
    SynthesizedOutcome,
    UncertaintyInterpretation,
)
from src.synthesis.synthesizer import (
    _aggregate_uncertainty_method,
    _attach_uncertainty_to_outcomes,
    _extract_uncertainty_estimate,
    _format_models_without_uq,
    _format_uncertainty_table,
    synthesize_by_section,
)


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _result_with_uq(
    model_id: str,
    scenario: Scenario,
    outputs: dict,
    uq_estimates: dict[str, dict],
    method: str = "perturbation",
    n_replicates: int = 20,
) -> ModelExecutionResult:
    """Build a ModelExecutionResult with a serialized UncertaintyReport."""
    return ModelExecutionResult(
        scenario_id=scenario,
        model_id=model_id,
        status=ModelExecutionStatus.COMPLETED,
        outputs=outputs,
        uncertainty={
            "method": method,
            "n_replicates": n_replicates,
            "perturbation_pct": 10.0,
            "estimates": uq_estimates,
            "notes": "test",
            "failures": 0,
        },
    )


def _make_uq_entry(mean: float, std: float, p05: float, p95: float) -> dict:
    return {
        "mean": mean,
        "std": std,
        "n_samples": 21,
        "quantiles": {
            "p05": p05,
            "p25": (mean + p05) / 2,
            "p50": mean,
            "p75": (mean + p95) / 2,
            "p95": p95,
        },
    }


# --------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------


def test_extract_uncertainty_estimate_returns_none_without_uq():
    r = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="x",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"y": 1.0},
    )
    assert _extract_uncertainty_estimate(r, "y") is None


def test_extract_uncertainty_estimate_returns_dict_when_present():
    r = _result_with_uq(
        "x", Scenario.A, {"y": 100.0}, {"y": _make_uq_entry(100.0, 5.0, 90.0, 110.0)}
    )
    est = _extract_uncertainty_estimate(r, "y")
    assert est is not None
    assert est["mean"] == 100.0
    assert est["p05"] == 90.0
    assert est["p95"] == 110.0


def test_format_uncertainty_table_includes_each_model_and_key():
    r1 = _result_with_uq(
        "poles_jrc", Scenario.A, {"oil_price": 100.0},
        {"oil_price": _make_uq_entry(100.0, 5.0, 90.0, 110.0)},
        method="perturbation",
    )
    r2 = _result_with_uq(
        "pycge", Scenario.A, {"gdp_impact_pct": -1.5},
        {"gdp_impact_pct": _make_uq_entry(-1.5, 0.4, -2.3, -0.7)},
        method="native",
    )
    table = _format_uncertainty_table([r1, r2])
    assert "poles_jrc" in table
    assert "pycge" in table
    assert "oil_price" in table
    assert "gdp_impact_pct" in table
    # Method appears in the header.
    assert "method=perturbation" in table
    assert "method=native" in table


def test_format_uncertainty_table_handles_no_uq():
    r = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="bare",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"y": 1.0},
    )
    assert _format_uncertainty_table([r]).startswith("No uncertainty data")


def test_aggregate_uncertainty_method_unique_method():
    r = _result_with_uq(
        "m", Scenario.A, {"y": 1.0},
        {"y": _make_uq_entry(1.0, 0.1, 0.8, 1.2)},
        method="perturbation",
    )
    assert _aggregate_uncertainty_method([r]) == "perturbation"


def test_aggregate_uncertainty_method_mixed():
    r1 = _result_with_uq(
        "m1", Scenario.A, {"y": 1.0},
        {"y": _make_uq_entry(1.0, 0.1, 0.8, 1.2)},
        method="perturbation",
    )
    r2 = _result_with_uq(
        "m2", Scenario.A, {"z": 2.0},
        {"z": _make_uq_entry(2.0, 0.2, 1.6, 2.4)},
        method="native",
    )
    assert _aggregate_uncertainty_method([r1, r2]) == "mixed"


def test_aggregate_uncertainty_method_none_when_no_uq():
    r = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="x",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"y": 1.0},
    )
    assert _aggregate_uncertainty_method([r]) == "none"


def test_format_models_without_uq_lists_missing_models():
    r1 = _result_with_uq(
        "withuq", Scenario.A, {"y": 1.0},
        {"y": _make_uq_entry(1.0, 0.1, 0.8, 1.2)},
    )
    r2 = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="naked",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"y": 2.0},
    )
    msg = _format_models_without_uq([r1, r2])
    assert "naked" in msg
    assert "withuq" not in msg


# --------------------------------------------------------------------
# Outcome-level attachment
# --------------------------------------------------------------------


def test_attach_uncertainty_to_outcomes_matches_by_variable_name():
    synthesis = ScenarioSynthesis(
        scenario_id=Scenario.A,
        scenario_label="Swift Contained",
        sections=[
            ScopedSynthesis(
                time_horizon=TimeHorizon.SHORT_RUN,
                outcome_scope=OutcomeScope.MICRO,
                outcomes=[
                    SynthesizedOutcome(
                        variable="oil_price_usd",
                        value="100",
                        source_model_id="poles_jrc",
                    )
                ],
            )
        ],
    )
    results = [
        _result_with_uq(
            "poles_jrc", Scenario.A, {"oil_price_usd": 100.0},
            {"oil_price_usd": _make_uq_entry(100.0, 7.0, 88.0, 113.0)},
        )
    ]
    out = _attach_uncertainty_to_outcomes(synthesis, results)
    band = out.sections[0].outcomes[0].uncertainty
    assert band is not None
    assert band["mean"] == 100.0
    assert band["p05"] == 88.0
    assert band["p95"] == 113.0


def test_attach_uncertainty_falls_through_when_variable_unknown():
    synthesis = ScenarioSynthesis(
        scenario_id=Scenario.A,
        scenario_label="Swift Contained",
        sections=[
            ScopedSynthesis(
                time_horizon=TimeHorizon.SHORT_RUN,
                outcome_scope=OutcomeScope.MICRO,
                outcomes=[
                    SynthesizedOutcome(
                        variable="nonexistent_variable",
                        value="100",
                        source_model_id="poles_jrc",
                    )
                ],
            )
        ],
    )
    results = [
        _result_with_uq(
            "poles_jrc", Scenario.A, {"oil_price_usd": 100.0},
            {"oil_price_usd": _make_uq_entry(100.0, 7.0, 88.0, 113.0)},
        )
    ]
    out = _attach_uncertainty_to_outcomes(synthesis, results)
    # No matching estimate -> field stays None, no exception raised.
    assert out.sections[0].outcomes[0].uncertainty is None


def test_attach_uncertainty_skips_when_results_have_no_uq():
    synthesis = ScenarioSynthesis(
        scenario_id=Scenario.A,
        scenario_label="...",
        sections=[
            ScopedSynthesis(
                time_horizon=TimeHorizon.SHORT_RUN,
                outcome_scope=OutcomeScope.MICRO,
                outcomes=[
                    SynthesizedOutcome(
                        variable="oil_price_usd",
                        value="100",
                        source_model_id="poles_jrc",
                    )
                ],
            )
        ],
    )
    bare = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="poles_jrc",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"oil_price_usd": 100.0},
    )
    out = _attach_uncertainty_to_outcomes(synthesis, [bare])
    assert out.sections[0].outcomes[0].uncertainty is None


# --------------------------------------------------------------------
# End-to-end synthesize_by_section with UQ
# --------------------------------------------------------------------


class _UQAwareLLM:
    """Fake LLM that returns ScopedSynthesis for sections and a canned
    UncertaintyInterpretation for the UQ chain."""

    def __init__(self) -> None:
        self.uq_called = 0
        self.section_calls = 0

    def with_structured_output(self, schema):
        if schema is UncertaintyInterpretation:
            def _uq(_value):
                self.uq_called += 1
                return UncertaintyInterpretation(
                    summary="Bands are wide on macro outcomes; tight on commodity.",
                    high_confidence_findings=[
                        "oil_price_usd (poles_jrc): tight ~10% band",
                    ],
                    low_confidence_findings=[
                        "gdp_impact_pct (pycge): band crosses zero",
                    ],
                    decision_implications=(
                        "Lean on commodity-tier results; treat macro CGE as illustrative."
                    ),
                )
            return RunnableLambda(_uq)

        # Section synthesizer path.
        def _section(value):
            self.section_calls += 1
            messages = (
                value.to_messages() if hasattr(value, "to_messages") else value
            )
            text = "\n".join(
                getattr(m, "content", "")
                for m in (messages or [])
                if hasattr(m, "content")
            )
            time_horizon = TimeHorizon.SHORT_RUN
            outcome_scope = OutcomeScope.MICRO
            for th in TimeHorizon:
                if f"time_horizon={th.value}" in text:
                    time_horizon = th
                    break
            for sc in OutcomeScope:
                if f"outcome_scope={sc.value}" in text:
                    outcome_scope = sc
                    break
            return ScopedSynthesis(
                time_horizon=time_horizon,
                outcome_scope=outcome_scope,
                outcomes=[
                    SynthesizedOutcome(
                        variable="oil_price_usd",
                        value="100",
                        source_model_id="poles_jrc",
                        narrative="oil price under shock",
                    )
                ],
            )
        return RunnableLambda(_section)


def test_synthesize_by_section_attaches_uncertainty_and_interpretation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "poles_jrc": sectioning.ModelMetadata(
            "poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY
        ),
    }

    def _lookup(model_ids):
        return {mid: metadata[mid] for mid in model_ids if mid in metadata}

    monkeypatch.setattr(
        "src.synthesis.synthesizer.lookup_model_metadata", _lookup
    )

    llm = _UQAwareLLM()
    narrative = ScenarioNarrativeState(
        scenario_id=Scenario.A,
        label="Swift Contained",
        narrative="...",
    )
    results = [
        _result_with_uq(
            "poles_jrc", Scenario.A, {"oil_price_usd": 100.0},
            {"oil_price_usd": _make_uq_entry(100.0, 7.0, 88.0, 113.0)},
        )
    ]

    flags, synthesis, metrics = synthesize_by_section(
        llm,
        scenario_id=Scenario.A,
        narrative=narrative,
        results=results,
    )

    # Method aggregated and stored.
    assert synthesis.uncertainty_method == "perturbation"
    # UQ interpretation LLM call fired exactly once for this scenario.
    assert llm.uq_called == 1
    # Interpretation attached.
    interp = synthesis.uncertainty_interpretation
    assert interp is not None
    assert interp.high_confidence_findings
    assert interp.low_confidence_findings
    # Per-outcome band attached.
    sr_micro = next(
        s for s in synthesis.sections
        if s.time_horizon == TimeHorizon.SHORT_RUN
        and s.outcome_scope == OutcomeScope.MICRO
    )
    assert sr_micro.outcomes[0].uncertainty is not None
    assert sr_micro.outcomes[0].uncertainty["p05"] == 88.0


def test_synthesize_by_section_no_uq_skips_interpretation_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no result carries UQ, the LLM uncertainty call must not fire."""
    metadata = {
        "poles_jrc": sectioning.ModelMetadata(
            "poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY
        ),
    }

    def _lookup(model_ids):
        return {mid: metadata[mid] for mid in model_ids if mid in metadata}

    monkeypatch.setattr(
        "src.synthesis.synthesizer.lookup_model_metadata", _lookup
    )

    llm = _UQAwareLLM()
    narrative = ScenarioNarrativeState(
        scenario_id=Scenario.A,
        label="Swift Contained",
        narrative="...",
    )
    bare = ModelExecutionResult(
        scenario_id=Scenario.A,
        model_id="poles_jrc",
        status=ModelExecutionStatus.COMPLETED,
        outputs={"oil_price_usd": 100.0},
    )
    _, synthesis, _ = synthesize_by_section(
        llm,
        scenario_id=Scenario.A,
        narrative=narrative,
        results=[bare],
    )
    assert llm.uq_called == 0
    assert synthesis.uncertainty_method == "none"
    assert synthesis.uncertainty_interpretation is None
