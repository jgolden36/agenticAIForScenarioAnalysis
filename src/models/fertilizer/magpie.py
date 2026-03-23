"""MAgPIE model adapter.

MAgPIE (Model of Agricultural Production and its Impact on the Environment) is
a recursive-dynamic optimization model for land use and agricultural production.
It projects how fertilizer price shocks, crop yield changes, and water
availability reductions reshape global and regional land use, food production,
and associated environmental outcomes under crisis scenarios.

Real integration requirements:
    - R installation with the MAgPIE package and its dependencies
    - MAgPIE input data system (madrat) with regional configuration
    - rpy2 or subprocess-based R invocation
    - Access to the MAgPIE model repository (PIK GitHub)
    - Configured scenario settings (cfg) files for shock parameterization
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "fertilizer_price_shock_pct",
    "crop_yield_impact_pct",
    "water_availability_change_pct",
]


class MAgPIEAdapter(ModelAdapter):
    """Adapter for the MAgPIE land-use and agricultural production optimization model.

    MAgPIE solves a cost-minimization problem over global land use, accounting
    for biophysical constraints, trade, and technology adoption. Under Strait of
    Hormuz closure scenarios, it captures how higher fertilizer costs and reduced
    irrigation water availability shift land allocation and reduce crop output,
    with downstream effects on food prices and land-use change emissions.
    """

    @property
    def model_id(self) -> str:
        return "magpie"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "MAgPIE (Model of Agricultural Production and its Impact on the Environment): "
            "recursive-dynamic optimization model projecting land use, agricultural "
            "production, and environmental impacts under fertilizer and water disruptions."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required MAgPIE parameters are present and in range.

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

        if "fertilizer_price_shock_pct" in params:
            val = params["fertilizer_price_shock_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'fertilizer_price_shock_pct' must be numeric")
            elif val < 0:
                errors.append("'fertilizer_price_shock_pct' must be >= 0")
            elif val > 500:
                warnings.append(
                    f"'fertilizer_price_shock_pct' = {val}% is unusually large; verify source"
                )

        if "crop_yield_impact_pct" in params:
            val = params["crop_yield_impact_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'crop_yield_impact_pct' must be numeric")
            elif val < -100:
                errors.append("'crop_yield_impact_pct' cannot be less than -100%")
            elif val > 0:
                warnings.append(
                    "'crop_yield_impact_pct' is positive (yield increase); "
                    "confirm this is intended under a crisis scenario"
                )

        if "water_availability_change_pct" in params:
            val = params["water_availability_change_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'water_availability_change_pct' must be numeric")
            elif val < -100:
                errors.append("'water_availability_change_pct' cannot be less than -100%")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation writes MAgPIE cfg files.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute MAgPIE — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: MAgPIE integration is pending. Real implementation
                must invoke MAgPIE via R (rpy2 or subprocess), writing scenario
                configuration (cfg) files with shock parameters, running the
                start.R entry point, and collecting outputs from the MAgPIE
                output directory (RDS or CSV result files).
        """
        raise NotImplementedError(
            "MAgPIEAdapter.execute is not yet implemented. "
            "Real integration requires: (1) an R installation with the MAgPIE package "
            "and madrat data system, (2) writing scenario cfg files with fertilizer price "
            "and water availability shocks, (3) invoking MAgPIE via rpy2 or subprocess, "
            "and (4) parsing output RDS or CSV files from the MAgPIE output directory."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses MAgPIE result files.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
