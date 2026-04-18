"""Futures forecasting model adapter.

Futures forecasting models are time-series models that project commodity futures
price trajectories under supply disruption scenarios. They combine statistical
time-series methods (e.g., ARIMA, VAR, regime-switching models) with
fundamental supply-demand inputs to generate forward price curves for
agricultural and energy commodities. Under Strait of Hormuz closure scenarios,
they translate an initial price shock into a price path over the forecast
horizon, reflecting market expectations of disruption duration, supply
substitution, and eventual resolution.

Real integration requirements:
    - Time-series model codebase (Python/R statistical packages)
    - Historical commodity futures price data (CBOT wheat, corn, soybeans;
      NYMEX natural gas; fertilizer benchmark prices)
    - Calibrated model parameters for regime-switching or shock-propagation dynamics
    - Commodity list specifying which markets to model
    - Forecast horizon aligned with the scenario disruption duration
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "initial_price_shock_pct",
    "commodities",
    "forecast_horizon_months",
]

_SUPPORTED_COMMODITIES = {
    "wheat",
    "corn",
    "soybeans",
    "rice",
    "natural_gas",
    "urea",
    "ammonia",
    "dap",
    "potash",
    "palm_oil",
    "sugar",
}


class FuturesAdapter(ModelAdapter):
    """Adapter for commodity futures price trajectory forecasting models.

    Futures forecasting models generate forward price curves for agricultural
    and energy commodities under a given initial price shock. In the Strait of
    Hormuz pipeline, they translate the commodity-level price impacts (from
    World Fertilizer Model, POLES-JRC, and shipping models) into time-path
    projections that capture market expectations of how quickly prices return
    to baseline as the disruption resolves or structural adjustments occur.
    These price paths feed downstream macro models (short-run inflation and
    GDP impacts) and are used in the synthesis module to characterize the
    temporal profile of economic harm across scenarios.

    Outputs fed downstream:
        - Monthly forward price curves per commodity ($/unit, indexed to baseline)
        - Price volatility estimates (implied or realized)
        - Expected time-to-normalization per commodity
        - Scenario-conditioned price distributions (where model supports it)
    """

    @property
    def model_id(self) -> str:
        return "futures"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Futures forecasting models: time-series models generating commodity futures "
            "price trajectories under supply disruption, translating initial price shocks "
            "into forward price curves for agricultural and energy commodities over the "
            "scenario forecast horizon."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required futures forecasting parameters are present and in range.

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

        if "initial_price_shock_pct" in params:
            val = params["initial_price_shock_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'initial_price_shock_pct' must be numeric")
            elif val > 500:
                warnings.append(
                    f"'initial_price_shock_pct' = {val}% is extreme; "
                    "verify consistency with commodity-level model outputs (World Fertilizer "
                    "Model, POLES-JRC) before running futures trajectory models"
                )

        if "commodities" in params:
            val = params["commodities"]
            if not isinstance(val, list):
                errors.append(
                    "'commodities' must be a list of commodity name strings "
                    f"(e.g., ['wheat', 'urea']); supported values: "
                    f"{sorted(_SUPPORTED_COMMODITIES)}"
                )
            elif len(val) == 0:
                errors.append("'commodities' must contain at least one commodity name")
            else:
                unrecognized = [c for c in val if c not in _SUPPORTED_COMMODITIES]
                if unrecognized:
                    warnings.append(
                        f"Unrecognized commodity names: {unrecognized}. "
                        f"Supported commodities are: {sorted(_SUPPORTED_COMMODITIES)}. "
                        "The model may lack calibrated parameters for these commodities."
                    )

        if "forecast_horizon_months" in params:
            val = params["forecast_horizon_months"]
            if not isinstance(val, (int, float)):
                errors.append("'forecast_horizon_months' must be numeric")
            elif val <= 0:
                errors.append("'forecast_horizon_months' must be > 0")
            elif val > 60:
                warnings.append(
                    f"'forecast_horizon_months' = {val} exceeds 5 years; "
                    "time-series model accuracy degrades substantially at this horizon; "
                    "consider using CGE models (GTAP, MIRAGRODEP) for structural long-run effects"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation formats time-series model inputs.

        The real implementation would extract historical price series for each
        commodity in the list, apply the initial shock as a level shift at the
        disruption start date, and configure the time-series model to produce
        a conditional forecast over the specified horizon.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the futures forecasting model — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Futures model integration is pending. Real
                implementation must load calibrated time-series model parameters,
                apply the initial price shock, and generate forward price curves
                for each specified commodity over the forecast horizon.
        """
        raise NotImplementedError(
            "FuturesAdapter.execute is not yet implemented. "
            "Real integration requires: (1) calibrated time-series model parameters "
            "(ARIMA, VAR, or regime-switching specifications) for each commodity in the "
            "supported set, (2) historical commodity futures price data (CBOT, NYMEX, or "
            "fertilizer benchmark sources) for model calibration and baseline construction, "
            "(3) logic to apply the initial_price_shock_pct as a level shift at the "
            "disruption start date within the model's conditional forecasting framework, "
            "(4) execution of the forecasting routine (Python statsmodels/arch/pyflux, or "
            "R forecast/vars packages via subprocess) for each commodity in the list, and "
            "(5) collection of monthly forward price curve outputs (point forecast plus "
            "confidence intervals) over the forecast_horizon_months period."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses price curve arrays.

        The real implementation would extract monthly price forecast arrays per
        commodity, compute implied volatility or confidence intervals where
        available, and structure results as a dict keyed by commodity name with
        values being monthly price series indexed to the disruption start date.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
