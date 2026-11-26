"""Robustness checks ported from AgResilience: ladder, LHS / first-order index, open-loop gap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "revision"))

import elasticity_lhs  # noqa: E402
import open_loop_gap  # noqa: E402
import robustness_common as rc  # noqa: E402
import zero_shock_ladder as zsl  # noqa: E402


# ------------------------------------------------------------- common

def test_latin_hypercube_hits_every_stratum_once():
    draws = rc.latin_hypercube(50, ["a", "b"], 0.5, 1.5, seed=1)
    assert len(draws) == 50
    for name in ("a", "b"):
        strata = sorted(int((d[name] - 0.5) / 1.0 * 50) for d in draws)
        assert strata == list(range(50))
    assert draws == rc.latin_hypercube(50, ["a", "b"], 0.5, 1.5, seed=1)


def test_first_order_recovers_known_split():
    import numpy as np

    rng = np.random.default_rng(0)
    x1, x2 = rng.random(4000), rng.random(4000)
    y = 3.0 * x1 + 1.0 * x2  # Var shares 9/10 and 1/10
    assert rc.first_order(x1, y) == pytest.approx(0.9, abs=0.03)
    assert rc.first_order(x2, y) == pytest.approx(0.1, abs=0.03)
    assert np.isnan(rc.first_order([1, 2], [3, 4]))


def test_constant_override_restores():
    from src.models.macro import macro_kernel

    original = macro_kernel.GDP_ELASTICITY_TO_OIL_PCT
    knobs = [{"name": "g", "kind": "constant", "module": "src.models.macro.macro_kernel",
              "attribute": "GDP_ELASTICITY_TO_OIL_PCT"}]
    with rc.ConstantOverride(knobs, {"g": 2.0}):
        assert macro_kernel.GDP_ELASTICITY_TO_OIL_PCT == pytest.approx(2 * original)
    assert macro_kernel.GDP_ELASTICITY_TO_OIL_PCT == original


def test_mapping_override_scales_forwarding_elasticity_only_in_copy():
    from src.pipeline.upstream_forwarding import load_mapping

    base = load_mapping()
    knob = {"name": "e", "kind": "forwarding", "model": "apsim", "param": "fertilizer_application_reduction_pct",
            "source_index": 0, "field": "elasticity"}
    new = rc.mapping_with_overrides(base, [knob], {"e": 2.0})

    def elasticity(m):
        rule = next(r for r in m.by_model["apsim"] if r.target_param == "fertilizer_application_reduction_pct")
        return rule.sources[0].elasticity

    assert elasticity(new) == pytest.approx(2 * elasticity(base))
    assert elasticity(base) == pytest.approx(0.35)


# ------------------------------------------------------------- ladder

def test_scale_value_rules():
    assert zsl.scale_value(80.0, 0.0, 0.5) == (40.0, False)
    assert zsl.scale_value(1.5, 1.0, 2.0) == (2.0, False)
    assert zsl.scale_value(85.0, 0.0, 1.6, (0.0, 100.0)) == (100.0, True)
    assert zsl.scale_value(True, False, 0.0) == (False, False)
    assert zsl.scale_value(True, False, 0.5) == (True, False)
    assert zsl.scale_value("damaged", "intact", 0.0) == ("intact", False)
    scaled, _ = zsl.scale_value({"lng": 60.0, "fertilizer": 20.0}, 0.0, 0.5)
    assert scaled == {"lng": 30.0, "fertilizer": 10.0}
    spec, _ = zsl.scale_value({"trade_cost_multiplier": 1.4, "affected_regions": ["EU"]},
                              {"trade_cost_multiplier": 1.0, "affected_regions": None}, 0.0)
    assert spec == {"trade_cost_multiplier": 1.0, "affected_regions": ["EU"]}


def test_monotone_and_sign_helpers():
    assert zsl.is_monotone([0, 1, 2, 2, 3])
    assert zsl.is_monotone([0, -1, -3])
    assert not zsl.is_monotone([0, 2, 1])
    assert zsl.sign_consistent([1, 2, 3], 0.0)
    assert not zsl.sign_consistent([-1, 2], 0.0)


def test_ladder_on_pycge_has_zero_residual_and_is_monotone():
    spec = {"factors": [0.0, 0.5, 1.0, 1.6], "zero_tolerance_abs": 1e-4,
            "models": {"pycge": {"fields": {"oil_price_shock_pct": 0.0, "commodity_price_shocks": 0.0}}}}
    result = zsl.run_ladder(spec, rc.baseline_cells(), rc.build_registry(False),
                            {"pycge": ["gdp_impact_pct", "cpi_inflation_pct"]}, ["swift_contained"])
    assert result["zero_shock"] and all(r["passed"] for r in result["zero_shock"])
    assert all(r["monotone"] and r["sign_consistent"] for r in result["summary"])
    verdict = zsl.model_verdicts(result)[0]
    assert verdict["zero_failed"] == 0 and verdict["non_monotone"] == 0


# ------------------------------------------------------------- LHS

def test_lhs_small_run_point_control_and_ordering(tmp_path):
    spec = rc.load_yaml(rc.ROBUSTNESS_DIR / "elasticities.yaml")
    spec["models"] = ["poles_jrc", "pycge"]
    spec["outputs"] = {"pycge": ["gdp_impact_pct"]}
    spec["knobs"] = [k for k in spec["knobs"] if k["name"] in ("gdp_elasticity_oil", "oil_demand_elasticity")]
    result = elasticity_lhs.run(spec, tmp_path, rc.DEFAULT_BASELINE, n=12, use_configs=False)
    assert result["point_control_ok"]
    assert result["ordering"] and all(0.0 <= o["share_kept"] <= 1.0 for o in result["ordering"])
    band = next(b for b in result["bands"] if b["scenario_id"] == "swift_contained")
    assert band["p05"] <= band["p50"] <= band["p95"]
    assert (tmp_path / "elasticity_lhs.md").exists()


# ------------------------------------------------------------- open loop

def test_apsim_gtap_gaps_from_records(tmp_path):
    rec = {"scenario_id": "swift_contained", "model_id": "apsim_gtap", "status": "completed",
           "outputs": {"fixed_point_iterations": 3, "converged": True,
                       "arm_a": {"yield_change_pct": -1.0, "us_gro_price_pct": 0.0, "us_gro_production_pct": -0.5, "us_gdp_pct": -0.01},
                       "arm_c": {"yield_change_pct": -1.0, "us_gro_price_pct": 0.4, "us_gro_production_pct": -0.9, "us_gdp_pct": -0.012}}}
    (tmp_path / "R1_model_refilled_swift_contained_apsim_gtap.json").write_text(json.dumps(rec))
    (tmp_path / "R1_model_commodity_0.json").write_text(json.dumps({"model_id": "pycge"}))
    rows = open_loop_gap.apsim_gtap_gaps([tmp_path], None)
    by = {r["variable"]: r for r in rows}
    assert by["us_gro_price_pct"]["gap"] == pytest.approx(0.4)
    assert by["us_gro_production_pct"]["gap_pct_of_one_pass"] == pytest.approx(80.0)
    assert rows[0]["run_id"] == "R1"


def test_forwarding_ablation_changes_downstream_only():
    rows = open_loop_gap.forwarding_ablation(["poles_jrc", "world_fertilizer", "apsim", "pycge"],
                                             {"poles_jrc": ["peak_price_change_pct"], "apsim": ["mean_yield_pct_change"]},
                                             rc.DEFAULT_BASELINE, use_configs=False)
    poles = [r for r in rows if r["model_id"] == "poles_jrc"]
    assert all(r["difference"] == 0 for r in poles)
    assert any(r["forwarded_inputs"] > 0 for r in rows if r["model_id"] == "apsim")


# ------------------------------------------------------------- APSIM-GTAP sweep

import apsim_gtap_ssa  # noqa: E402


def test_ssa_design_and_edits():
    draws = apsim_gtap_ssa.design(8, 1, 0.5, 1.5)
    assert draws[0]["draw"] == "point" and set(draws[0]["multipliers"].values()) == {1.0}
    assert len(draws) == 9
    edits = apsim_gtap_ssa.parameter_edits({"esubm_chm": 0.8, "esubd_gro": 1.2})
    assert edits[0] == {"name": "esubm", "indices": ["chm", "*"], "operation": "multiply", "value": 0.8}
    assert edits[1]["name"] == "esubd" and edits[1]["indices"] == ["gro", "*"]


def test_ssa_aggregate_from_chunk_files(tmp_path):
    scen = ["a_s", "b_s"]
    draws = apsim_gtap_ssa.design(6, 2, 0.5, 1.5)
    results = []
    for d in draws:
        k = d["multipliers"]["esubm_chm"]
        for i, s in enumerate(scen):
            out = {"us_gdp_pct": -(i + 1) * k, "gulf_gdp_pct": -5.0, "us_maize_yield_change_pct": -1.0,
                   "us_gro_price_pct": 0.5, "us_chm_consumption_pct": -3.0, "converged": True,
                   "zero_shock_residual_gdp_pct": 0.0, "zero_shock_gate_passed": True}
            results.append({"case_id": f"{d['draw']}|{s}", "status": "completed", "outputs": out})
    (tmp_path / "chunk_0.json").write_text(json.dumps({"results": results}))
    (tmp_path / "chunk_0_meta.json").write_text(json.dumps(
        {"chunk": 0, "n_chunks": 1, "draws": [d["draw"] for d in draws],
         "multipliers": {str(d["draw"]): d["multipliers"] for d in draws}}))
    res = apsim_gtap_ssa.aggregate(tmp_path, tmp_path / "out", {"n": 6, "seed": 2, "low": 0.5, "high": 1.5})
    assert res["n_complete_draws"] == 6 and not res["failures"] and not res["gate_failures"]
    order = next(o for o in res["ordering"] if o["variable"] == "us_gdp_pct")
    assert order["share_kept"] == 1.0
    s1 = [r for r in res["first_order"] if r["variable"] == "us_gdp_pct" and r["knob"] == "esubm_chm"]
    assert s1 and (tmp_path / "out" / "apsim_gtap_ssa.md").exists()


def test_driver_run_case_with_fakes():
    import types

    from src.models.fertilizer import apsim_gtap_driver as drv

    def solve(req):
        loss = next((1 - i["value"] for i in req["apply"] if i["indices"].get("commodity") == "chm"), 0.0)
        return {"regions": ["usa", "wasia"], "c": -10.0 * loss}

    def extract(result, variable, region="usa", commodity="chm"):
        if variable == "consumption_change" and commodity == "chm" and region == "usa":
            return result["c"]
        return 0.0

    coupling = types.SimpleNamespace(consumption_to_nitrogen=lambda c, n0, e: n0 * (1 + e * c / 100))
    fixed_point = types.SimpleNamespace(emulator_yield=lambda: ((lambda n: n / 190.0), 190.0))
    counts = {"cache_hits": 0, "solves": 0}
    out = drv.run_case({"shocks": {"chm_output_loss_share": 0.2}}, solve, coupling, fixed_point, extract, counts)
    assert out["converged"] and out["us_maize_yield_change_pct"] == pytest.approx(-2.0)
    assert out["zero_shock_gate_passed"] and out["_execution_mode"] == "julia"


def test_first_order_ignores_round_off_variance():
    import numpy as np

    x = np.linspace(0.5, 1.5, 100)
    y = np.full(100, 15.582)
    assert np.isnan(rc.first_order(x, y))
