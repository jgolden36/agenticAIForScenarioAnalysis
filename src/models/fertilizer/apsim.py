"""APSIM model adapter.

APSIM (Agricultural Production Systems sIMulator) is a biophysical crop
simulation model that predicts the response of crop yields to changes in soil,
climate, and management inputs. Under Strait of Hormuz closure scenarios, it
quantifies the physical yield penalty from reduced fertilizer application and
irrigation water availability, providing the biophysical crop-level foundation
for downstream agricultural trade and food security analyses.

Real integration requirements:
    - APSIM Next Generation installation (cross-platform, .NET-based)
    - APSIM simulation files (.apsimx) with site-specific soil, climate, and
      management configurations for target agricultural regions
    - Climate data files for the relevant growing season
    - Fertilizer application schedules and irrigation management rules
      parameterized to reflect disruption-induced reductions
    - Python API (pyAPSIM) or subprocess invocation of the APSIM CLI
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "fertilizer_application_reduction_pct",
    "irrigation_water_reduction_pct",
    "growing_season",
]

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Crop-specific N-response and water-response coefficients, calibrated
# from FAO (1979) yield-response-to-water + Mitscherlich-style N-response
# curves (Sinclair & Park 1993). yield_drop_pct = a * fert_red^p + b *
# water_red^q.
_N_RESPONSE: dict[str, tuple[float, float]] = {
    # crop -> (coefficient, exponent) on fertilizer reduction
    "wheat": (0.65, 0.7),
    "rice": (0.50, 0.7),
    "maize": (0.70, 0.7),
    "soybean": (0.30, 0.7),  # legume, lower N response
    "barley": (0.55, 0.7),
}
_WATER_RESPONSE: dict[str, tuple[float, float]] = {
    "wheat": (0.45, 0.8),
    "rice": (0.85, 0.9),  # rice is highly water-sensitive
    "maize": (0.60, 0.8),
    "soybean": (0.40, 0.7),
    "barley": (0.40, 0.7),
}
# Default crop list when ``growing_season`` doesn't encode a specific
# crop. MENA wheat + South-Asian rice are the dominant Hormuz-affected
# crops.
_DEFAULT_CROPS: list[str] = ["wheat", "rice", "maize"]
# Baseline N use efficiency (kg yield / kg N applied). FAO 2021 World
# Fertilizer Outlook.
_NUE_BASELINE: float = 25.0


class APSIMAdapter(ModelAdapter):
    """Adapter for the APSIM biophysical crop simulation model.

    APSIM simulates crop growth, development, and yield at the field or farm
    scale using detailed soil-plant-atmosphere process representations. In the
    Strait of Hormuz pipeline, APSIM quantifies the physical crop yield
    penalties associated with reduced fertilizer availability (due to supply
    disruption and price spikes deterring application) and reduced irrigation
    water (due to desalination infrastructure risk or reduced pumping capacity).
    These yield impacts are passed upstream to agricultural trade models
    (CAPRI, MAgPIE, SIMPLE-G, GTAP) as biophysical constraints.

    Outputs fed downstream:
        - Crop yield change by crop type and region (% relative to baseline)
        - Nitrogen use efficiency under reduced application rates
        - Soil nitrogen balance implications for subsequent seasons
        - Water-limited vs. nitrogen-limited yield decomposition
    """

    @property
    def model_id(self) -> str:
        return "apsim"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "APSIM (Agricultural Production Systems sIMulator): biophysical crop simulation "
            "model predicting yield responses to reductions in fertilizer application and "
            "irrigation water under crisis-induced input constraints."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required APSIM parameters are present and in range.

        Args:
            params: Parameter dictionary from the extraction module.

        Returns:
            ValidationResult with errors for missing or out-of-range values.
        """
        errors: list[str] = []
        warnings: list[str] = []

        for key in _REQUIRED_PARAMS:
            if key not in params:
                errors.append(f"Missing required parameter: '{key}'")

        if "fertilizer_application_reduction_pct" in params:
            val = params["fertilizer_application_reduction_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'fertilizer_application_reduction_pct' must be numeric")
            elif not (0.0 <= val <= 100.0):
                errors.append(
                    f"'fertilizer_application_reduction_pct' = {val} is out of range; "
                    "expected a value in [0, 100] representing percent reduction from baseline"
                )
            elif val > 75:
                warnings.append(
                    f"'fertilizer_application_reduction_pct' = {val}% implies near-complete "
                    "cessation of fertilizer use; verify this is scenario-consistent"
                )

        if "irrigation_water_reduction_pct" in params:
            val = params["irrigation_water_reduction_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'irrigation_water_reduction_pct' must be numeric")
            elif not (0.0 <= val <= 100.0):
                errors.append(
                    f"'irrigation_water_reduction_pct' = {val} is out of range; "
                    "expected a value in [0, 100] representing percent reduction from baseline"
                )
            elif val > 80:
                warnings.append(
                    f"'irrigation_water_reduction_pct' = {val}% implies near-total loss of "
                    "irrigation; APSIM results at this level should be cross-checked against "
                    "WEAP/WaterGAP2 water model outputs"
                )

        if "growing_season" in params:
            val = params["growing_season"]
            if not isinstance(val, str):
                errors.append("'growing_season' must be a string (e.g., '2026_winter_wheat')")
            elif not val.strip():
                errors.append("'growing_season' must not be an empty string")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation modifies APSIM simulation files.

        The real implementation would open the relevant .apsimx simulation file,
        patch the fertilizer application manager rules (reducing N application rates
        by fertilizer_application_reduction_pct) and irrigation manager rules
        (reducing irrigation triggers or total allocations by
        irrigation_water_reduction_pct) for the specified growing_season, then
        save the modified simulation to a temporary working directory.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the analytical-MVP APSIM crop-yield model.

        Closed-form crop-yield response curves combining
        Mitscherlich-style nitrogen response with FAO water-yield
        functions. Real APSIM Next Generation invocation requires the
        .NET runtime + .apsimx simulation files; this MVP fallback gives
        the FERTILIZER_AGRICULTURE tier a biophysical crop-level model
        to complement ``futures`` and ``world_fertilizer``.

        Mechanics per crop:

          ``yield_drop_pct = a_n * (fert_red/100)^p_n * 100``
          ``                + a_w * (water_red/100)^p_w * 100``

        capped at 95% (no negative yields). NUE under reduced
        application rates rises as crops use scarce N more efficiently.
        """
        params = inputs if isinstance(inputs, dict) else dict(inputs)

        fert_red = float(params["fertilizer_application_reduction_pct"])
        irrig_red = float(params["irrigation_water_reduction_pct"])
        growing_season = str(params["growing_season"])

        # Pick crops based on growing_season hint or fall back to defaults.
        crops: list[str] = []
        for crop in _N_RESPONSE:
            if crop in growing_season.lower():
                crops.append(crop)
        if not crops:
            crops = list(_DEFAULT_CROPS)

        yield_change_by_crop: dict[str, float] = {}
        n_limited_share: dict[str, float] = {}
        water_limited_share: dict[str, float] = {}
        for crop in crops:
            a_n, p_n = _N_RESPONSE.get(crop, (0.6, 0.7))
            a_w, p_w = _WATER_RESPONSE.get(crop, (0.5, 0.8))
            n_drop = a_n * (fert_red / 100.0) ** p_n * 100.0
            w_drop = a_w * (irrig_red / 100.0) ** p_w * 100.0
            total_drop = min(95.0, n_drop + w_drop)
            yield_change_by_crop[crop] = round(-total_drop, 3)
            denom = max(n_drop + w_drop, 1e-6)
            n_limited_share[crop] = round(n_drop / denom, 3)
            water_limited_share[crop] = round(w_drop / denom, 3)

        # Mean yield drop across the requested crops.
        mean_yield_drop_pct = sum(
            yield_change_by_crop.values()
        ) / max(len(yield_change_by_crop), 1)

        # NUE rises under input scarcity (Mitscherlich): when farmers
        # apply less N, the marginal kg yields a higher kg of grain.
        # Calibrated such that 50% application reduction lifts NUE by
        # 30%.
        nue_change_pct = 0.6 * fert_red
        new_nue = round(_NUE_BASELINE * (1.0 + nue_change_pct / 100.0), 3)

        outputs: dict[str, Any] = {
            "fertilizer_application_reduction_pct": fert_red,
            "irrigation_water_reduction_pct": irrig_red,
            "growing_season": growing_season,
            "yield_pct_change_by_crop": yield_change_by_crop,
            "mean_yield_pct_change": round(mean_yield_drop_pct, 3),
            "n_limited_yield_share_by_crop": n_limited_share,
            "water_limited_yield_share_by_crop": water_limited_share,
            "n_use_efficiency_baseline": _NUE_BASELINE,
            "n_use_efficiency_new": new_nue,
            "n_use_efficiency_change_pct": round(nue_change_pct, 3),
            # Crop-aggregate yield loss for downstream forwarding (mean
            # of all simulated crops).
            "crop_yield_loss_pct": round(-mean_yield_drop_pct, 3),
            "simulated_crops": crops,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "FAO (1979) Yield Response to Water (Doorenbos & "
                    "Kassam); Sinclair & Park (1993) Mitscherlich N "
                    "response; FAO (2021) World Fertilizer Outlook NUE."
                ),
                "n_response_coefficients": dict(_N_RESPONSE),
                "water_response_coefficients": dict(_WATER_RESPONSE),
                "nue_baseline": _NUE_BASELINE,
                "note": (
                    "Analytical MVP path. Real APSIM integration "
                    "requires: (1) APSIM Next Generation install, "
                    "(2) site-specific .apsimx files, (3) fertilizer/"
                    "irrigation manager-rule patching, (4) Models.exe "
                    "subprocess invocation, (5) SQLite output parsing."
                ),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses the APSIM output database.

        The real implementation would open the APSIM output SQLite database,
        query the Report table for yield (kg/ha), nitrogen uptake (kg N/ha),
        and water balance columns, and aggregate results across simulation nodes
        to produce regional yield impact estimates.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
