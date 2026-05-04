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

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# US baseline oil consumption (mb/d), EIA STEO 2025 reference. Used for
# the consumer-surplus triangle.
_US_OIL_CONSUMPTION_MBD: float = 19.0
# US baseline natural gas consumption (Tcf/yr -> bcf/d ~= 88), EIA STEO 2025.
_US_GAS_CONSUMPTION_BCFD: float = 88.0
# Reference oil and natural gas prices for surplus calculation (USD).
_OIL_BASELINE_USD_PER_BBL: float = 80.0
_GAS_BASELINE_USD_PER_MMBTU: float = 3.5
# Short-run elasticities of demand by carrier. Hamilton (2009 Brookings)
# for oil; Auffhammer & Rubin (2018 J Env Econ Mgmt) for gas.
_DEMAND_ELASTICITY_OIL: float = -0.06
_DEMAND_ELASTICITY_GAS: float = -0.10
# Cross-elasticity between oil and gas (heat-content substitution).
_CROSS_ELASTICITY: float = 0.05
# Sector consumption shares (US average), EIA AEO 2024.
_OIL_SECTOR_SHARES: dict[str, float] = {
    "transport": 0.69,
    "industrial": 0.23,
    "residential": 0.04,
    "commercial": 0.04,
}
_GAS_SECTOR_SHARES: dict[str, float] = {
    "industrial": 0.32,
    "residential": 0.16,
    "commercial": 0.13,
    "electric_power": 0.39,
}

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
        """Execute the analytical-MVP MarketSim consumer-surplus model.

        Closed-form approximation of the BOEM MarketSim partial-
        equilibrium framework. Real MarketSim invocation requires the
        BOEM codebase + calibration matrices; this fallback gives the
        OIL tier a welfare-loss model alongside POLES-JRC and
        Bornstein-Krusell-Rebelo.

        Mechanics:

          * Triangle-rule consumer-surplus loss for oil and gas:
            ``CS_loss = 0.5 * Q * P * Δ * (1 + |ε| * Δ/2)``,
            where ``Δ`` is the fractional price change.
          * Fuel-switching volume from the cross-elasticity: positive
            oil shock pulls additional gas demand at rate
            ``cross * oil_pct/100 * gas_baseline``.
          * Implied demand destruction in mb/d from the own-price
            elasticity.
          * Producer surplus change is positive on a price rise (the
            consumer surplus loss is partially redistributed to
            producers; rest is deadweight). Heuristic split: producers
            capture 60% of the consumer-surplus drop on a positive
            shock; deadweight is the residual.
          * Surplus values scaled by ``duration_months/12`` to get a
            cumulative impact over the disruption window.
        """
        params = inputs if isinstance(inputs, dict) else dict(inputs)

        oil_pct = float(params["oil_price_shock_pct"])
        gas_pct = float(params["natural_gas_price_change_pct"])
        duration_months = float(params["disruption_duration_months"])

        oil_delta = oil_pct / 100.0
        gas_delta = gas_pct / 100.0
        duration_scaler = max(0.0, duration_months / 12.0)

        # Annual oil consumption in barrels.
        oil_q_bbl_yr = _US_OIL_CONSUMPTION_MBD * 1e6 * 365.0
        gas_q_mmbtu_yr = _US_GAS_CONSUMPTION_BCFD * 1e6 * 365.0 * 1.037  # 1 bcf ~= 1.037 MMBtu (HHV)

        # Consumer-surplus loss in USD (annualised), then scaled by duration.
        # Multiply by 0.5 because triangle, by Δ for height, and add the
        # elasticity quadratic correction term.
        oil_cs_loss = (
            0.5
            * oil_q_bbl_yr
            * _OIL_BASELINE_USD_PER_BBL
            * oil_delta
            * (1.0 + abs(_DEMAND_ELASTICITY_OIL) * oil_delta / 2.0)
        )
        gas_cs_loss = (
            0.5
            * gas_q_mmbtu_yr
            * _GAS_BASELINE_USD_PER_MMBTU
            * gas_delta
            * (1.0 + abs(_DEMAND_ELASTICITY_GAS) * gas_delta / 2.0)
        )
        oil_cs_loss_bn = oil_cs_loss * duration_scaler / 1e9
        gas_cs_loss_bn = gas_cs_loss * duration_scaler / 1e9
        total_cs_loss_bn = oil_cs_loss_bn + gas_cs_loss_bn

        # Producer-surplus change: 60% redistribution from consumers to
        # producers on a positive shock, sign-aware.
        oil_ps_change_bn = oil_cs_loss_bn * 0.6
        gas_ps_change_bn = gas_cs_loss_bn * 0.6
        net_welfare_bn = -(total_cs_loss_bn) + oil_ps_change_bn + gas_ps_change_bn

        # Demand destruction (mb/d) from own-price elasticity.
        oil_demand_destruction_mbd = (
            _US_OIL_CONSUMPTION_MBD * _DEMAND_ELASTICITY_OIL * oil_delta
        )
        gas_demand_destruction_bcfd = (
            _US_GAS_CONSUMPTION_BCFD * _DEMAND_ELASTICITY_GAS * gas_delta
        )

        # Fuel switching from cross-elasticity. Positive oil shock
        # increases gas demand and vice versa; convert oil-displaced
        # mb/d to MMBtu/yr equivalents using ~5.8 MMBtu/bbl.
        cross_oil_to_gas_mmbtu = (
            _CROSS_ELASTICITY * oil_delta * _US_GAS_CONSUMPTION_BCFD * 1e6 * 365.0 * 1.037
            * duration_scaler
        )
        cross_gas_to_oil_bbl = (
            _CROSS_ELASTICITY * gas_delta * _US_OIL_CONSUMPTION_MBD * 1e6 * 365.0
            * duration_scaler
        )

        # Sectoral CS-loss split (proportional to baseline shares).
        cs_loss_by_sector_oil = {
            sec: round(share * oil_cs_loss_bn, 3)
            for sec, share in _OIL_SECTOR_SHARES.items()
        }
        cs_loss_by_sector_gas = {
            sec: round(share * gas_cs_loss_bn, 3)
            for sec, share in _GAS_SECTOR_SHARES.items()
        }

        outputs: dict[str, Any] = {
            "oil_price_shock_pct": oil_pct,
            "natural_gas_price_change_pct": gas_pct,
            "disruption_duration_months": duration_months,
            "consumer_surplus_loss_oil_bn_usd": round(oil_cs_loss_bn, 3),
            "consumer_surplus_loss_gas_bn_usd": round(gas_cs_loss_bn, 3),
            "consumer_surplus_loss_bn_usd": round(total_cs_loss_bn, 3),
            "producer_surplus_change_oil_bn_usd": round(oil_ps_change_bn, 3),
            "producer_surplus_change_gas_bn_usd": round(gas_ps_change_bn, 3),
            "net_welfare_impact_bn_usd": round(net_welfare_bn, 3),
            "oil_demand_destruction_mbd": round(oil_demand_destruction_mbd, 4),
            "gas_demand_destruction_bcfd": round(gas_demand_destruction_bcfd, 4),
            "fuel_switching_oil_to_gas_mmbtu": round(cross_oil_to_gas_mmbtu, 1),
            "fuel_switching_gas_to_oil_bbl": round(cross_gas_to_oil_bbl, 1),
            "cs_loss_by_sector_oil_bn_usd": cs_loss_by_sector_oil,
            "cs_loss_by_sector_gas_bn_usd": cs_loss_by_sector_gas,
            "us_baseline_oil_consumption_mbd": _US_OIL_CONSUMPTION_MBD,
            "us_baseline_gas_consumption_bcfd": _US_GAS_CONSUMPTION_BCFD,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "EIA STEO 2025 baseline consumption; Hamilton (2009 "
                    "Brookings) oil demand elasticity; Auffhammer & "
                    "Rubin (2018 JEEM) gas demand elasticity; EIA AEO "
                    "2024 sector shares."
                ),
                "demand_elasticity_oil": _DEMAND_ELASTICITY_OIL,
                "demand_elasticity_gas": _DEMAND_ELASTICITY_GAS,
                "cross_elasticity": _CROSS_ELASTICITY,
                "oil_sector_shares": dict(_OIL_SECTOR_SHARES),
                "gas_sector_shares": dict(_GAS_SECTOR_SHARES),
                "note": (
                    "Analytical MVP path. Real BOEM MarketSim integration "
                    "would require: (1) BOEM model codebase + calibration "
                    "matrices, (2) regional demand elasticity tables, "
                    "(3) sector-level baseline consumption data."
                ),
            },
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
