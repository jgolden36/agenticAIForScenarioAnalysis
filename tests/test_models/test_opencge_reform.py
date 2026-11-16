"""OpenCGE (OG-Core) reform construction.

These tests pin the parameter shapes that OG-Core 0.15.x validates
(``default_parameters.json``): ``Z`` is a 2-D float list (years x M
industries) and ``delta_annual`` is a scalar. The adapter previously sent
a flat ``Z`` list and a scalar ``delta_tau_annual``, which OG-Core rejected
with "Not a valid list." on every scenario of runs 20260504_222710 and
rev_20261102_llama8b_r2.
"""

from __future__ import annotations

import pickle
from pathlib import Path

from src.models.macro.opencge import OpenCGEAdapter, OpenCGEConfig


def _params(**over):
    p = {
        "scenario_id": "swift_contained",
        "oil_price_shock_pct": 50.0,
        "commodity_price_shocks": {"lng": 40.0, "fertilizer": 20.0},
        "disruption_duration_months": 18,
    }
    p.update(over)
    return p


def test_z_is_two_dimensional_years_by_industry():
    a = OpenCGEAdapter(OpenCGEConfig())
    out = a.translate_inputs(_params())
    z = out["reform_dict"]["Z"]
    assert len(z) == 25
    assert all(isinstance(row, list) and len(row) == 1 for row in z)
    # 18 months: a full shock year, a half-weighted year, then baseline.
    expected = (1 - 0.0008 * 50) * (1 - 0.0004 * 40) * (1 - 0.0002 * 20)
    assert abs(z[0][0] - expected) < 1e-12
    assert abs(z[1][0] - (1 + (expected - 1) * 0.5)) < 1e-12
    assert z[2] == [1.0] and z[-1] == [1.0]


def test_short_disruption_is_weighted_by_its_share_of_the_year():
    out = OpenCGEAdapter(OpenCGEConfig()).translate_inputs(
        _params(disruption_duration_months=5, commodity_price_shocks={})
    )
    z = out["reform_dict"]["Z"]
    assert abs(z[0][0] - (1 - 0.0008 * 50 * 5 / 12)) < 1e-12
    assert z[1] == [1.0] and len(z) == 25
    f = OpenCGEAdapter._duration_weighted_z
    assert f(0.9, 2.0) == [0.9, 0.9]
    assert f(0.9, 0.0) == [1.0]


def test_tax_depreciation_is_not_touched():
    out = OpenCGEAdapter(OpenCGEConfig()).translate_inputs(_params())
    assert "delta_tau_annual" not in out["reform_dict"]
    adj = out["delta_annual_adj"]
    assert abs(adj - (0.00005 * 50 + 0.00002 * 40 + 0.00001 * 20)) < 1e-12


def test_capital_drag_only_in_configured_scenarios():
    cfg = OpenCGEConfig(capital_drag_scenarios=["infrastructure_collapse"])
    a = OpenCGEAdapter(cfg)
    off = a.translate_inputs(_params(scenario_id="swift_contained"))
    on = a.translate_inputs(_params(scenario_id="infrastructure_collapse"))
    assert off["delta_annual_adj"] == 0.0 and off["capital_drag_applied"] is False
    assert all(r["delta_annual_delta"] == 0.0 for r in off["applied_shocks"].values())
    assert on["capital_drag_applied"] is True and on["delta_annual_adj"] > 0
    # The productivity path is the same either way.
    assert off["reform_dict"]["Z"] == on["reform_dict"]["Z"]


def test_shipped_yaml_restricts_capital_drag_to_infrastructure_collapse():
    from src.models.registry import _build_opencge_adapter

    root = Path(__file__).resolve().parents[2]
    a = _build_opencge_adapter(root / "configs" / "model_configs")
    assert a._config.capital_drag_scenarios == ["infrastructure_collapse"]


def test_delta_annual_update_is_baseline_plus_drag_and_clamped():
    f = OpenCGEAdapter._delta_annual_update
    assert abs(f(0.05, 0.0035) - 0.0535) < 1e-12
    assert f(0.05, -1.0) == 0.0
    assert f(0.9, 0.5) == 1.0


def test_delta_per_pct_alias():
    cfg = OpenCGEConfig(shock_to_productivity={"oil": {"Z_mult_per_pct": 0.0, "delta_per_pct": 0.001}})
    out = OpenCGEAdapter(cfg).translate_inputs(_params(commodity_price_shocks={}))
    assert abs(out["delta_annual_adj"] - 0.05) < 1e-12


def test_maxiter_follows_time_path_iter():
    out = OpenCGEAdapter(OpenCGEConfig(time_path_iter=123)).translate_inputs(_params())
    assert out["reform_dict"]["maxiter"] == 123


def test_long_disruption_uses_single_row():
    out = OpenCGEAdapter(OpenCGEConfig()).translate_inputs(_params(disruption_duration_months=400))
    assert out["reform_dict"]["Z"] == [[out["reform_dict"]["Z"][0][0]]]


def test_water_shock_has_a_yaml_mapping():
    import yaml

    raw = yaml.safe_load(Path("configs/model_configs/opencge.yaml").read_text())
    assert "water" in raw["shock_to_productivity"]


def test_baseline_complete_requires_tpi_for_tpi_runs(tmp_path):
    (tmp_path / "SS").mkdir()
    (tmp_path / "SS" / "SS_vars.pkl").write_bytes(b"x")
    assert OpenCGEAdapter._baseline_complete(tmp_path, "SS")
    assert not OpenCGEAdapter._baseline_complete(tmp_path, "TPI")
    (tmp_path / "TPI").mkdir()
    (tmp_path / "TPI" / "TPI_vars.pkl").write_bytes(b"x")
    assert OpenCGEAdapter._baseline_complete(tmp_path, "TPI")
    shared = {"start_year": 2026, "budget_balance": False, "maxiter": 200}
    # No stamp: a cache solved with unknown settings is re-solved.
    assert not OpenCGEAdapter._baseline_complete(tmp_path, "TPI", shared)
    OpenCGEAdapter._write_baseline_stamp(tmp_path, shared)
    assert OpenCGEAdapter._baseline_complete(tmp_path, "TPI", shared)
    assert not OpenCGEAdapter._baseline_complete(tmp_path, "TPI", {**shared, "start_year": 2025})


def test_steady_state_outputs_read_ogcore_short_keys(tmp_path):
    base = tmp_path / "base"
    ref = tmp_path / "ref"
    for d, c in ((base, 2.0), (ref, 1.9)):
        (d / "SS").mkdir(parents=True)
        with open(d / "SS" / "SS_vars.pkl", "wb") as f:
            pickle.dump({"Y": 10.0, "C": c, "K": 30.0, "w": 1.0, "r": 0.04}, f)
    out = OpenCGEAdapter(OpenCGEConfig())._read_outputs(base, ref)
    assert out["ss_reform"]["C"] == 1.9
    assert out["welfare_pct_change"] == -5.0


def _fake_ogcore(monkeypatch, calls):
    import sys
    import types

    class Spec:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.delta_annual = 0.05

        def update_specifications(self, d):
            self.__dict__.update(d)

    def runner(p, time_path=True, client=None):
        calls.append(p.baseline)
        raise RuntimeError("stop after the first runner call")

    ex = types.ModuleType("ogcore.execute")
    ex.runner = runner
    pa = types.ModuleType("ogcore.parameters")
    pa.Specifications = Spec
    og = types.ModuleType("ogcore")
    og.execute, og.parameters = ex, pa
    dd = types.ModuleType("dask.distributed")
    dd.LocalCluster = lambda **kw: types.SimpleNamespace(close=lambda: None)
    dd.Client = lambda c: types.SimpleNamespace(close=lambda: None)
    dk = types.ModuleType("dask")
    dk.distributed = dd
    for name, mod in {"ogcore": og, "ogcore.execute": ex, "ogcore.parameters": pa,
                      "dask": dk, "dask.distributed": dd}.items():
        monkeypatch.setitem(sys.modules, name, mod)


def test_parallel_cells_never_solve_the_shared_baseline(tmp_path, monkeypatch):
    import pytest

    calls: list = []
    _fake_ogcore(monkeypatch, calls)
    monkeypatch.setenv("HORMUZ_OPENCGE_REQUIRE_BASELINE", "1")
    a = OpenCGEAdapter(OpenCGEConfig(baseline_dir=tmp_path / "base", reform_dir=tmp_path / "ref"))
    inputs = a.translate_inputs(_params())
    inputs["baseline_dir"], inputs["reform_dir"] = str(tmp_path / "base"), str(tmp_path / "ref")
    with pytest.raises(RuntimeError, match="forbids re-solving"):
        a.execute(inputs)
    assert calls == []  # the baseline runner was never called

    # With a complete, stamped cache the cell goes straight to the reform.
    base = tmp_path / "base"
    for sub, name in (("SS", "SS_vars.pkl"), ("TPI", "TPI_vars.pkl")):
        (base / sub).mkdir(parents=True, exist_ok=True)
        (base / sub / name).write_bytes(b"x")
    shared = {k: inputs["reform_dict"][k] for k in OpenCGEAdapter._SHARED_SETTINGS if k in inputs["reform_dict"]}
    OpenCGEAdapter._write_baseline_stamp(base, shared)
    try:
        a.execute(inputs)
    except Exception:
        pass
    assert calls == [False]  # only the reform runner ran


def test_baseline_marker_blocks_a_second_solver(tmp_path, monkeypatch):
    import json
    import subprocess
    import time

    import pytest

    marker = tmp_path / OpenCGEAdapter._BASELINE_MARKER
    monkeypatch.setenv("SLURM_JOB_ID", "999")
    marker.write_text(json.dumps({"job_id": "89206", "started": time.time()}))

    def squeue(listed):
        return lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=listed, stderr="")

    monkeypatch.setattr(subprocess, "run", squeue("RUNNING\n"))
    assert "89206" in OpenCGEAdapter._live_baseline_marker(tmp_path)
    monkeypatch.setattr(subprocess, "run", squeue(""))
    assert OpenCGEAdapter._live_baseline_marker(tmp_path) is None  # job gone: stale
    marker.write_text(json.dumps({"job_id": "89206", "started": time.time() - 3 * 86400}))
    monkeypatch.setattr(subprocess, "run", squeue("RUNNING\n"))
    assert OpenCGEAdapter._live_baseline_marker(tmp_path) is None  # too old: stale

    # execute() refuses to start a baseline solve while the marker is live.
    calls: list = []
    _fake_ogcore(monkeypatch, calls)
    monkeypatch.delenv("HORMUZ_OPENCGE_REQUIRE_BASELINE", raising=False)
    marker.write_text(json.dumps({"job_id": "89206", "started": time.time()}))
    a = OpenCGEAdapter(OpenCGEConfig(baseline_dir=tmp_path, reform_dir=tmp_path / "ref"))
    inputs = a.translate_inputs(_params())
    inputs["baseline_dir"], inputs["reform_dir"] = str(tmp_path), str(tmp_path / "ref")
    with pytest.raises(RuntimeError, match="being solved by another job"):
        a.execute(inputs)
    assert calls == []

    # Without a live marker it solves, and clears its own marker afterwards.
    monkeypatch.setattr(subprocess, "run", squeue(""))
    try:
        a.execute(inputs)
    except Exception:
        pass
    assert calls == [True] and not marker.exists()


def test_uq_replicates_are_skipped_for_expensive_models(monkeypatch):
    from src.models.base import ModelOutput
    from src.models.uncertainty import UncertaintyConfig, maybe_run_with_uncertainty

    monkeypatch.delenv("HORMUZ_UQ_SKIP_MODELS", raising=False)
    calls = []

    def run(inputs):
        calls.append(inputs)
        return ModelOutput(model_id="opencge", outputs={"gdp_impact_pct": -0.5})

    cfg = UncertaintyConfig(enabled=True, method="perturbation", n_replicates=5)
    out = maybe_run_with_uncertainty(OpenCGEAdapter(), {"x": 1.0}, cfg, execute_fn=run)
    assert len(calls) == 1 and "uncertainty_skipped" in out.metadata
    monkeypatch.setenv("HORMUZ_UQ_SKIP_MODELS", "")
    calls.clear()
    maybe_run_with_uncertainty(OpenCGEAdapter(), {"x": 1.0}, cfg, execute_fn=run)
    assert len(calls) == 6


def test_regional_context_receives_percent_shocks_not_records():
    """The kernel drops non-numeric shocks; passing the per-commodity
    records made the regional context table all zeros (supplementary
    runs, November 2026)."""
    from src.models.macro.macro_kernel import compute_regional_macro_outcomes

    a = OpenCGEAdapter(OpenCGEConfig())
    applied = a.translate_inputs(_params())["applied_shocks"]
    assert all(isinstance(v, dict) for v in applied.values())

    shocks = OpenCGEAdapter._kernel_shocks(applied)
    assert shocks == {"oil": 50.0, "lng": 40.0, "fertilizer": 20.0}

    rows = compute_regional_macro_outcomes(shocks, 18.0, regime="long_run")
    us = next(r for r in rows if r["region"] == "US")
    assert us["gdp_impact_pct"] < 0
    # The raw records reproduce the old all-zero table.
    old = compute_regional_macro_outcomes(applied, 18.0, regime="long_run")
    assert all(r["gdp_impact_pct"] == 0 for r in old)
