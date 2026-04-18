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
        """Execute APSIM — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: APSIM integration is pending. Real implementation
                must invoke the APSIM Next Generation CLI via subprocess on the
                modified .apsimx simulation file and parse the resulting SQLite
                database output for yield, soil nitrogen, and water balance results.
        """
        raise NotImplementedError(
            "APSIMAdapter.execute is not yet implemented. "
            "Real integration requires: (1) an APSIM Next Generation installation "
            "(cross-platform, .NET-based; available at apsim.info), (2) configured "
            ".apsimx simulation files with site-specific soil and climate data for "
            "relevant agricultural regions (e.g., MENA wheat zones, South Asian rice), "
            "(3) patching the fertilizer and irrigation manager rules in the simulation "
            "file to reflect scenario-specific reduction percentages, (4) invoking the "
            "APSIM CLI via subprocess (e.g., `Models.exe simulation.apsimx`), and "
            "(5) parsing the output SQLite database (.db) for crop yield, soil N balance, "
            "and water use results by crop type and simulation node."
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
