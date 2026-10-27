"""Tests for the extended provenance chain and the trace CLI loaders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.trace_provenance import (  # noqa: E402
    build_state_from_report_dir,
    build_state_from_state_dir,
    main as trace_main,
)
from src.common.types import ConfidenceLevel, ModelExecutionStatus, Scenario  # noqa: E402
from src.interface.provenance import (  # noqa: E402
    ProvenanceTracker,
    find_narrative_sentences,
    render_chain_markdown,
    split_sentences,
)
from src.pipeline.state import (  # noqa: E402
    ModelExecutionResult,
    ModelParameterSet,
    ParameterValue,
    PipelineState,
    ScenarioNarrativeState,
    SynthesisResult,
)

NARRATIVE = (
    "Iranian forces mine the Strait on 28 February 2026. The closure removes 20.5 mb/d of "
    "crude from the market and the LLM assumes a 25% oil price shock. Naval escorts reopen "
    "the Strait after 5 weeks. Desalination plants are not attacked."
)


def _state() -> PipelineState:
    return PipelineState(
        run_id="run-P",
        scenario_narratives=[ScenarioNarrativeState(scenario_id=Scenario.C, label="Swift Escalated", narrative=NARRATIVE)],
        parameter_sets=[ModelParameterSet(
            scenario_id=Scenario.C, model_id="fed_oil",
            parameters=[
                ParameterValue(name="oil_price_change_pct", value=58.25, unit="%", confidence=ConfidenceLevel.LOW,
                               extraction_note="replaced by upstream"),
                ParameterValue(name="shock_type", value="supply", confidence=ConfidenceLevel.HIGH),
                ParameterValue(name="disruption_duration_quarters", value=1.0, unit="quarters"),
            ],
        )],
        execution_results=[
            ModelExecutionResult(scenario_id=Scenario.C, model_id="fed_oil", status=ModelExecutionStatus.COMPLETED,
                                 runtime_seconds=0.002, implementation_mode="analytical_reduction",
                                 outputs={"oil_price_change_pct": 58.25, "peak_gdp_impact_pct": -0.6553,
                                          "_upstream_overrides": [{
                                              "name": "oil_price_change_pct", "target_key": None, "llm_value": 25.0,
                                              "computed_value": 58.25, "source_model_id": "poles_jrc",
                                              "source_field": "peak_price_change_pct", "transform": "identity",
                                              "deviation_pct": 79.93}]}),
            ModelExecutionResult(scenario_id=Scenario.C, model_id="poles_jrc", status=ModelExecutionStatus.COMPLETED,
                                 outputs={"peak_price_change_pct": 58.25}),
        ],
        synthesis_results=[SynthesisResult(
            scenario_id=Scenario.C, time_horizon="short_run", outcome_scope="macro",
            outcome_variable="oil_price_change_pct", value="58.25", source_model_id="fed_oil",
            narrative_summary="The oil price is expected to increase by 58.25%.")],
    )


def test_sentence_utilities():
    sents = split_sentences(NARRATIVE)
    assert len(sents) == 4
    assert find_narrative_sentences(NARRATIVE, "oil_price_change_pct", 25.0) == [sents[1]]
    assert find_narrative_sentences(NARRATIVE, "supply_loss_mbd", 20.5) == [sents[1]]
    # Keyword fallback when the value is not stated numerically.
    assert find_narrative_sentences(NARRATIVE, "desalination_capacity_loss_pct", 0.0) == [sents[3]]


def test_trace_populates_every_link():
    rec = ProvenanceTracker(_state()).trace(Scenario.C, "fed_oil", "oil_price_change_pct")
    assert rec.chain_complete and rec.chain_links == {"narrative": True, "parameters": True, "model_run": True, "synthesis": True}
    assert rec.synthesized_value == 58.25 and rec.implementation_mode == "analytical_reduction"
    assert rec.parameter_confidence["oil_price_change_pct"] == "low"
    assert rec.parameter_validation_status == "pending"
    o = rec.upstream_overrides[0]
    assert (o.llm_value, o.computed_value, o.source_model_id, o.flagged, o.source_ran_in_run) == (25.0, 58.25, "poles_jrc", True, True)
    # The narrative sentence is found through the LLM-extracted value (25%), not the forwarded 58.25.
    assert "25% oil price shock" in rec.narrative_sentences["oil_price_change_pct"][0]
    assert rec.synthesis_outcomes[0]["value"] == "58.25"
    md = render_chain_markdown(rec)
    for row in ("1. Scenario narrative", "2. Extracted parameters", "3. Adapter inputs", "4. Model output", "5. Synthesis"):
        assert row in md
    assert "LLM-extracted 25 -> upstream 58.25" in md and "flagged at 50%" in md and "(complete)" in md


def test_trace_marks_missing_links():
    state = _state()
    state.synthesis_results = []
    state.scenario_narratives = []
    rec = ProvenanceTracker(state).trace(Scenario.C, "fed_oil", "oil_price_change_pct")
    assert not rec.chain_complete
    assert rec.chain_links["synthesis"] is False and rec.chain_links["narrative"] is False
    assert "_no synthesis outcome cites" in render_chain_markdown(rec)


def _write_state_files(sd: Path, run_id: str = "run-S") -> None:
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"{run_id}_scenarios.json").write_text(json.dumps({
        "scenario_narratives": [{"scenario_id": "swift_escalated", "label": "C", "narrative": NARRATIVE,
                                 "quantitative_assumptions": {"oil_price_shock": "25%"}, "validation_status": "approved"}]}))
    (sd / f"{run_id}_params_3.json").write_text(json.dumps({
        "scenario_id": "swift_escalated", "model_id": "fed_oil", "status": "completed", "validation_status": "approved",
        "parameters": [{"name": "oil_price_change_pct", "value": 25.0, "unit": "%", "confidence": "medium", "extraction_note": None}]}))
    (sd / f"{run_id}_model_macro_2.json").write_text(json.dumps({
        "scenario_id": "swift_escalated", "model_id": "fed_oil", "status": "completed", "runtime_seconds": 0.01,
        "implementation_mode": "analytical_reduction",
        "outputs": {"oil_price_change_pct": 58.25, "_upstream_overrides": [{"name": "oil_price_change_pct", "llm_value": 25.0,
                    "computed_value": 58.25, "source_model_id": "poles_jrc", "source_field": "peak_price_change_pct",
                    "transform": "identity", "deviation_pct": 79.93}]}}))
    (sd / f"{run_id}_model_commodity_9.json").write_text(json.dumps({
        "scenario_id": "swift_escalated", "model_id": "poles_jrc", "status": "completed", "outputs": {"peak_price_change_pct": 58.25}}))
    (sd / f"{run_id}_synthesis.json").write_text(json.dumps({"synthesis_results": [{
        "scenario_id": "swift_escalated", "time_horizon": "short_run", "outcome_scope": "macro",
        "outcome_variable": "oil_price_change_pct", "value": "58.25", "source_model_id": "fed_oil",
        "narrative_summary": "Oil rises 58.25%."}], "consistency_flags": []}))


def test_build_state_from_state_dir_and_cli(tmp_path):
    sd = tmp_path / "state"
    _write_state_files(sd)
    state = build_state_from_state_dir("run-S", sd)
    assert len(state.scenario_narratives) == 1 and len(state.parameter_sets) == 1
    assert {r.model_id for r in state.execution_results} == {"fed_oil", "poles_jrc"}
    assert state.parameter_sets[0].validation_status.value == "approved"
    out = tmp_path / "docs"
    rc = trace_main(["--run-id", "run-S", "--scenario", "swift_escalated", "--model", "fed_oil",
                     "--variable", "oil_price_change_pct", "--state-dir", str(sd), "--out-dir", str(out)])
    assert rc == 0
    rec = json.loads((out / "provenance_run-S_swift_escalated_fed_oil_oil_price_change_pct.json").read_text())
    assert rec["chain_links"] == {"narrative": True, "parameters": True, "model_run": True, "synthesis": True}
    assert rec["upstream_overrides"][0]["flagged"] is True
    md = (out / "provenance_run-S_swift_escalated_fed_oil_oil_price_change_pct.md").read_text()
    assert "analyst validation: approved" in md


def test_build_state_from_report_dir(tmp_path):
    report = tmp_path / "run-R"
    (report / "csv").mkdir(parents=True)
    (report / "synthesis.json").write_text(json.dumps({
        "synthesis_results": [{"scenario_id": "swift_escalated", "time_horizon": "short_run", "outcome_scope": "macro",
                               "outcome_variable": "oil_price_change_pct", "value": "58.25", "source_model_id": "fed_oil",
                               "narrative_summary": "Oil rises 58.25%."}],
        "consistency_flags": [{"scenario_id": "swift_escalated", "model_a_id": "fed_oil", "model_b_id": "poles_jrc",
                               "variable": "oil_price_change_pct", "value_a": 25.0, "value_b": 58.25, "tolerance_pct": 50.0,
                               "deviation_pct": 79.93, "message": "LLM-extracted vs upstream-computed disagreement ..."}]}))
    (report / "csv" / "model_status.csv").write_text(
        "scenario_id,model_id,status,runtime_seconds,error_message,implementation_mode\n"
        "swift_escalated,fed_oil,completed,0.01,,\nswift_escalated,poles_jrc,completed,0.01,,\n")
    (report / "csv" / "quantitative_results.csv").write_text(
        "scenario_id,model_id,output_key,value_numeric,value_raw,is_numeric\n"
        "swift_escalated,fed_oil,oil_price_change_pct,58.25,58.25,true\n")
    state = build_state_from_report_dir("run-R", report)
    rec = ProvenanceTracker(state).trace(Scenario.C, "fed_oil", "oil_price_change_pct")
    assert rec.chain_links == {"narrative": False, "parameters": False, "model_run": True, "synthesis": True}
    assert rec.upstream_overrides[0].computed_value == 58.25 and rec.upstream_overrides[0].source_ran_in_run is True
