"""Tests for the deterministic (LLM-free) baseline runner and its baseline file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.run_deterministic_baseline import (  # noqa: E402
    baseline_parameter_sets,
    load_baseline,
    main,
    run_baseline,
)

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "configs" / "baselines" / "hormuz_2026_analyst.yaml"
# NEMS's output-ingestion mapping covers the four matrix scenarios only, so
# its tail-risk cell fails validation in every run, LLM-driven or not.
KNOWN_INVALID = {("infrastructure_collapse", "nems")}


def test_baseline_covers_full_grid_and_validates():
    from src.models.registry import build_default_registry, default_config_dir
    from src.parameters.model_specs import ALL_MODEL_SPECS

    baseline = load_baseline(BASELINE)
    assert set(baseline["models"]) == set(ALL_MODEL_SPECS)
    assert [s["scenario_id"] for s in baseline["scenarios"]] == [
        "swift_contained", "prolonged_contained", "swift_escalated", "prolonged_escalated", "infrastructure_collapse",
    ]
    cells = baseline_parameter_sets(baseline)
    assert len(cells) == 5 * len(ALL_MODEL_SPECS)
    registry = build_default_registry(default_config_dir())
    invalid = set()
    for sid, mid, params in cells:
        assert params["scenario_id"] == sid
        adapter = registry.get(mid)
        assert adapter is not None, mid
        if not adapter.validate_inputs(params).valid:
            invalid.add((sid, mid))
    assert invalid == KNOWN_INVALID


def test_parameter_sets_merge_default_and_overrides():
    baseline = {
        "scenarios": [{"scenario_id": "swift_contained"}, {"scenario_id": "prolonged_contained"}],
        "models": {
            "m": {"default": {"a": 1, "nested": {"x": 1, "y": 2}},
                  "by_scenario": {"prolonged_contained": {"a": 2, "nested": {"y": 3}}}},
            "only_default": {"default": {"k": 0}},
            "no_default": {"by_scenario": {"swift_contained": {"z": 9}}},
        },
    }
    cells = {(s, m): p for s, m, p in baseline_parameter_sets(baseline)}
    assert cells[("swift_contained", "m")] == {"a": 1, "nested": {"x": 1, "y": 2}, "scenario_id": "swift_contained"}
    assert cells[("prolonged_contained", "m")] == {"a": 2, "nested": {"x": 1, "y": 3}, "scenario_id": "prolonged_contained"}
    assert ("prolonged_contained", "only_default") in cells
    assert ("prolonged_contained", "no_default") not in cells and ("swift_contained", "no_default") in cells
    assert [m for s, m, _ in baseline_parameter_sets(baseline, model_ids=["m"])] == ["m", "m"]


@pytest.mark.parametrize("forwarding", [True, False])
def test_run_baseline_end_to_end_subset(tmp_path, forwarding):
    models = ["poles_jrc", "fed_oil", "pycge", "world_helium_model", "argonne_abm", "ggm"]
    summary = run_baseline(
        BASELINE, "bl_test", output_root=tmp_path, scenario_ids=["swift_contained"], model_ids=models,
        apply_forwarding=forwarding, export=True,
    )
    assert summary["llm_calls"] == 0 and summary["synthesis_method"] == "templated"
    assert summary["cells"]["parameter_sets"] == 6 and summary["cells"]["model_records"] == 6
    assert summary["cells"]["completed"] == 5 and summary["cells"]["skipped"] == 1  # ggm needs a GAMS config
    assert summary["clean_synthesis"] is True
    assert summary["fidelity_strict_match_rate"] == 1.0
    assert summary["upstream_forwarding"] is forwarding
    assert set(summary["stage_seconds"]) >= {"scenario_generation_seconds", "parameter_extraction_seconds",
                                             "model_execution_seconds", "synthesis_seconds", "export_seconds"}

    state = tmp_path / "data" / "pipeline_state"
    report = tmp_path / "data" / "reports" / "bl_test"
    scen = json.loads((state / "bl_test_scenarios.json").read_text())
    assert scen["scenarios_validated"] is True and scen["config"]["llm"]["provider"] == "none"
    assert scen["validation_mode"] == "analyst_authored_baseline"
    params = [json.loads(p.read_text()) for p in sorted(state.glob("bl_test_params_*.json"))]
    assert len(params) == 6 and all(p["validation_status"] == "approved" and p["source"] == "analyst_baseline" for p in params)
    records = {json.loads(p.read_text())["model_id"]: json.loads(p.read_text()) for p in state.glob("bl_test_model_baseline_*.json")}
    assert set(records) == set(models)
    assert records["poles_jrc"]["status"] == "completed" and records["poles_jrc"]["manifest_name"] == "models_baseline"
    assert records["poles_jrc"]["implementation_mode"] == "analytical_reduction"
    abm = records["argonne_abm"]
    if forwarding:
        assert abm.get("upstream_overrides"), "argonne_abm should receive helium-model overrides"
        assert {o["source_model_id"] for o in abm["upstream_overrides"]} == {"world_helium_model"}
        fed = records["fed_oil"]
        assert any(o["name"] == "oil_price_change_pct" for o in fed.get("upstream_overrides") or [])
    else:
        assert not abm.get("upstream_overrides") and not records["fed_oil"].get("upstream_overrides")

    synth = json.loads((state / "bl_test_synthesis.json").read_text())
    assert synth["synthesis_method"] == "templated" and synth["context_budget_summary"]["sections_failed"] == 0
    assert synth["run_health"]["clean_synthesis"] is True
    assert synth["run_health"]["wall_clock"]["stages"]["model_execution_seconds"] >= 0
    outcomes = synth["synthesis_results"]
    assert outcomes and all(o["fidelity_status"] == "exact" for o in outcomes)
    assert {o["source_model_id"] for o in outcomes} == {"poles_jrc", "fed_oil", "pycge", "world_helium_model", "argonne_abm"}
    for name in ("synthesis.json", "summary.json", "synthesis.md", "swift_contained.md", "fidelity.json", "baseline_run.json"):
        assert (report / name).exists(), name
    assert (report / "csv" / "quantitative_results.csv").exists() and (report / "csv" / "model_status.csv").exists()
    assert json.loads((report / "summary.json").read_text())["clean_synthesis"] is True
    assert json.loads((report / "fidelity.json").read_text())["summary"]["strict_match_rate"] == 1.0


def test_main_cli(tmp_path):
    rc = main(["--baseline", str(BASELINE), "--run-id", "cli", "--output-root", str(tmp_path),
               "--scenarios", "swift_contained", "--models", "poles_jrc", "--no-export"])
    assert rc == 0
    assert (tmp_path / "data" / "reports" / "cli" / "baseline_run.json").exists()
    assert not (tmp_path / "data" / "reports" / "cli" / "csv").exists()
