"""Pydantic schemas for synthesis output (Module 4)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.common.types import OutcomeScope, Scenario, TimeHorizon


class SynthesizedOutcome(BaseModel):
    """A single synthesized outcome variable.

    Distributional fields (``regional_distribution``,
    ``sectoral_distribution``, ``distribution_note``,
    ``native_regional_records``) are optional and are pre-populated by
    the synthesizer from upstream model outputs *before* the LLM call,
    so the LLM never invents region- or sector-level numbers — it only
    writes ``distribution_note`` to summarise winners and losers.

    The same rule applies to ``uncertainty``: the dict is populated
    automatically from the source model's ``UncertaintyReport`` (mean,
    std, p05/p25/p50/p75/p95). The LLM only authors
    ``uncertainty_note`` — a short qualitative interpretation of how
    wide that band is and what it implies for decision-making.
    """

    variable: str
    value: str
    unit: str | None = None
    source_model_id: str
    narrative: str = ""
    reliability_note: str = ""
    regional_distribution: dict[str, float] | None = None
    sectoral_distribution: dict[str, float] | None = None
    distribution_note: str = ""
    native_regional_records: list[dict] = Field(default_factory=list)
    uncertainty: dict[str, float] | None = Field(
        default=None,
        description=(
            "Per-output-key uncertainty estimate from the source model "
            "(populated from UncertaintyReport: mean, std, p05, p25, "
            "p50, p75, p95). Authored by the executor, not the LLM."
        ),
    )
    uncertainty_note: str = Field(
        default="",
        description=(
            "1-2 sentence qualitative interpretation of the uncertainty "
            "band. Authored by the LLM; no numeric fabrication."
        ),
    )


class ScopedSynthesis(BaseModel):
    """Synthesis for a specific (time_horizon, outcome_scope) pair."""

    time_horizon: TimeHorizon
    outcome_scope: OutcomeScope
    outcomes: list[SynthesizedOutcome] = Field(default_factory=list)


class UncertaintyInterpretation(BaseModel):
    """LLM-authored interpretation of a scenario's uncertainty profile.

    Produced by a dedicated synthesis LLM call that is given (a) the
    per-outcome uncertainty bands extracted from each model's
    UncertaintyReport and (b) the scenario narrative, and asked to
    explain what the spread means for decision-making — without
    fabricating any numbers of its own.
    """

    summary: str = Field(
        default="",
        description=(
            "2-4 sentence overall reading of the scenario's uncertainty: "
            "are the tails wide or narrow, are they driven by a few "
            "models or many, are macro outcomes more or less uncertain "
            "than commodity outcomes."
        ),
    )
    high_confidence_findings: list[str] = Field(
        default_factory=list,
        description=(
            "Outcomes whose p05-p95 band is tight enough that an "
            "analyst can plan against the central estimate. Each entry "
            "names the variable and source model verbatim."
        ),
    )
    low_confidence_findings: list[str] = Field(
        default_factory=list,
        description=(
            "Outcomes whose band spans a decision-relevant threshold "
            "(e.g. recession vs. soft landing). Treat the central "
            "estimate as one draw among many."
        ),
    )
    decision_implications: str = Field(
        default="",
        description=(
            "How an analyst should weight this scenario's findings "
            "given the uncertainty profile. e.g. 'lean on commodity-tier "
            "results; treat macro CGE GDP impacts as illustrative.'"
        ),
    )


class ScenarioSynthesis(BaseModel):
    """Complete synthesis for a single scenario."""

    scenario_id: Scenario
    scenario_label: str
    sections: list[ScopedSynthesis] = Field(default_factory=list)
    failed_models: list[str] = Field(default_factory=list)
    consistency_warnings: list[str] = Field(default_factory=list)
    uncertainty_method: str = Field(
        default="none",
        description=(
            "UncertaintyMethod value applied to this scenario's models "
            "('native', 'perturbation', 'bootstrap', 'none'). Mixed "
            "methods across models report 'mixed'."
        ),
    )
    uncertainty_interpretation: UncertaintyInterpretation | None = Field(
        default=None,
        description=(
            "LLM-authored qualitative reading of the scenario's "
            "uncertainty bands. None when UQ is disabled."
        ),
    )


class FullSynthesis(BaseModel):
    """Complete synthesis across all scenarios."""

    scenarios: list[ScenarioSynthesis] = Field(default_factory=list)
    cross_scenario_notes: str = ""
