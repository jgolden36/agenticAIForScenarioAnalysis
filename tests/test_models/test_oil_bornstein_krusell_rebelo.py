"""Tests for the Bornstein-Krusell-Rebelo Octave + Dynare adapter.

These tests stay in the validate / translate / script-generation layers
so they can run without Octave or Dynare installed.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.oil.bornstein_krusell_rebelo import (
    SECTION_MOD_MAP,
    BornsteinKrusellRebeloAdapter,
    BornsteinKrusellRebeloConfig,
)


SAMPLE_PARAMS: dict = {
    "scenario_id": "test_B",
    "supply_loss_mbd": 8.0,
    "disruption_duration_months": 12.0,
    "spr_release_mbd": 1.0,
    "opec_spare_capacity_mbd": 2.0,
    "demand_elasticity_override": 0.4,
    "frisch_elasticity": 2.0,
}


class TestBornsteinKrusellRebeloAdapter:
    def test_metadata(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        assert adapter.model_id == "bornstein_krusell_rebelo"
        assert adapter.commodity_system == CommoditySystem.OIL
        assert adapter.analytical_level == AnalyticalLevel.COMMODITY

    def test_default_section_resolves_to_known_mod_file(self) -> None:
        cfg = BornsteinKrusellRebeloConfig()
        assert cfg.section in SECTION_MOD_MAP
        assert cfg.resolve_mod_file() == SECTION_MOD_MAP[cfg.section]

    def test_explicit_mod_file_overrides_mapping(self) -> None:
        cfg = BornsteinKrusellRebeloConfig(
            section="Section 5/cartel_deviations",
            mod_file="World_Economy_Cartel_alt",
        )
        assert cfg.resolve_mod_file() == "World_Economy_Cartel_alt"

    def test_validate_accepts_canonical_params(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        result = adapter.validate_inputs(SAMPLE_PARAMS)
        assert result.valid, result.errors

    def test_validate_flags_missing_required(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        bad = {k: v for k, v in SAMPLE_PARAMS.items() if k != "spr_release_mbd"}
        result = adapter.validate_inputs(bad)
        assert not result.valid
        assert any("spr_release_mbd" in e for e in result.errors)

    def test_validate_rejects_negative_supply_loss(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        bad = {**SAMPLE_PARAMS, "supply_loss_mbd": -1.0}
        result = adapter.validate_inputs(bad)
        assert not result.valid

    def test_translate_inputs_computes_net_loss_and_variances(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        translated = adapter.translate_inputs(SAMPLE_PARAMS)
        raw = translated["raw_inputs"]
        # supply_loss=8, spr=1, opec_spare=2 => net=5
        assert raw["net_loss_mbd"] == 5.0
        assert raw["opec_loss_mbd"] + raw["non_opec_loss_mbd"] == 5.0

        shocks = translated["shock_param_overrides"]
        assert shocks["u_var"] >= 0
        assert shocks["u_no_var"] >= 0
        # Both variances should be strictly positive given a 5 mb/d net loss
        assert shocks["u_var"] + shocks["u_no_var"] > 0

    def test_translate_inputs_propagates_struct_overrides(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        translated = adapter.translate_inputs(SAMPLE_PARAMS)
        struct = translated["struct_param_overrides"]
        assert struct["epsilon"] == 0.4
        # frisch=2 -> nu = 1/2 = 0.5
        assert abs(struct["nu"] - 0.5) < 1e-9

    def test_translate_inputs_irf_horizon_grows_with_duration(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        long_disruption = {**SAMPLE_PARAMS, "disruption_duration_months": 120.0}
        translated = adapter.translate_inputs(long_disruption)
        assert translated["irf_horizon"] >= 40

    def test_override_script_writes_set_param_lines(self, tmp_path: Path) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        translated = adapter.translate_inputs(SAMPLE_PARAMS)
        mat_path = tmp_path / "calibration_parameters.mat"
        script = adapter._build_override_script(
            mat_path,
            translated["shock_param_overrides"],
            translated["struct_param_overrides"],
        )
        assert "load(" in script
        assert "shock_param.u_var" in script
        assert "shock_param.u_no_var" in script
        assert "struct_param.epsilon" in script
        assert "struct_param.nu" in script
        assert "save(" in script

    def test_run_script_addpaths_and_invokes_dynare(self, tmp_path: Path) -> None:
        cfg = BornsteinKrusellRebeloConfig(
            dynare_path=tmp_path / "dynare_root",
        )
        adapter = BornsteinKrusellRebeloAdapter(config=cfg)
        section_dir = tmp_path / "section"
        dynare_codes_dir = section_dir / "dynare_codes"
        dynare_codes_dir.mkdir(parents=True)
        override = tmp_path / "apply_overrides.m"
        override.write_text("% noop\n")
        out_json = tmp_path / "results.json"

        script = adapter._build_run_script(
            dynare_path=cfg.dynare_path,
            section_dir=section_dir,
            dynare_codes_dir=dynare_codes_dir,
            mod_basename="World_Economy_Cartel_nonopec_shocks",
            irf_horizon=24,
            output_json=out_json,
            override_script=override,
        )
        assert f"addpath('{cfg.dynare_path.as_posix()}')" in script
        assert "dynare World_Economy_Cartel_nonopec_shocks noclearall" in script
        assert "jsonencode(results)" in script
        assert out_json.as_posix() in script

    def test_summarize_irf_extracts_peak_pct(self) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        results = {
            "irfs": {
                "p_eps_u_no": [0.001, 0.005, 0.012, 0.008, 0.003],
            },
            "steady_state": [4.5, 0.0, 0.0],
            "endo_names": ["p", "I_o", "I_n"],
        }
        summary = adapter._summarize_irf(results)
        assert "oil_price_irf_eps_u_no_pct" in summary
        assert summary["oil_price_peak_pct_eps_u_no"] == 1.2
        assert "oil_price_usd" in summary

    def test_read_json_raises_when_missing(self, tmp_path: Path) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        missing = tmp_path / "results.json"
        try:
            adapter._read_json(missing)
        except RuntimeError as exc:
            assert "results JSON not found" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError for missing results.json")

    def test_read_json_returns_dict(self, tmp_path: Path) -> None:
        adapter = BornsteinKrusellRebeloAdapter()
        path = tmp_path / "r.json"
        path.write_text(json.dumps({"convergence_status": "completed"}))
        result = adapter._read_json(path)
        assert result["convergence_status"] == "completed"
