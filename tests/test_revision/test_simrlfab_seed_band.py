"""SimRLFab seed override and the seed-band analysis."""

from __future__ import annotations

import json
import sys
import types

from scripts.revision import simrlfab_seed_band as band


def test_seed_reaches_driver_inputs(tmp_path):
    from src.models.helium.simrlfab import SimRLFabAdapter, SimRLFabConfig

    cfg = SimRLFabConfig(simrlfab_repo_path=tmp_path, seed=13)
    d = SimRLFabAdapter(cfg).translate_inputs_to_dict({"helium_supply_reduction_pct": 9.0})
    assert d["seed"] == 13
    assert SimRLFabAdapter(SimRLFabConfig(simrlfab_repo_path=tmp_path)).translate_inputs_to_dict({})["seed"] is None


def test_driver_patch_sets_seed(monkeypatch):
    from src.models.helium import simrlfab_driver as drv

    ie = types.ModuleType("production.envs.initialize_env")

    def extend(p):
        p.update({"NUM_MACHINES": 8, "NUM_SOURCES": 3, "MTBF": [1000.0] * 8, "MTOL": [200.0] * 8})

    ie.extend_production_parameters = extend
    ie.extend_agent_parameters = lambda p: p
    envs = types.ModuleType("production.envs")
    envs.initialize_env = ie
    prod = types.ModuleType("production")
    prod.envs = envs
    monkeypatch.setitem(sys.modules, "production", prod)
    monkeypatch.setitem(sys.modules, "production.envs", envs)
    monkeypatch.setitem(sys.modules, "production.envs.initialize_env", ie)

    applied = drv._install_overrides({"machine_mtbf_overrides": {"0": 910.0}}, "FIFO", None, seed=17)
    p = {"SEED": 10}
    ie.extend_production_parameters(p)
    assert p["SEED"] == 17 and p["MTBF"][0] == 910.0 and applied["seed"] == 17

    ie.extend_production_parameters = extend  # the driver patches once per process
    drv._install_overrides({}, "FIFO", None)  # no seed: upstream SEED kept
    p = {"SEED": 10}
    ie.extend_production_parameters(p)
    assert p["SEED"] == 10


def _record(scenario, he, mtbf):
    return {
        "model_id": "simrlfab", "scenario_id": scenario, "status": "completed",
        "metadata": {"episodes_requested": 50, "timesteps_per_episode": 100, "agent_type": "FIFO"},
        "outputs": {
            "machines_working": 0.8,
            "applied_overrides": {"machine_mtbf_overrides": {"0": mtbf}, "machine_mtol_overrides": {"0": 200.0},
                                  "mtog_per_source": 10.0},
            "_upstream_overrides": [{"name": "helium_supply_reduction_pct", "computed_value": he}],
        },
    }


def test_cells_pair_with_controls_and_summarise(tmp_path):
    (tmp_path / "r_model_commodity_downstream_0.json").write_text(json.dumps(_record("d", 9.0, 910.0)))
    (tmp_path / "r_model_commodity_downstream_1.json").write_text(json.dumps({"model_id": "opencge"}))
    cells = band.load_cells(tmp_path, "r")
    assert len(cells) == 1 and cells[0]["helium_supply_reduction_pct"] == 9.0

    s_key = band.config_key(band.driver_config(cells[0], 0, False))
    c_key = band.config_key(band.driver_config(cells[0], 0, True))
    assert s_key != c_key
    assert band.driver_config(cells[0], 0, True)["simrlfab_overrides"]["machine_mtbf_overrides"] == {}

    seeds = [10, 11, 12]
    draws = {
        s_key: {sd: {k: 0.70 + 0.01 * i for k in band.KPIS} for i, sd in enumerate(seeds)},
        c_key: {sd: {k: 0.80 + 0.01 * i for k in band.KPIS} for i, sd in enumerate(seeds)},
    }
    rows = band.summarise(cells, draws, seeds)
    r = next(x for x in rows if x["kpi"] == "machines_working")
    assert abs(r["paired_diff_mean"] + 0.10) < 1e-12
    assert r["paired_diff_sd"] < 1e-12 and r["diff_exceeds_2se"] is True
    band.write_outputs(rows, [{"config": "d", "seed": 10, **draws[s_key][10]}], tmp_path / "out",
                       {"run_id": "r", "seeds": seeds, "errors": []})
    assert "| d |" in (tmp_path / "out" / "simrlfab_seed_band.md").read_text()


def test_arms_split_helium_and_neon_machines():
    cell = {"scenario_id": "d", "episodes": 70, "timesteps": 100, "agent_type": "FIFO", "mtog": 10.0,
            "mtbf": {"0": 910.0, "1": 910.0, "2": 910.0, "3": 700.0, "4": 700.0},
            "mtol": {"0": 218.0, "1": 218.0, "2": 218.0, "3": 260.0, "4": 260.0}}
    he = band.driver_config(cell, 10, "helium_only")["simrlfab_overrides"]
    ne = band.driver_config(cell, 10, "neon_only")["simrlfab_overrides"]
    assert set(he["machine_mtbf_overrides"]) == {"0", "1", "2"}
    assert set(ne["machine_mtbf_overrides"]) == {"3", "4"}
    # Overrides equal to SimRLFab's defaults collapse onto the control config.
    flat = dict(cell, mtbf={str(i): 1000.0 for i in range(5)}, mtol={str(i): 200.0 for i in range(5)})
    keys = {band.config_key(band.driver_config(flat, 10, a)) for a in band.ARMS}
    assert len(keys) == 1


def test_parse_seeds():
    assert band.parse_seeds("10-12,20") == [10, 11, 12, 20]
