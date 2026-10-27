"""Tests for the run-level health assessment (clean-synthesis definition)."""

from __future__ import annotations

import json

from src.synthesis.run_health import (
    CLEAN_SYNTHESIS_DEFINITION,
    assess_run,
    load_run_inputs,
    render_checkpoint_markdown,
    stage_span_seconds,
)


def _models():
    return [
        {"scenario_id": "swift_contained", "model_id": "fed_oil", "status": "completed", "runtime_seconds": 0.5,
         "started_at": "2026-05-04T23:40:00+00:00", "completed_at": "2026-05-04T23:40:01+00:00", "manifest_name": "models_macro"},
        {"scenario_id": "swift_contained", "model_id": "ggm", "status": "skipped", "error_message": "Not yet implemented: requires a GGMConfig",
         "started_at": "2026-05-04T23:39:00+00:00", "completed_at": "2026-05-04T23:39:01+00:00", "manifest_name": "models_commodity"},
        {"scenario_id": "prolonged_contained", "model_id": "fed_oil", "status": "completed", "runtime_seconds": 1.5,
         "started_at": "2026-05-04T23:41:00+00:00", "completed_at": "2026-05-04T23:41:03+00:00", "manifest_name": "models_macro"},
    ]


def _scenarios(validated=True):
    return {"scenarios_validated": validated, "config": {"llm": {"provider": "vllm", "model": "gpt-oss-120b"}},
            "scenario_narratives": [{"scenario_id": "swift_contained"}, {"scenario_id": "prolonged_contained"}]}


def _synthesis(failed=0, outcomes_scenarios=("swift_contained", "prolonged_contained")):
    return {
        "synthesis_validated": True,
        "synthesis_results": [{"scenario_id": s, "outcome_variable": "x", "value": "1"} for s in outcomes_scenarios],
        "context_budget_summary": {"section_calls": 12, "sections_failed": failed},
        "context_budget_events": [{"status": "failed", "error": "LengthFinishReasonError"}] * failed,
    }


def test_clean_synthesis_true():
    a = assess_run("r", synthesis_state=_synthesis(), model_results=_models(),
                   param_results=[{"validation_status": "approved", "runtime_seconds": 2.0}] * 3,
                   scenarios_state=_scenarios(), n_model_specs=34)
    assert a["clean_synthesis"] is True
    assert a["clean_synthesis_definition"] == CLEAN_SYNTHESIS_DEFINITION
    assert a["backend"]["model"] == "gpt-oss-120b"
    assert a["cells"] == {"parameter_sets": 3, "parameter_sets_failed": 0, "model_records": 3, "completed": 2, "failed": 0, "skipped": 1}
    assert a["denominators"]["grid"] == 68
    wc = a["wall_clock"]
    assert wc["stages"]["model_execution_runtime_sum_seconds"] == 2.0
    assert wc["stages"]["model_execution_span_seconds"] == 123.0
    assert wc["stages"]["model_tier_span_seconds[models_macro]"] == 63.0
    assert wc["stages"]["parameter_extraction_llm_seconds"] == 6.0
    assert wc["seconds_per_completed_model_run"] == 1.0
    assert wc["analyst_review_seconds"] == 0.0 and wc["review_mode"] == "auto_approved"
    assert a["checkpoints"]["parameters_validation_status"] == {"approved": 3}
    assert a["failure_reasons"]["model_skip_classes"] == {"missing_config": 1}


def test_clean_synthesis_false_when_sections_failed_or_scenario_uncovered():
    a = assess_run("r", synthesis_state=_synthesis(failed=7), model_results=_models(), scenarios_state=_scenarios())
    assert a["clean_synthesis"] is False
    assert a["failure_reasons"]["synthesis_section_errors"] == {"LengthFinishReasonError": 7}
    b = assess_run("r", synthesis_state=_synthesis(outcomes_scenarios=("swift_contained",)), model_results=_models(),
                   scenarios_state=_scenarios())
    assert b["clean_synthesis"] is False
    assert b["criteria"]["scenarios_with_completed_model_and_outcome"] == 1
    c = assess_run("r", synthesis_state=_synthesis(), model_results=_models(), scenarios_state=_scenarios(),
                   bash_failures=[{"stage": "stonybrook_ai_cluster_04_synthesis"}])
    assert c["clean_synthesis"] is False


def test_clean_synthesis_undetermined_without_section_telemetry_and_false_without_state():
    s = _synthesis()
    del s["context_budget_summary"]
    a = assess_run("r", synthesis_state=s, model_results=_models(), scenarios_state=_scenarios())
    assert a["clean_synthesis"] is None
    b = assess_run("r", synthesis_state=None, model_results=_models(), scenarios_state=_scenarios(validated=False))
    assert b["clean_synthesis"] is False
    assert b["wall_clock"]["review_mode"] == "interactive" and b["wall_clock"]["analyst_review_seconds"] is None


def test_stage_span_and_checkpoint_markdown():
    assert stage_span_seconds([{"started_at": "2026-01-01T00:00:00+00:00", "completed_at": "2026-01-01T00:00:10+00:00"}]) == 10.0
    assert stage_span_seconds([{"started_at": None}]) is None
    a = assess_run("r", synthesis_state=_synthesis(), model_results=_models(), scenarios_state=_scenarios(),
                   param_results=[{"validation_status": "approved"}])
    md = render_checkpoint_markdown([a])
    assert "| `r` | gpt-oss-120b | True | True | approved: 1 | True | 0.0 |" in md


def test_load_run_inputs_prefers_state_and_falls_back_to_report(tmp_path):
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "r_scenarios.json").write_text(json.dumps(_scenarios()))
    (sd / "r_model_macro_0.json").write_text(json.dumps(_models()[0]))
    (sd / "r_params_0.json").write_text(json.dumps({"validation_status": "approved"}))
    report = tmp_path / "report"
    (report / "csv").mkdir(parents=True)
    (report / "synthesis.json").write_text(json.dumps({**_synthesis(), "bash_failures": [{"stage": "x_02_parameters"}]}))
    inputs = load_run_inputs("r", sd, report)
    assert inputs["scenarios_state"]["config"]["llm"]["model"] == "gpt-oss-120b"
    assert len(inputs["model_results"]) == 1 and len(inputs["param_results"]) == 1
    assert inputs["synthesis_state"]["context_budget_summary"]["sections_failed"] == 0
    assert inputs["bash_failures"] == [{"stage": "x_02_parameters"}]
