"""Tests for the synthesis fidelity audit and inline validator."""

from __future__ import annotations

import csv
import json
from pathlib import Path

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
from src.pipeline.config import FidelityConfig, PipelineConfig
from src.pipeline.state import ModelExecutionResult, ScenarioNarrativeState
from src.synthesis import sectioning
from src.synthesis.fidelity import (
    audit_brief,
    audit_outcome,
    audit_prose,
    audit_run,
    canonicalize_model_id,
    flatten_numeric,
    match_number,
    model_outputs_from_report_csv,
    parse_value,
    render_markdown,
    split_source_ids,
)
from src.synthesis.schemas import ScopedSynthesis, SynthesizedOutcome
from src.synthesis.synthesizer import synthesize_by_section

KNOWN = ["pycge", "mpsge_jl", "nrel", "fed_oil", "poles_jrc", "aisdb", "ais_project"]


# --------------------------------------------------------------------------- parsing


def test_parse_value_variants():
    assert [p.value for p in parse_value("54.79")] == [54.79]
    assert [p.value for p in parse_value("-0.157 %")] == [-0.157]
    assert [p.value for p in parse_value("$123.83/bbl")] == [123.83]
    labelled = parse_value("{nrel: 126.39090909090909}")
    assert labelled[0].label == "nrel" and labelled[0].value == pytest.approx(126.3909090909)
    multi = parse_value("{pycge: -0.157, mpsge_jl: -0.025}")
    assert {p.label: p.value for p in multi} == {"pycge": -0.157, "mpsge_jl": -0.025}
    assert parse_value("not available") == []
    assert [p.value for p in parse_value("1,234.5 mb/d")] == [1234.5]
    assert parse_value(None) == []
    paren = parse_value("[60.5 (mpsgel), 60.5 (pycge)]")
    assert [(p.value, p.label) for p in paren] == [(60.5, "mpsgel"), (60.5, "pycge")]
    assert parse_value("1.1869 (mpsge_jl)")[0].label == "mpsge_jl"


def test_split_and_canonicalize_source_ids():
    assert split_source_ids("pycge, mpsge_jl") == ["pycge", "mpsge_jl"]
    assert split_source_ids("`fed_oil` and poles_jrc") == ["fed_oil", "poles_jrc"]
    assert canonicalize_model_id("pycge", KNOWN) == ("pycge", "exact")
    assert canonicalize_model_id("mpse_jl", KNOWN) == ("mpsge_jl", "fuzzy")
    assert canonicalize_model_id("mpsgel", KNOWN) == ("mpsge_jl", "fuzzy")
    assert canonicalize_model_id("MPSGE-JL", KNOWN) == ("mpsge_jl", "normalized")
    assert canonicalize_model_id("completely_different", KNOWN) == (None, "none")


# --------------------------------------------------------------------------- matching


def _flat():
    return flatten_numeric({
        "peak_price_change_pct": 54.79,
        "peak_price_usd_per_bbl": 123.83,
        "baseline_price_usd_per_bbl": 80.0,
        "gdp_impact_pct": -0.157,
        "share": 0.43,
        "brent_price_path_usd_per_bbl": [126.6, 114.95],
        "regional_vars": [{"region": "US", "gdp_impact_pct": -0.7444}],
    })


def test_match_categories():
    flat = _flat()
    assert match_number(parse_value("54.79")[0], "peak_price_change_pct", flat).category == "exact"
    assert match_number(parse_value("54.8")[0], "peak_price_change_pct", flat).category == "rounded"
    m = match_number(parse_value("43")[0], "share", flat)
    assert (m.category, m.relation) == ("unit_scaled", "x100")
    m = match_number(parse_value("123.83")[0], "something_else", flat)
    assert m.category == "matched_other_key" and m.matched_key == "peak_price_usd_per_bbl"
    m = match_number(parse_value("43.83")[0], "price_increase_usd", flat)
    assert m.category == "derived_arithmetic" and m.relation == "difference"
    assert match_number(parse_value("999.9")[0], "peak_price_change_pct", flat).category == "unmatched"
    # Nested list / regional leaf values are reachable.
    assert match_number(parse_value("114.95")[0], "brent_price_path_usd_per_bbl", flat).category == "exact"
    assert match_number(parse_value("-0.7444")[0], "regional_vars", flat).category == "exact"


def test_audit_outcome_source_handling():
    outputs = {"fed_oil": {"oil_price_change_pct": 58.25, "peak_gdp_impact_pct": -0.6553,
                           "_upstream_overrides": [{"llm_value": 25.0, "computed_value": 58.25, "deviation_pct": 79.93}]},
               "poles_jrc": None}
    a = audit_outcome({"scenario_id": "swift_escalated", "outcome_variable": "oil_price_change_pct", "value": "58.25",
                       "source_model_id": "fed_oil",
                       "narrative_summary": "The oil price is expected to increase by 58.25% over 4 months.",
                       "reliability_note": "upstream value 58.25 vs LLM-extracted 25.0 (deviation: 79.9%)"},
                      outputs, KNOWN)
    assert a.category == "exact" and a.chain_complete
    assert a.prose_tokens == 5  # 58.25, 4, 58.25, 25.0, 79.9
    assert a.prose_unmatched == ["4"]
    assert a.prose_relations == {"exact": 4}
    # Malformed id repaired; value matched on the repaired model.
    outputs2 = {"mpsge_jl": {"gdp_impact_pct": -0.8695}}
    b = audit_outcome({"scenario_id": "C", "variable": "gdp_impact_pct", "value": "-0.8695", "source_model_id": "mpse_jl"},
                      outputs2, KNOWN)
    assert b.source_model_ids == ["mpsge_jl"] and b.source_canonicalization == {"mpse_jl": "mpsge_jl"}
    assert b.category == "exact"
    # Cited model did not run.
    c = audit_outcome({"scenario_id": "D", "variable": "peak_price_change_pct", "value": "51.82", "source_model_id": "poles_jrc"},
                      outputs, KNOWN)
    assert c.category == "source_not_run" and not c.chain_complete
    # Labelled dict value picks the labelled model.
    d = audit_outcome({"scenario_id": "C", "variable": "gdp_impact_pct", "value": "{mpsge_jl: -0.8695}", "source_model_id": "nrel"},
                      {"nrel": {"gdp_impact_pct": -0.4494}, "mpsge_jl": {"gdp_impact_pct": -0.8695}}, KNOWN)
    assert d.category == "exact" and d.number_matches[0].source_model_id == "mpsge_jl"
    # Unknown source id.
    e = audit_outcome({"scenario_id": "C", "variable": "x", "value": "1.5", "source_model_id": "zzz_model"}, outputs, KNOWN)
    assert e.category == "source_unknown"
    # Non-numeric value.
    f = audit_outcome({"scenario_id": "C", "variable": "status", "value": "supply", "source_model_id": "fed_oil"}, outputs, KNOWN)
    assert f.category == "non_numeric" and not f.is_numeric


def test_audit_prose_skips_years_and_counts_unit_scaled():
    total, matched, unmatched, rel = audit_prose(["In 2026 the share reached 43% versus 0.5 baseline"], [{"share": 0.43}])
    assert (total, matched, unmatched) == (2, 1, ["0.5"])
    assert rel == {"x100": 1}


def test_audit_prose_accepts_sign_drop_and_multiplier_percent_but_not_slips():
    pools = [{"gdp_impact_pct": -0.0407, "trade_cost_multiplier": 1.1869, "x": -0.8139}]
    total, matched, unmatched, rel = audit_prose(
        ["GDP declines by 0.0407% while trade costs rise 18.69%; output falls 8.139%"], pools
    )
    assert (total, matched) == (3, 2)
    assert unmatched == ["8.139"]
    assert rel == {"sign_dropped": 1, "multiplier_to_pct": 1}


def test_audit_run_summary_and_markdown():
    synthesis = [
        {"scenario_id": "A", "outcome_variable": "peak_price_change_pct", "value": "54.79", "source_model_id": "poles_jrc", "narrative_summary": "up 54.79%"},
        {"scenario_id": "A", "outcome_variable": "gdp_impact_pct", "value": "-15.7", "source_model_id": "pycge", "narrative_summary": "GDP falls 15.7%"},
        {"scenario_id": "A", "outcome_variable": "shock_type", "value": "supply", "source_model_id": "fed_oil"},
    ]
    outputs = {"A": {"poles_jrc": {"peak_price_change_pct": 54.79}, "pycge": {"gdp_impact_pct": -0.157}, "fed_oil": {"shock_type": "supply"}}}
    report = audit_run("run-F", synthesis, outputs, KNOWN)
    s = report.summary
    assert s["outcomes"] == 3 and s["numeric_outcomes"] == 2
    assert s["by_category"] == {"exact": 1, "unit_scaled": 1, "non_numeric": 1}
    assert s["strict_match_rate"] == 1.0
    md = render_markdown(report)
    assert "Synthesis fidelity audit" in md and "unit_scaled" in md


def test_model_outputs_from_report_csv(tmp_path):
    csv_dir = tmp_path / "csv"
    (csv_dir / "raw" / "swift_contained").mkdir(parents=True)
    with open(csv_dir / "model_status.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_id", "status"])
        w.writeheader()
        w.writerow({"scenario_id": "swift_contained", "model_id": "poles_jrc", "status": "completed"})
        w.writerow({"scenario_id": "swift_contained", "model_id": "ggm", "status": "skipped"})
    with open(csv_dir / "quantitative_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_id", "output_key", "value_numeric", "value_raw", "is_numeric"])
        w.writeheader()
        w.writerow({"scenario_id": "swift_contained", "model_id": "poles_jrc", "output_key": "peak_price_change_pct", "value_numeric": "54.79", "value_raw": "54.79", "is_numeric": "true"})
    with open(csv_dir / "raw" / "swift_contained" / "poles_jrc__brent_price_path_usd_per_bbl__series.csv", "w", newline="") as f:
        f.write("period,value\n0,126.6\n1,114.95\n")
    with open(csv_dir / "raw" / "swift_contained" / "poles_jrc__regional_vars.csv", "w", newline="") as f:
        f.write("region,gdp_impact_pct\nUS,-0.7\n")
    out = model_outputs_from_report_csv(csv_dir)
    assert out["swift_contained"]["ggm"] is None
    pj = out["swift_contained"]["poles_jrc"]
    assert pj["peak_price_change_pct"] == 54.79
    assert pj["brent_price_path_usd_per_bbl"] == [126.6, 114.95]
    assert pj["regional_vars.US.gdp_impact_pct"] == -0.7


def test_audit_brief_matches_indicators_to_articles():
    brief = {"week_start": "2026-03-15", "observed_indicators": [
        {"name": "brent_usd_bbl", "value": 112.4, "unit": "USD/bbl", "source": "EIA"},
        {"name": "fleet_loss_pct", "value": 40.0},
    ]}
    articles = [{"title": "Brent settles at $112.40 as closure persists", "description": "", "content": ""}]
    res = audit_brief(brief, articles)
    assert res["indicators"] == 2 and res["matched"] == 1


# --------------------------------------------------------------------------- inline validator


def _fake_llm(outcomes_by_call: list[list[SynthesizedOutcome]]):
    calls = {"n": 0}

    class _LLM:
        def with_structured_output(self, schema):
            def _invoke(value):
                messages = value.to_messages() if hasattr(value, "to_messages") else value
                text = "\n".join(getattr(m, "content", "") for m in (messages or []))
                th = next((t for t in TimeHorizon if f"time_horizon={t.value}" in text), TimeHorizon.SHORT_RUN)
                sc = next((s for s in OutcomeScope if f"outcome_scope={s.value}" in text), OutcomeScope.MICRO)
                idx = min(calls["n"], len(outcomes_by_call) - 1)
                calls["n"] += 1
                return ScopedSynthesis(time_horizon=th, outcome_scope=sc, outcomes=list(outcomes_by_call[idx]))
            return RunnableLambda(_invoke)
    return _LLM(), calls


def _one_section_setup(monkeypatch):
    meta = {"poles_jrc": sectioning.ModelMetadata("poles_jrc", CommoditySystem.OIL, AnalyticalLevel.COMMODITY)}
    monkeypatch.setattr("src.synthesis.synthesizer.lookup_model_metadata", lambda ids: {m: meta[m] for m in ids if m in meta})
    routes = [sectioning.SectionRoute(key=sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO),
                                      analytical_levels={AnalyticalLevel.COMMODITY})]
    results = [ModelExecutionResult(scenario_id=Scenario.C, model_id="poles_jrc", status=ModelExecutionStatus.COMPLETED,
                                    outputs={"peak_price_change_pct": 58.25, "peak_price_usd_per_bbl": 126.6})]
    narrative = ScenarioNarrativeState(scenario_id=Scenario.C, label="C", narrative="x")
    return routes, results, narrative


def _outcomes():
    return [
        SynthesizedOutcome(variable="peak_price_change_pct", value="58.25", source_model_id="poles_jrc"),
        SynthesizedOutcome(variable="peak_price_usd_per_bbl", value="126.6", source_model_id="poles-jrc"),
        SynthesizedOutcome(variable="made_up", value="999", source_model_id="poles_jrc"),
    ]


def test_validator_flags_and_canonicalizes(monkeypatch):
    routes, results, narrative = _one_section_setup(monkeypatch)
    llm, calls = _fake_llm([_outcomes()])
    monkeypatch.setattr("src.synthesis.synthesizer._interpret_uncertainty", lambda *a, **k: ("none", None))
    flags, synth, metrics = synthesize_by_section(
        llm, Scenario.C, narrative, results, routes=routes, fidelity_config=FidelityConfig(on_mismatch="flag")
    )
    section = next(s for s in synth.sections if s.outcomes)
    assert [o.fidelity_status for o in section.outcomes] == ["exact", "exact", "unmatched"]
    repaired = section.outcomes[1]
    assert repaired.source_model_id == "poles_jrc" and repaired.source_model_id_raw == "poles-jrc"
    fid_flags = [f for f in flags if f.model_b_id == "synthesis_llm"]
    assert len(fid_flags) == 1 and fid_flags[0].variable == "made_up"
    key = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO)
    assert metrics[key]["fidelity"]["mismatched"] == 1 and metrics[key]["fidelity"]["canonicalized_sources"] == 1
    assert calls["n"] == 1


def test_validator_blocks_unverifiable_outcomes(monkeypatch):
    routes, results, narrative = _one_section_setup(monkeypatch)
    llm, _ = _fake_llm([_outcomes()])
    monkeypatch.setattr("src.synthesis.synthesizer._interpret_uncertainty", lambda *a, **k: ("none", None))
    flags, synth, metrics = synthesize_by_section(
        llm, Scenario.C, narrative, results, routes=routes, fidelity_config=FidelityConfig(on_mismatch="block")
    )
    section = next(s for s in synth.sections if s.outcomes)
    assert [o.variable for o in section.outcomes] == ["peak_price_change_pct", "peak_price_usd_per_bbl"]
    assert any("dropped outcome 'made_up'" in w for w in synth.consistency_warnings)
    key = sectioning.SectionKey(TimeHorizon.SHORT_RUN, OutcomeScope.MICRO)
    assert metrics[key]["fidelity"]["dropped"] == 1


def test_validator_reprompts_once_and_keeps_better_answer(monkeypatch):
    routes, results, narrative = _one_section_setup(monkeypatch)
    good = [SynthesizedOutcome(variable="peak_price_change_pct", value="58.25", source_model_id="poles_jrc")]
    llm, calls = _fake_llm([_outcomes(), good])
    monkeypatch.setattr("src.synthesis.synthesizer._interpret_uncertainty", lambda *a, **k: ("none", None))
    flags, synth, metrics = synthesize_by_section(
        llm, Scenario.C, narrative, results, routes=routes,
        fidelity_config=FidelityConfig(on_mismatch="flag", reprompt_once=True),
    )
    section = next(s for s in synth.sections if s.outcomes)
    assert calls["n"] == 2
    assert [o.variable for o in section.outcomes] == ["peak_price_change_pct"]
    assert not [f for f in flags if f.model_b_id == "synthesis_llm"]


def test_validator_off_leaves_outcomes_untouched(monkeypatch):
    routes, results, narrative = _one_section_setup(monkeypatch)
    llm, _ = _fake_llm([_outcomes()])
    monkeypatch.setattr("src.synthesis.synthesizer._interpret_uncertainty", lambda *a, **k: ("none", None))
    flags, synth, metrics = synthesize_by_section(
        llm, Scenario.C, narrative, results, routes=routes, fidelity_config=FidelityConfig(on_mismatch="off")
    )
    section = next(s for s in synth.sections if s.outcomes)
    assert all(o.fidelity_status == "" for o in section.outcomes)
    assert section.outcomes[1].source_model_id == "poles-jrc"


def test_pipeline_config_carries_fidelity_defaults():
    cfg = PipelineConfig()
    assert cfg.synthesis.fidelity.enabled and cfg.synthesis.fidelity.on_mismatch == "flag"
    # Older serialized configs (no 'synthesis' key) still load.
    assert PipelineConfig(**{"llm": {"provider": "vllm"}}).synthesis.fidelity.on_mismatch == "flag"
