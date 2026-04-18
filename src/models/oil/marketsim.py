"""Adapter for the MarketSim (BOEM) consumer surplus and energy substitution model.

Reference:
    Bureau of Ocean Energy Management (BOEM) — MarketSim. A partial-equilibrium
    model for estimating consumer surplus changes and energy substitution patterns
    under oil and natural gas price disruptions.

Real implementation requirements:
    - Access to the BOEM MarketSim model codebase and calibration data (available
      through BOEM's Office of Resource Evaluation).
    - Regional demand elasticity matrices and baseline consumption data by sector.
    - A Python or compiled-binary execution environment compatible with the model
      distribution format.
    - Output: consumer surplus loss by region and sector, fuel-switching quantities
      by energy carrier, welfare decomposition (consumer vs. producer surplus).
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model. Each entry is (name, type_description).
_REQUIRED_PARAMS: list[tuple[str, str]] = [
    ("oil_price_shock_pct", "float — percentage change in oil price relative to pre-disruption baseline (e.g., 40.0 = 40% increase)"),
    ("natural_gas_price_change_pct", "float — percentage change in natural gas price relative to pre-disruption baseline; can be positive or negative"),
    ("disruption_duration_months", "float — expected duration of the supply disruption in months"),
]

_REQUIRED_PARAM_NAMES: set[str] = {name for name, _ in _REQUIRED_PARAMS}


class MarketSimAdapter(ModelAdapter):
    """Adapter stub for the MarketSim (BOEM) consumer surplus and substitution model.

    MarketSim is a partial-equilibrium model developed by the Bureau of Ocean Energy
    Management to evaluate the economic consequences of energy supply disruptions on
    US consumers and producers. It estimates welfare changes (consumer and producer
    surplus) and quantifies fuel-switching behavior as market participants substitute
    away from disrupted energy sources.

    Outputs fed downstream:
        - Consumer surplus loss by sector (residential, commercial, industrial, transport)
          in billion USD
        - Producer surplus change (billion USD)
        - Fuel-switching volumes by energy carrier (oil, natural gas, coal, renewables)
          in million BTU equivalents
        - Net welfare impact (billion USD)
        - Implied demand destruction (mb/d) attributable to price response
    """

    @property
    def model_id(self) -> str:
        return "marketsim"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "MarketSim (BOEM) — Bureau of Ocean Energy Management partial-equilibrium "
            "model for consumer surplus and energy substitution analysis. Estimates "
            "welfare losses and fuel-switching behavior under oil and natural gas price "
            "disruptions across US consumer and producer sectors."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required parameters are present and within plausible bounds."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check required parameters are present
        missing = _REQUIRED_PARAM_NAMES - set(params.keys())
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Bounds checks
        oil_shock = params["oil_price_shock_pct"]
        if not isinstance(oil_shock, (int, float)):
            errors.append("'oil_price_shock_pct' must be a numeric value")
        elif oil_shock <= -100:
            errors.append(
                f"'oil_price_shock_pct' value {oil_shock}% implies a zero or negative oil price, "
                "which is not a valid market equilibrium"
            )
        elif oil_shock > 500:
            warnings.append(
                f"'oil_price_shock_pct' value {oil_shock}% implies a more than 6x price increase; "
                "MarketSim demand elasticity calibration may not hold at this magnitude"
            )

        gas_shock = params["natural_gas_price_change_pct"]
        if not isinstance(gas_shock, (int, float)):
            errors.append("'natural_gas_price_change_pct' must be a numeric value")
        elif gas_shock <= -100:
            errors.append(
                f"'natural_gas_price_change_pct' value {gas_shock}% implies a zero or negative "
                "natural gas price, which is not a valid market equilibrium"
            )
        elif abs(gas_shock) > 300:
            warnings.append(
                f"'natural_gas_price_change_pct' value {gas_shock}% is extremely large in "
                "magnitude; verify scenario assumption against historical natural gas price spikes"
            )

        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append("'disruption_duration_months' must be a numeric value")
        elif duration <= 0:
            errors.append("'disruption_duration_months' must be positive")
        elif duration > 24:
            warnings.append(
                f"'disruption_duration_months' value {duration} exceeds 24 months; "
                "MarketSim is calibrated for short-run disruptions and may understate "
                "structural demand shifts at longer horizons"
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through as-is.

        The real implementation would translate these into MarketSim's input format,
        which includes scenario configuration files specifying price shock vectors by
        energy carrier and time period, as well as sector-level demand baseline overrides.
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the MarketSim (BOEM) model.

        Not yet implemented. The real implementation requires:
            1. Translating price shock parameters into MarketSim's scenario input format
               (regional and sectoral price vectors by time period).
            2. Invoking the MarketSim model via its Python API or CLI interface.
            3. Collecting output files containing consumer and producer surplus estimates,
               fuel-switching volumes, and welfare decomposition tables.
            4. Mapping MarketSim sector and region codes to pipeline standardized identifiers.
            5. Handling edge cases where price shocks push demand to zero in specific sectors.

        Raises:
            NotImplementedError: Always, until the BOEM MarketSim codebase is integrated.
        """
        raise NotImplementedError(
            "MarketSimAdapter.execute() is not yet implemented. "
            "Integration requires: (1) access to the BOEM MarketSim model codebase and "
            "calibration data from BOEM's Office of Resource Evaluation, (2) regional "
            "demand elasticity matrices and baseline consumption data by sector, (3) a "
            "compatible Python or compiled-binary execution environment, and (4) output "
            "parsers for consumer/producer surplus tables and fuel-switching volumes by "
            "energy carrier and sector."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through, wrapping in standardized ModelOutput.

        The real implementation would parse MarketSim output tables into structured
        surplus change arrays by sector and region, fuel-switching volume matrices by
        carrier, and a scalar net welfare impact estimate.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )
