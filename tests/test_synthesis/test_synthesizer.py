"""Tests for the section-aware Module 4 synthesizer.

Asserts that ``synthesize_by_section`` invokes the LLM once per
non-empty (time_horizon, outcome_scope) section, never crams all model
outputs into a single prompt, and surfaces per-section telemetry the
SLURM driver records into the synthesis-state JSON.
"""

from __future__ import annotations

from unittest.mock import MagicMock

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
)
from src.synthesis.synthesizer import (
    _empty_scoped_synthesis,
    _halve_section_inputs,
    synthesize_by_section,
)


# --------------------------------------------------------------------
# Mock LLM scaffolding
# --------------------------------------------------------------------


def _make_recording_runnable(recorder: list[dict]) -> RunnableLambda:
    """Stand-in for ``llm.with_structured_output(ScopedSynthesis)``.

    Returned as a ``RunnableLambda`` so it composes with ``PROMPT |
    structured_llm`` the same way a real ChatModel would. Each
    invocation parses the section coordinates out of the rendered
    human message and records them on ``recorder``.
    """

    def _invoke(value):
        messages = value.to_messages() if hasattr(value, "to_messages") else value
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
        recorder.append(
            {
                "time_horizon": time_horizon,
                "outcome_scope": outcome_scope,
                "text": text,
            }
        )
        return ScopedSynthesis(
            time_horizon=time_horizon,
            outcome_scope=outcome_scope,
            outcomes=[
                SynthesizedOutcome(
                    variable=f"{time_horizon.value}_{outcome_scope.value}_summary",
                    value="42",
                    source_model_id="mock_source",
                    narrative="mock narrative",
                ),
            ],
        )

    return RunnableLambda(_invoke)


class _FakeLLM:
    """Stand-in for ``BaseChatModel`` exposing ``with_structured_output``."""

    def __init__(self) -> None:
        self.recorder: list[dict] = []

    def with_structured_output(self, schema):
        return _make_recording_runnable(self.recorder)


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _make_result(model_id: str, scenario: Scenario, outputs: dict) -> ModelExecutionResult:
    return ModelExecutionResult(
        scenario_id=scenario,
        model_id=model_id,
        status=ModelExecutionStatus.COMPLETED,
        outputs=outputs,
    )


def _stub_metadata(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, sectioning.ModelMetadata]) -> None:
    """Bypass the registry for the duration of one test."""

    def _lookup(model_ids):
        return {mid: mapping[mid] for mid in model_ids if mid in mapping}

    monkeypatch.setattr(
        "src.synthesis.synthesizer.lookup_model_metadata",
        _lookup,
    )


# --------------------------------------------------------------------
# synthesize_by_section
# --------------------------------------------------------------------


def test_synthesize_by_section_calls_llm_once_per_nonempty_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "poles_jrc": sectioning.ModelMetadata(
            "poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY
        ),
        "nems": sectioning.ModelMetadata(
            "nems", CommoditySystem.MACROECONOMIC, AnalyticalLevel.SHORT_RUN_MACRO
        ),
        "opencge": sectioning.ModelMetadata(
            "opencge", CommoditySystem.MACROECONOMIC, AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC
        ),
    }
    _stub_metadata(monkeypatch, metadata)

    llm = _FakeLLM()
    narrative = ScenarioNarrativeState(
        scenario_id=Scenario.A,
        label="Swift Resolution, Contained Conflict",
        narrative="A short narrative.",
        quantitative_assumptions={},
    )
    results = [
        _make_result("poles_jrc", Scenario.A, {"oil_price_usd": 90.0}),
        _make_result("nems", Scenario.A, {"gdp_growth_pct": 2.1}),
        _make_result("opencge", Scenario.A, {"long_run_gdp_pct": -0.5}),
    ]

    flags, synthesis, section_metrics = synthesize_by_section(
        llm,
        scenario_id=Scenario.A,
        narrative=narrative,
        results=results,
    )

    # Three models route to multiple sections under the default rules:
    #   poles_jrc (OIL/COMMODITY)            -> SR/MICRO + LR/MICRO
    #   nems (MACROECONOMIC/SHORT_RUN_MACRO) -> SR/MACRO + SR/STRATEGIC
    #   opencge (MACROECONOMIC/LRMS)         -> LR/MACRO + LR/STRATEGIC
    # Every section that matches at least one model must produce
    # exactly one LLM call.
    horizons_called = {(c["time_horizon"], c["outcome_scope"]) for c in llm.recorder}
    assert (TimeHorizon.SHORT_RUN, OutcomeScope.MICRO) in horizons_called
    assert (TimeHorizon.SHORT_RUN, OutcomeScope.MACRO) in horizons_called
    assert (TimeHorizon.SHORT_RUN, OutcomeScope.STRATEGIC) in horizons_called
    assert (TimeHorizon.LONG_RUN, OutcomeScope.MICRO) in horizons_called
    assert (TimeHorizon.LONG_RUN, OutcomeScope.MACRO) in horizons_called
    assert (TimeHorizon.LONG_RUN, OutcomeScope.STRATEGIC) in horizons_called
    # Exactly N calls = N non-empty sections (no double-invocation).
    assert len(llm.recorder) == 6

    # synthesis is a ScenarioSynthesis with one section per call.
    assert isinstance(synthesis, ScenarioSynthesis)
    # All 6 sections appear (empty ones included) so the grid stays uniform.
    assert len(synthesis.sections) == 6


def test_synthesize_by_section_returns_metrics_per_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "poles_jrc": sectioning.ModelMetadata(
            "poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY
        ),
    }
    _stub_metadata(monkeypatch, metadata)

    llm = _FakeLLM()
    narrative = ScenarioNarrativeState(
        scenario_id=Scenario.B,
        label="Prolonged Closure, Contained",
        narrative="...",
    )
    results = [_make_result("poles_jrc", Scenario.B, {"oil_price_usd": 130.0})]

    _, _, metrics = synthesize_by_section(
        llm,
        scenario_id=Scenario.B,
        narrative=narrative,
        results=results,
    )

    # Six section keys present in the metrics dict.
    assert len(metrics) == 6
    # poles_jrc (OIL/COMMODITY) routes to SR/MICRO and LR/MICRO.
    short_micro = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO)
    long_micro = sectioning.SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.MICRO)
    for key in (short_micro, long_micro):
        assert metrics[key]["status"] == "ok"
        assert metrics[key]["model_count"] == 1
        assert metrics[key]["prompt_tokens"] > 0
        assert metrics[key]["truncation_attempts"] == 0
    # The macro and strategic sections receive no oil-tier model so
    # they must be empty (no LLM call).
    short_macro = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MACRO)
    assert metrics[short_macro]["status"] == "empty"
    assert metrics[short_macro]["prompt_tokens"] == 0


def test_synthesize_by_section_handles_failure_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed LLM call must produce an empty section + warning, not crash."""
    metadata = {
        "poles_jrc": sectioning.ModelMetadata(
            "poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY
        ),
    }
    _stub_metadata(monkeypatch, metadata)

    def _boom(_value):
        raise RuntimeError("simulated LLM failure")

    class _ExplodingLLM:
        def with_structured_output(self, schema):
            return RunnableLambda(_boom)

    narrative = ScenarioNarrativeState(
        scenario_id=Scenario.A,
        label="Swift Resolution",
        narrative="...",
    )
    results = [_make_result("poles_jrc", Scenario.A, {"oil_price_usd": 90.0})]

    _, synthesis, metrics = synthesize_by_section(
        _ExplodingLLM(),
        scenario_id=Scenario.A,
        narrative=narrative,
        results=results,
    )

    short_micro = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO)
    assert metrics[short_micro]["status"] == "failed"
    # The section appears in the aggregated synthesis as empty.
    sr_micro_section = next(
        s for s in synthesis.sections
        if s.time_horizon == TimeHorizon.SHORT_RUN
        and s.outcome_scope == OutcomeScope.MICRO
    )
    assert sr_micro_section.outcomes == []
    # A consistency warning is recorded so the failure is auditable.
    assert any(
        "synthesis failed" in w.lower() for w in synthesis.consistency_warnings
    )


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def test_halve_section_inputs_shrinks_text_fields() -> None:
    inputs = {
        "model_results": "word " * 1000,
        "scenario_description": "word " * 1000,
        "non_text_field": 123,
        "scenario_id": "swift_contained",
    }
    halved = _halve_section_inputs(inputs)
    assert len(halved["model_results"]) < len(inputs["model_results"])
    assert len(halved["scenario_description"]) < len(inputs["scenario_description"])
    # Non-text fields pass through.
    assert halved["non_text_field"] == 123
    assert halved["scenario_id"] == "swift_contained"


def test_empty_scoped_synthesis_is_well_formed() -> None:
    key = sectioning.SectionKey(TimeHorizon.LONG_RUN, OutcomeScope.MACRO)
    empty = _empty_scoped_synthesis(key)
    assert empty.time_horizon == TimeHorizon.LONG_RUN
    assert empty.outcome_scope == OutcomeScope.MACRO
    assert empty.outcomes == []
