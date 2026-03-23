"""World Fertilizer Model adapter.

The World Fertilizer Model is a market-equilibrium model of global fertilizer
supply and demand. It tracks nitrogen (N), phosphorus (P), and potassium (K)
fertilizer markets, incorporating natural gas as the primary feedstock for
nitrogen fertilizer production. Under Strait of Hormuz closure scenarios, it
quantifies how Middle East production losses and natural gas price increases
cascade into global fertilizer supply shortfalls and price spikes.

Real integration requirements:
    - Access to the World Fertilizer Model codebase and calibrated dataset
    - Platform-specific execution environment (Python, GAMS, or proprietary)
    - Natural gas price and Middle East production capacity inputs
    - Disruption duration for dynamic equilibrium path calculation
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "natural_gas_price_change_pct",
    "middle_east_production_loss_pct",
    "disruption_duration_months",
]


class WorldFertilizerAdapter(ModelAdapter):
    """Adapter for the World Fertilizer Model market-equilibrium model.

    The World Fertilizer Model solves for equilibrium fertilizer prices and
    trade flows under supply and cost shocks. The Strait of Hormuz closure
    directly affects this model through two channels: (1) loss of Middle East
    natural gas feedstock, disrupting nitrogen fertilizer production in Qatar,
    Iran, Saudi Arabia, and UAE; and (2) higher natural gas prices globally,
    raising the marginal cost of nitrogen fertilizer production worldwide.
    """

    @property
    def model_id(self) -> str:
        return "world_fertilizer"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "World Fertilizer Model: market-equilibrium model of global nitrogen, "
            "phosphorus, and potassium fertilizer supply and demand, with natural gas "
            "as the primary feedstock input for nitrogen production."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required World Fertilizer Model parameters are present and in range.

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

        if "natural_gas_price_change_pct" in params:
            val = params["natural_gas_price_change_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'natural_gas_price_change_pct' must be numeric")
            elif val > 1000:
                warnings.append(
                    f"'natural_gas_price_change_pct' = {val}% is extreme; "
                    "verify that this reflects a scenario-consistent shock"
                )

        if "middle_east_production_loss_pct" in params:
            val = params["middle_east_production_loss_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'middle_east_production_loss_pct' must be numeric")
            elif not (0.0 <= val <= 100.0):
                errors.append(
                    f"'middle_east_production_loss_pct' = {val} is out of range; "
                    "expected a value in [0, 100]"
                )
            elif val > 80:
                warnings.append(
                    f"'middle_east_production_loss_pct' = {val}% implies near-total "
                    "regional production loss; confirm this is scenario-consistent"
                )

        if "disruption_duration_months" in params:
            val = params["disruption_duration_months"]
            if not isinstance(val, (int, float)):
                errors.append("'disruption_duration_months' must be numeric")
            elif val <= 0:
                errors.append("'disruption_duration_months' must be > 0")
            elif val > 24:
                warnings.append(
                    f"'disruption_duration_months' = {val} exceeds typical model "
                    "calibration horizon; results may extrapolate beyond validated range"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation formats World Fertilizer Model inputs.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the World Fertilizer Model — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: World Fertilizer Model integration is pending.
                Real implementation must invoke the model's execution environment,
                supply natural gas price and Middle East production loss parameters,
                and collect equilibrium fertilizer price and trade flow outputs.
        """
        raise NotImplementedError(
            "WorldFertilizerAdapter.execute is not yet implemented. "
            "Real integration requires: (1) access to the World Fertilizer Model codebase "
            "and its execution environment, (2) parameterizing natural gas price shocks and "
            "Middle East production capacity losses, (3) invoking the model for the specified "
            "disruption duration, and (4) collecting equilibrium fertilizer prices (N, P, K) "
            "and regional trade flow outputs."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses World Fertilizer Model results.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
