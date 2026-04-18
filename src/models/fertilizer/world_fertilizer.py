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
from src.models.adapters.gams_adapter import GAMSAdapter, GAMSConfig
from src.models.base import ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "natural_gas_price_change_pct",
    "middle_east_production_loss_pct",
    "disruption_duration_months",
]


class WorldFertilizerAdapter(GAMSAdapter):
    """Adapter for the World Fertilizer Model market-equilibrium model.

    Inherits from GAMSAdapter for GAMS Control API execution with
    GamsWorkspace/GamsJob orchestration and convergence checking.

    The World Fertilizer Model solves for equilibrium fertilizer prices and
    trade flows under supply and cost shocks. The Strait of Hormuz closure
    directly affects this model through two channels: (1) loss of Middle East
    natural gas feedstock, disrupting nitrogen fertilizer production in Qatar,
    Iran, Saudi Arabia, and UAE; and (2) higher natural gas prices globally,
    raising the marginal cost of nitrogen fertilizer production worldwide.

    IMPORTANT: GamsWorkspace is NOT thread-safe. The GAMSAdapter base class
    allocates isolated temp directories for each execution.
    """

    def __init__(self, config: GAMSConfig | None = None) -> None:
        super().__init__(config)

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

    def populate_database(self, db: Any, params: dict[str, Any]) -> None:
        """Inject scenario parameters into the GAMS database.

        Creates GAMS parameters for natural gas price shock, Middle East
        production loss, and disruption duration. The real implementation
        should match the .gms file's expected parameter names exactly.

        Args:
            db: A gams.GamsDatabase instance.
            params: Validated parameter dictionary.
        """
        gas_param = db.add_parameter("natural_gas_price_change_pct", 0)
        gas_param.add_record().value = params["natural_gas_price_change_pct"]

        prod_param = db.add_parameter("middle_east_production_loss_pct", 0)
        prod_param.add_record().value = params["middle_east_production_loss_pct"]

        dur_param = db.add_parameter("disruption_duration_months", 0)
        dur_param.add_record().value = params["disruption_duration_months"]

    def extract_results(self, out_db: Any) -> dict[str, Any]:
        """Extract equilibrium prices and trade flows from GAMS output.

        Args:
            out_db: The output GamsDatabase from job execution.

        Returns:
            Dict with fertilizer prices (N, P, K) and trade flow data.
        """
        results: dict[str, Any] = {}

        # Extract equilibrium prices by nutrient type
        if "equilibrium_price" in out_db:
            for rec in out_db["equilibrium_price"]:
                results[f"price_{rec.keys[0]}"] = rec.level

        # Extract trade flows if available
        if "trade_flow" in out_db:
            flows = {}
            for rec in out_db["trade_flow"]:
                key = f"{rec.keys[0]}_{rec.keys[1]}" if len(rec.keys) > 1 else rec.keys[0]
                flows[key] = rec.level
            results["trade_flows"] = flows

        # Extract aggregate price index
        if "fertilizer_price_index" in out_db:
            for rec in out_db["fertilizer_price_index"]:
                results["fertilizer_price_index"] = rec.level

        return results

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the World Fertilizer Model.

        When a GAMSConfig is provided, the GAMSAdapter base class handles
        workspace creation, parameter injection, solver execution, convergence
        checking, and result extraction. Until then, raises NotImplementedError.
        """
        if self._config is not None:
            return super().execute(inputs)

        raise NotImplementedError(
            "WorldFertilizerAdapter.execute is not yet implemented. "
            "Provide a GAMSConfig to enable execution via the GAMS Control API. "
            "Requirements: (1) GAMS system installation with matching gamsapi version, "
            "(2) the World Fertilizer Model .gms file, (3) CONOPT solver license."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
