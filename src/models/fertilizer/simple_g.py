"""SIMPLE-G model adapter.

SIMPLE-G (Simplified International Model of agricultural Prices, Land use, and
the Environment — Global) is a global computable general equilibrium model
specialized for agricultural markets. It captures how fertilizer and energy
price shocks interact with global trade disruptions to affect agricultural
commodity prices, land use, and welfare across countries and regions.

Real integration requirements:
    - GAMS installation with the SIMPLE-G model code
    - SIMPLE-G base data (calibrated to a benchmark equilibrium year)
    - GAMS license
    - Access to the SIMPLE-G model repository (Purdue/GTAP group)
    - Scenario shock parameterization via GAMS sets and parameters
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "fertilizer_price_shock_pct",
    "energy_price_shock_pct",
    "trade_disruption_index",
]


class SIMPLEGAdapter(ModelAdapter):
    """Adapter for the SIMPLE-G global agricultural CGE model.

    SIMPLE-G solves for market-clearing prices and quantities across global
    agricultural commodity markets, accounting for cross-commodity substitution
    and international trade linkages. Under Strait of Hormuz closure scenarios,
    it translates simultaneous fertilizer and energy price shocks combined with
    trade route disruptions into welfare and food-security impacts by region.
    """

    @property
    def model_id(self) -> str:
        return "simple_g"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "SIMPLE-G (Simplified International Model of agricultural Prices, Land use, "
            "and the Environment — Global): global agricultural CGE model capturing "
            "fertilizer and energy price shocks combined with trade route disruptions."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required SIMPLE-G parameters are present and in range.

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

        if "energy_price_shock_pct" in params:
            val = params["energy_price_shock_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'energy_price_shock_pct' must be numeric")
            elif val > 500:
                warnings.append(
                    f"'energy_price_shock_pct' = {val}% is unusually large; verify source"
                )

        if "trade_disruption_index" in params:
            val = params["trade_disruption_index"]
            if not isinstance(val, (int, float)):
                errors.append("'trade_disruption_index' must be numeric")
            elif not (0.0 <= val <= 1.0):
                errors.append(
                    f"'trade_disruption_index' = {val} is out of range; "
                    "expected a value in [0.0, 1.0] where 0 = no disruption and 1 = full closure"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation writes GAMS shock files.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute SIMPLE-G — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: SIMPLE-G integration is pending. Real implementation
                must invoke the SIMPLE-G GAMS entry point via subprocess, passing
                shock parameters through GAMS command-line defines or a shock file,
                and collect output from the SIMPLE-G GDX or CSV result files.
        """
        raise NotImplementedError(
            "SIMPLEGAdapter.execute is not yet implemented. "
            "Real integration requires: (1) a GAMS installation with the SIMPLE-G model, "
            "(2) writing scenario shock parameters to a GAMS-compatible input file, "
            "(3) invoking the SIMPLE-G GAMS entry point via subprocess, and "
            "(4) parsing output GDX or CSV files for agricultural price, trade, and "
            "welfare results by region."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses SIMPLE-G result files.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
