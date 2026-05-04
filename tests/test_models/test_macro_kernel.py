"""Tests for the closed-form macro kernel and its consumers.

Covers three things:

1. ``src.models.macro.macro_kernel`` golden-number tests for a reference
   30 % oil + 6-month disruption scenario, plus monotonicity properties
   (larger shock => larger absolute GDP / CPI; longer duration => larger
   welfare loss; sign flips for an oil price *drop*).

2. ``PyCGEAdapter`` analytical-MVP fallback. Exercises the path where
   ``cge_modeling`` is unavailable / has a pre-alpha API and verifies
   the adapter returns a COMPLETED ``ModelOutput`` with the
   synthesizer's standard macro schema. The cluster-MVP guarantee is
   that ``pycge`` always reports COMPLETED, never SKIPPED or FAILED,
   even when the optional cge_modeling package is missing.

3. Smoke test for ``derive_macro_from_energy_shocks`` against the
   operational shock dicts TEMOA / OSeMOSYS / MESSAGEix produce, so
   energy adapters always have macro-flavoured outputs to inject.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from src.models.base import ModelOutput
from src.models.macro.macro_kernel import (
    GLOBAL_OIL_SUPPLY_MBD,
    UNIFIED_REGIONS,
    compute_macro_outcomes,
    compute_regional_macro_outcomes,
    derive_macro_from_energy_shocks,
)
from src.models.macro.pycge import PyCGEAdapter


# ---------------------------------------------------------------------------
# Required schema every macro-tier consumer relies on
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = {
    "gdp_impact_pct",
    "gdp_growth_pct",
    "cpi_inflation_pct",
    "consumption_impact_pct",
    "welfare_pct_change",
    "wage_impact_pct",
    "interest_rate_impact_pct",
    "sectoral_output_pct_change",
}


# ---------------------------------------------------------------------------
# 1. Kernel: golden numbers + monotonicity
# ---------------------------------------------------------------------------


class TestComputeMacroOutcomes:
    def test_returns_full_schema(self) -> None:
        out = compute_macro_outcomes({"oil": 30.0}, duration_months=6.0)
        missing = _REQUIRED_KEYS - out.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_30pct_oil_6mo_reference_scenario(self) -> None:
        """Reference golden numbers for a 30% oil shock over 6 months.

        Short-run duration scaler at 6 months is 0.583. So:
            GDP:  -0.025 * 30 * 0.583 = -0.4374 pp
            CPI:  +0.04  * 30 * 0.583 = +0.6996 pp
        Tolerances are wide because the scaler is piecewise-smooth
        and not the focus of this test.
        """
        out = compute_macro_outcomes({"oil": 30.0}, duration_months=6.0)
        assert out["gdp_impact_pct"] < 0.0
        assert out["gdp_impact_pct"] == pytest.approx(-0.44, abs=0.05)
        assert out["cpi_inflation_pct"] > 0.0
        assert out["cpi_inflation_pct"] == pytest.approx(0.7, abs=0.1)
        # Welfare follows real consumption -- always negative for an
        # oil price rise.
        assert out["welfare_pct_change"] < 0.0
        # Sectoral split: every non-energy sector should be hit, and
        # the agricultural & industrial sectors should fall *more per
        # unit of value-added* than services because their energy
        # cost shares are higher.
        sect = out["sectoral_output_pct_change"]
        from src.models.macro.macro_kernel import SECTOR_GDP_SHARE
        per_unit_ag = abs(sect["agriculture"]) / SECTOR_GDP_SHARE["agriculture"]
        per_unit_svc = abs(sect["services"]) / SECTOR_GDP_SHARE["services"]
        assert per_unit_ag > per_unit_svc
        assert sect["agriculture"] < 0.0
        assert sect["industry"] < 0.0
        assert sect["services"] < 0.0
        # Energy sector benefits from price rise -- relative to industry,
        # which loses output, energy gains.
        assert sect["energy"] > sect["industry"]

    def test_monotonicity_in_shock_size(self) -> None:
        small = compute_macro_outcomes({"oil": 10.0}, duration_months=6.0)
        big = compute_macro_outcomes({"oil": 50.0}, duration_months=6.0)
        assert abs(big["gdp_impact_pct"]) > abs(small["gdp_impact_pct"])
        assert big["cpi_inflation_pct"] > small["cpi_inflation_pct"]

    def test_monotonicity_in_duration(self) -> None:
        short = compute_macro_outcomes({"oil": 30.0}, duration_months=2.0)
        long = compute_macro_outcomes({"oil": 30.0}, duration_months=12.0)
        assert abs(long["welfare_pct_change"]) > abs(short["welfare_pct_change"])
        assert abs(long["gdp_impact_pct"]) >= abs(short["gdp_impact_pct"])

    def test_negative_oil_shock_flips_signs(self) -> None:
        """A negative oil shock (price collapse) should boost GDP / cut CPI."""
        out = compute_macro_outcomes({"oil": -20.0}, duration_months=6.0)
        assert out["gdp_impact_pct"] > 0.0
        assert out["cpi_inflation_pct"] < 0.0

    def test_unknown_commodity_uses_residual_elasticity(self) -> None:
        """An unrecognised commodity should still register, not silently zero."""
        out = compute_macro_outcomes({"ammonia": 25.0}, duration_months=6.0)
        assert out["gdp_impact_pct"] != 0.0
        assert out["cpi_inflation_pct"] != 0.0

    def test_empty_shocks_returns_zeroed_schema(self) -> None:
        out = compute_macro_outcomes({}, duration_months=6.0)
        assert out["gdp_impact_pct"] == 0.0
        assert out["cpi_inflation_pct"] == 0.0
        # Schema still complete so downstream code can blindly index.
        assert _REQUIRED_KEYS <= out.keys()

    def test_long_run_regime_scales_linearly_with_duration(self) -> None:
        """In long-run regime, doubling the duration roughly doubles GDP impact."""
        twelve = compute_macro_outcomes(
            {"oil": 30.0}, duration_months=12.0, regime="long_run"
        )
        twentyfour = compute_macro_outcomes(
            {"oil": 30.0}, duration_months=24.0, regime="long_run"
        )
        ratio = twentyfour["gdp_impact_pct"] / twelve["gdp_impact_pct"]
        assert ratio == pytest.approx(2.0, rel=0.05)

    def test_provenance_block_is_attached(self) -> None:
        out = compute_macro_outcomes({"oil": 30.0}, duration_months=6.0)
        assert "_inputs" in out
        assert "_calibration_sources" in out
        assert isinstance(out["_calibration_sources"], list)
        assert len(out["_calibration_sources"]) >= 5

    def test_water_shock_only_lands_when_provided(self) -> None:
        """The water channel should be active when the caller passes it,
        but should be a no-op when omitted (used only by the
        infrastructure_collapse scenario)."""
        no_water = compute_macro_outcomes({"oil": 30.0}, duration_months=6.0)
        with_water = compute_macro_outcomes(
            {"oil": 30.0, "water": 40.0}, duration_months=6.0
        )
        assert with_water["gdp_impact_pct"] < no_water["gdp_impact_pct"]


# ---------------------------------------------------------------------------
# 2. PyCGE analytical-MVP fallback
# ---------------------------------------------------------------------------


class _BogusCGEModeling:
    """Stand-in for a stale / pre-alpha cge_modeling install.

    Exposes the package import but none of the names ``PyCGEAdapter``
    needs (Model, load_sam, examples.hosoe_2region). The
    ``_cge_modeling_api_available`` probe should therefore return False
    and ``execute()`` should fall through to the analytical MVP.
    """

    __version__ = "0.0.6"


@pytest.fixture()
def pycge_params() -> dict[str, Any]:
    return {
        "scenario_id": "swift_contained",
        "oil_price_shock_pct": 35.0,
        "commodity_price_shocks": {
            "lng": 40.0,
            "fertilizer": 20.0,
            "helium": 10.0,
        },
        "disruption_duration_months": 6.0,
    }


def _force_pycge_to_use_mvp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the API probe so PyCGE always picks the analytical MVP.

    Direct manipulation of ``sys.modules`` would also work, but the
    cleaner thing is to short-circuit the probe. This isolates the
    test from whatever cge_modeling state is installed.
    """
    monkeypatch.setattr(
        PyCGEAdapter, "_cge_modeling_api_available", staticmethod(lambda: False)
    )


class TestPyCGEAnalyticalMVPFallback:
    def test_completes_when_cge_modeling_absent(
        self, pycge_params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Forcibly remove cge_modeling from sys.modules so the probe
        # cannot find it. Belt-and-suspenders alongside the staticmethod
        # patch below.
        monkeypatch.setitem(sys.modules, "cge_modeling", None)
        _force_pycge_to_use_mvp(monkeypatch)

        adapter = PyCGEAdapter()
        validation = adapter.validate_inputs(dict(pycge_params))
        assert validation.valid, validation.errors

        native = adapter.translate_inputs(dict(pycge_params))
        out: ModelOutput = adapter.execute(native)

        assert out.convergence_status == "completed"
        assert _REQUIRED_KEYS <= out.outputs.keys()
        assert out.outputs.get("_used_analytical_mvp") is True
        assert out.outputs.get("_execution_mode") == "analytical_mvp"
        assert out.metadata.get("execution_mode") == "analytical_mvp"
        # Sign sanity: oil + LNG + fertilizer + helium shocks all
        # depress GDP and lift CPI.
        assert out.outputs["gdp_impact_pct"] < 0.0
        assert out.outputs["cpi_inflation_pct"] > 0.0

    def test_completes_when_cge_modeling_api_mismatches(
        self, pycge_params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bogus cge_modeling stand-in (pre-alpha API) should still
        cleanly fall back."""
        monkeypatch.setitem(sys.modules, "cge_modeling", _BogusCGEModeling())

        adapter = PyCGEAdapter()
        native = adapter.translate_inputs(dict(pycge_params))
        out = adapter.execute(native)

        assert out.convergence_status == "completed"
        assert out.outputs.get("_execution_mode") == "analytical_mvp"

    def test_real_path_is_preferred_when_api_matches(
        self, pycge_params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the API probe says yes, execute() must call the real
        path -- not silently fall through to the MVP."""

        called: list[bool] = []

        def fake_real_path(self: PyCGEAdapter, inputs: Any) -> ModelOutput:
            called.append(True)
            return ModelOutput(
                model_id=self.model_id,
                outputs={"_execution_mode": "cge_modeling", "gdp_impact_pct": -0.42},
                convergence_status="completed",
                metadata={"execution_mode": "cge_modeling"},
            )

        monkeypatch.setattr(
            PyCGEAdapter,
            "_cge_modeling_api_available",
            staticmethod(lambda: True),
        )
        monkeypatch.setattr(
            PyCGEAdapter, "_execute_real_cge_modeling", fake_real_path
        )

        adapter = PyCGEAdapter()
        native = adapter.translate_inputs(dict(pycge_params))
        out = adapter.execute(native)

        assert called, "Real cge_modeling path was not invoked."
        assert out.outputs.get("_execution_mode") == "cge_modeling"

    def test_real_path_failure_falls_back_to_mvp(
        self, pycge_params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the real path raises during execute, the adapter should
        downgrade to the analytical MVP rather than fail the run."""

        def boom(self: PyCGEAdapter, inputs: Any) -> ModelOutput:
            raise RuntimeError("cge_modeling solver blew up")

        monkeypatch.setattr(
            PyCGEAdapter,
            "_cge_modeling_api_available",
            staticmethod(lambda: True),
        )
        monkeypatch.setattr(PyCGEAdapter, "_execute_real_cge_modeling", boom)

        adapter = PyCGEAdapter()
        native = adapter.translate_inputs(dict(pycge_params))
        out = adapter.execute(native)

        assert out.convergence_status == "completed"
        assert out.outputs.get("_execution_mode") == "analytical_mvp"


# ---------------------------------------------------------------------------
# 3. Energy-adapter operational-shock translator
# ---------------------------------------------------------------------------


class TestDeriveMacroFromEnergyShocks:
    def test_temoa_messageix_shape(self) -> None:
        """TEMOA / MESSAGEix's shocks dict should yield a populated macro
        response with non-zero GDP / CPI fields."""
        shocks = {
            "oil_supply_loss_mbd": 18.0,
            "gas_supply_loss_bcfd": 15.0,
            "lng_export_capacity_loss_pct": 25.0,
            "capital_cost_multiplier": 1.10,
            "duration_years": 0.5,
            "co2_price_baseline_usd_per_t": 50.0,
        }
        out = derive_macro_from_energy_shocks(shocks)
        assert _REQUIRED_KEYS <= out.keys()
        assert out["gdp_impact_pct"] < 0.0
        assert out["cpi_inflation_pct"] > 0.0
        assert out["_source_kind"] == "energy_adapter_derived"
        assert "oil" in out["_translation"]
        assert "lng" in out["_translation"]

    def test_supply_loss_translates_to_meaningful_oil_shock(self) -> None:
        """A 5 mb/d oil supply loss should imply roughly +45% Brent
        (5/102 / (-0.06 - 0.05)).
        """
        out = derive_macro_from_energy_shocks(
            {"oil_supply_loss_mbd": 5.0, "duration_years": 0.5}
        )
        oil_translation = out["_translation"].get("oil")
        assert oil_translation is not None
        assert oil_translation["price_shock_pct"] == pytest.approx(44.6, abs=2.0)

    def test_explicit_price_path_overrides_supply_calc(self) -> None:
        """If an explicit oil_price_path_override_usd is supplied, it
        should be used instead of recomputing from supply."""
        out = derive_macro_from_energy_shocks(
            {
                "oil_price_path_override_usd": [120.0, 110.0, 100.0],
                "duration_years": 0.5,
            }
        )
        # 120 vs 80 baseline -> +50% peak.
        assert out["_translation"]["oil"]["price_shock_pct"] == pytest.approx(
            50.0, abs=0.5
        )

    def test_empty_shocks_returns_safe_zeroed_payload(self) -> None:
        """When a caller has no operational shocks (e.g., a baseline
        run), the helper should return a complete schema with empty
        translation and no commodity entries."""
        out = derive_macro_from_energy_shocks({})
        assert _REQUIRED_KEYS <= out.keys()
        assert out["_translation"] == {}
        assert out["gdp_impact_pct"] == 0.0
        assert out["cpi_inflation_pct"] == 0.0

    def test_osemosys_pj_to_mbd_path(self) -> None:
        """OSeMOSYS' adapter passes its operational shocks through a
        unit-conversion shim. Replicate the conversion the adapter does
        and confirm the kernel still produces a non-zero macro answer.
        """
        oil_pj = 5.0 * 365.0 * 5.8e-3  # 5 mb/d oil loss
        oil_mbd = oil_pj / (365.0 * 5.8e-3)
        assert oil_mbd == pytest.approx(5.0, rel=1e-6)

        out = derive_macro_from_energy_shocks(
            {"oil_supply_loss_mbd": oil_mbd, "duration_years": 0.5}
        )
        assert out["gdp_impact_pct"] < 0.0


# ---------------------------------------------------------------------------
# 4. Regional disaggregation
# ---------------------------------------------------------------------------


_REGIONAL_ROW_KEYS = {
    "region",
    "gdp_impact_pct",
    "cpi_inflation_pct",
    "consumption_impact_pct",
    "welfare_pct_change",
    "wage_impact_pct",
    "interest_rate_impact_pct",
}


class TestComputeRegionalMacroOutcomes:
    def test_returns_one_row_per_unified_region(self) -> None:
        rows = compute_regional_macro_outcomes(
            {"oil": 30.0}, duration_months=6.0
        )
        assert len(rows) == len(UNIFIED_REGIONS)
        assert {r["region"] for r in rows} == set(UNIFIED_REGIONS)
        for row in rows:
            missing = _REGIONAL_ROW_KEYS - row.keys()
            assert not missing, f"row {row['region']} missing keys: {missing}"

    def test_oil_exporters_gain_on_positive_oil_shock(self) -> None:
        """A positive oil price shock should help GCC oil exporters
        (negative GDP multiplier in the regional table) and hurt
        importers like the EU and India."""
        rows = {r["region"]: r for r in compute_regional_macro_outcomes(
            {"oil": 30.0}, duration_months=6.0
        )}
        assert rows["MENA_GCC"]["gdp_impact_pct"] > 0.0
        assert rows["EU"]["gdp_impact_pct"] < 0.0
        assert rows["IND"]["gdp_impact_pct"] < 0.0
        assert rows["US"]["gdp_impact_pct"] < 0.0

    def test_emerging_markets_have_higher_cpi_passthrough(self) -> None:
        """India and SSA should show larger CPI inflation than the US
        for the same oil shock (Choi et al. 2018 calibration)."""
        rows = {r["region"]: r for r in compute_regional_macro_outcomes(
            {"oil": 30.0}, duration_months=6.0
        )}
        assert rows["IND"]["cpi_inflation_pct"] > rows["US"]["cpi_inflation_pct"]
        assert rows["SSA"]["cpi_inflation_pct"] > rows["US"]["cpi_inflation_pct"]

    def test_eu_more_exposed_to_lng_shock_than_us(self) -> None:
        """EU's gas-import dependence is roughly 3x the US baseline."""
        rows = {r["region"]: r for r in compute_regional_macro_outcomes(
            {"lng": 50.0}, duration_months=6.0
        )}
        assert abs(rows["EU"]["gdp_impact_pct"]) > abs(rows["US"]["gdp_impact_pct"])
        assert rows["EU"]["cpi_inflation_pct"] > rows["US"]["cpi_inflation_pct"]

    def test_water_shock_concentrates_in_gulf(self) -> None:
        """The infrastructure-collapse water shock should hit MENA_GCC
        far harder than non-MENA regions."""
        rows = {r["region"]: r for r in compute_regional_macro_outcomes(
            {"water": 40.0}, duration_months=6.0
        )}
        assert abs(rows["MENA_GCC"]["gdp_impact_pct"]) > abs(rows["EU"]["gdp_impact_pct"])
        assert abs(rows["MENA_GCC"]["gdp_impact_pct"]) > abs(rows["LAC"]["gdp_impact_pct"])
        assert abs(rows["MENA_OTHER"]["gdp_impact_pct"]) > abs(rows["US"]["gdp_impact_pct"])

    def test_empty_shocks_yields_zeroed_rows(self) -> None:
        rows = compute_regional_macro_outcomes({}, duration_months=6.0)
        assert len(rows) == len(UNIFIED_REGIONS)
        for row in rows:
            assert row["gdp_impact_pct"] == 0.0
            assert row["cpi_inflation_pct"] == 0.0

    def test_subset_regions_filter(self) -> None:
        rows = compute_regional_macro_outcomes(
            {"oil": 30.0}, duration_months=6.0, regions=("US", "MENA_GCC")
        )
        assert {r["region"] for r in rows} == {"US", "MENA_GCC"}

    def test_aggregate_kernel_attaches_regional_vars(self) -> None:
        """``compute_macro_outcomes`` must surface ``regional_vars`` so
        every consumer (PyCGE analytical-MVP, energy-tier derived macro)
        gets per-region detail without extra wiring."""
        out = compute_macro_outcomes(
            {"oil": 30.0, "lng": 20.0}, duration_months=6.0
        )
        assert "regional_vars" in out
        assert isinstance(out["regional_vars"], list)
        assert len(out["regional_vars"]) == len(UNIFIED_REGIONS)


class TestPyCGERegionalOutputs:
    def test_analytical_mvp_emits_regional_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "cge_modeling", None)
        _force_pycge_to_use_mvp(monkeypatch)

        adapter = PyCGEAdapter()
        params = {
            "scenario_id": "swift_contained",
            "oil_price_shock_pct": 35.0,
            "commodity_price_shocks": {"lng": 40.0, "fertilizer": 20.0},
            "disruption_duration_months": 6.0,
        }
        native = adapter.translate_inputs(params)
        out = adapter.execute(native)

        regional = out.outputs.get("regional_vars")
        assert isinstance(regional, list)
        assert len(regional) == len(UNIFIED_REGIONS)
        regions = {r["region"] for r in regional}
        assert "US" in regions and "MENA_GCC" in regions and "EU" in regions
        assert out.outputs.get("_regional_source") == "macro_kernel_derived"

        # Heterogeneity guard: the per-region GDP impacts should not all
        # be identical — that's the whole point of the disaggregation.
        gdps = [r["gdp_impact_pct"] for r in regional]
        assert len(set(gdps)) > 1
