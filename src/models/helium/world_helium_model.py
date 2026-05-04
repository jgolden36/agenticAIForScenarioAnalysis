"""Adapter stub for the World Helium Model (IFP Energies Nouvelles).

The World Helium Model is a global market equilibrium model of helium
supply and demand. It is developed by IFP Energies Nouvelles and tracks
helium production, storage, liquefaction, and end-use demand across all
major supply regions (United States, Qatar, Russia, Algeria, Australia).

Under Strait of Hormuz closure scenarios, Qatar's helium export capacity
is severely impaired — Qatar accounts for roughly 30% of global helium
supply, and its exports transit the Strait. This adapter parameterizes
that supply shock and elicits the model's equilibrium price and allocation
response.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Closed-form helium market equilibrium parameters used by the
# analytical-MVP execute() path. The IFP Energies Nouvelles World
# Helium Model proper would solve a full multi-region partial
# equilibrium with explicit liquefaction, storage, and trade
# routing. The values below let the HELIUM_SEMICONDUCTORS commodity
# system contribute a working model to the MVP pipeline while the
# licensed IFP EN binary remains unavailable.
#
# Qatar's share of global helium production. USGS Mineral Commodity
# Summaries 2024 (helium chapter) — Qatar accounts for ~30% of global
# helium output, second only to the United States.
_QATAR_GLOBAL_SHARE: float = 0.30
# Short-run price elasticity of helium demand. Massol & Rifaat
# (2018), "Phasing out the U.S. Federal Helium Reserve: Policy
# insights from a world helium model", Resource and Energy
# Economics 54, estimate short-run demand elasticities on the order
# of -0.3 across major end-use sectors.
_HELIUM_DEMAND_ELASTICITY: float = -0.3
# Reference baseline equilibrium spot price ($/Mscf). Roughly the
# 2024 BLM Crude Helium Price Index level for Grade-A liquid helium
# from major producers.
_HELIUM_BASELINE_USD_PER_MSCF: float = 280.0
# US Bureau of Land Management Cliffside reserve and private inventory
# capacity treated as the pool from which strategic-reserve releases
# are drawn (MMscf). Massol & Rifaat (2018) quote the BLM crude
# helium tank capacity at ~10,000 MMscf historically; the adapter
# accepts a release volume in MMscf via parameters and converts to a
# share of one year of Qatari supply.
_QATAR_ANNUAL_SUPPLY_MMSCF: float = 1_700.0  # ~30% of ~5,700 MMscf/yr global
# End-use sector demand shares (2024 USGS, IHS Markit). Used to
# distribute equilibrium allocation under rationing.
_SECTOR_DEMAND_SHARES: dict[str, float] = {
    "mri_medical": 0.32,
    "semiconductors": 0.28,
    "cryogenics_research": 0.20,
    "aerospace_defense": 0.12,
    "other": 0.08,
}


class WorldHeliumModelAdapter(ModelAdapter):
    """Adapter stub for the World Helium Model (IFP Energies Nouvelles).

    Real implementation requirements:
    - Access to the IFP Energies Nouvelles World Helium Model binary or
      licensed codebase. Contact IFP EN for licensing and data access.
    - Baseline calibration dataset: global helium production capacity by
      source, liquefaction capacity, storage inventories, and end-use
      demand by sector (MRI, semiconductor, aerospace, cryogenics).
    - Input/output format documentation for the IFP EN model's native
      interface (file-based or API-based, to be determined on access).
    - Qatar-specific supply capacity data: Ras Laffan helium plants
      (RasGas/QatarGas), storage buffer, and shipping schedules.
    """

    @property
    def model_id(self) -> str:
        return "world_helium_model"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.HELIUM_SEMICONDUCTORS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "World Helium Model (IFP Energies Nouvelles): global helium market "
            "equilibrium model tracking supply, liquefaction, storage, and end-use "
            "demand across major producing regions. Used to assess price and "
            "allocation impacts of Qatar helium supply disruption under Strait of "
            "Hormuz closure scenarios."
        )

    # ------------------------------------------------------------------
    # Required parameters and their validation rules
    # ------------------------------------------------------------------

    REQUIRED_PARAMS: dict[str, str] = {
        "qatar_helium_supply_loss_pct": (
            "Percentage of Qatar helium export capacity lost due to Strait "
            "closure (0–100). Qatar supplies ~30% of global helium."
        ),
        "disruption_duration_months": (
            "Duration of the supply disruption in months. Drives inventory "
            "drawdown trajectory and demand-response timing."
        ),
        "strategic_reserve_release": (
            "Volume of strategic helium reserve released in response to the "
            "disruption, in million standard cubic feet (MMscf). Zero if no "
            "reserve release is assumed."
        ),
    }

    PARAM_BOUNDS: dict[str, tuple[float, float]] = {
        "qatar_helium_supply_loss_pct": (0.0, 100.0),
        "disruption_duration_months": (0.0, 36.0),
        "strategic_reserve_release": (0.0, 10_000.0),
    }

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate required parameters and check value ranges.

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult with errors for missing or out-of-range parameters
            and warnings for borderline values.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check for required parameters
        for param_name in self.REQUIRED_PARAMS:
            if param_name not in params:
                errors.append(
                    f"Missing required parameter '{param_name}': "
                    f"{self.REQUIRED_PARAMS[param_name]}"
                )

        # Validate bounds for parameters that are present
        for param_name, (low, high) in self.PARAM_BOUNDS.items():
            if param_name not in params:
                continue  # already caught above
            value = params[param_name]
            try:
                fval = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"Parameter '{param_name}' must be numeric; got {value!r}."
                )
                continue
            if not (low <= fval <= high):
                errors.append(
                    f"Parameter '{param_name}' = {fval} is outside the valid "
                    f"range [{low}, {high}]."
                )

        # Scenario-specific sanity warnings
        if "qatar_helium_supply_loss_pct" in params:
            try:
                pct = float(params["qatar_helium_supply_loss_pct"])
                if pct > 90.0:
                    warnings.append(
                        f"qatar_helium_supply_loss_pct = {pct}% implies near-total "
                        "loss of Qatar supply. Verify this assumption reflects both "
                        "Ras Laffan plant shutdown and tanker embargo, not just one."
                    )
            except (TypeError, ValueError):
                pass

        if "disruption_duration_months" in params and "strategic_reserve_release" in params:
            try:
                duration = float(params["disruption_duration_months"])
                reserve = float(params["strategic_reserve_release"])
                if duration > 6.0 and reserve == 0.0:
                    warnings.append(
                        "disruption_duration_months > 6 with zero strategic reserve "
                        "release may understate market relief mechanisms. Confirm "
                        "whether the Bureau of Land Management Cliffside reserve "
                        "drawdown is modeled."
                    )
            except (TypeError, ValueError):
                pass

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through unchanged.

        The real implementation will serialize these to the IFP EN model's
        native input format (expected to be file-based; format TBD on access).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary, passed through unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the analytical-MVP helium market equilibrium.

        Closed-form constant-elasticity equilibrium that lets the
        HELIUM_SEMICONDUCTORS commodity system contribute a working
        model to the MVP pipeline without the licensed IFP EN
        World Helium Model.

        Mechanics:

          * Effective supply gap = ``Qatar share * Qatar loss``
            minus the strategic reserve release (converted from
            MMscf to a share of Qatari annual output).
          * Equilibrium price multiplier = ``1 + gap / |epsilon_d|``
            (constant-elasticity inversion: rationing the demand
            elasticity against the supply gap).
          * Demand rationing volume scales linearly with the
            unmet-share of demand.
          * Sector allocation shares are renormalised so essential
            sectors (MRI, semiconductors) absorb a smaller share
            of the rationing than discretionary sectors.

        Returns:
            ModelOutput with equilibrium price, sector allocation,
            and analytical-MVP metadata.
        """
        if not isinstance(inputs, dict):
            raise TypeError(
                "WorldHeliumModel inputs must be a dict from translate_inputs(); "
                f"got {type(inputs)}"
            )

        qatar_loss_pct = float(inputs["qatar_helium_supply_loss_pct"])
        duration_months = float(inputs["disruption_duration_months"])
        reserve_release_mmscf = float(inputs["strategic_reserve_release"])

        # All supply quantities expressed as monthly flows so the
        # gross gap, reserve offset, and global supply are
        # directly comparable. Global annual supply is implied
        # by Qatari supply and Qatar's global share.
        global_annual_mmscf = _QATAR_ANNUAL_SUPPLY_MMSCF / max(_QATAR_GLOBAL_SHARE, 1e-6)
        global_monthly_mmscf = global_annual_mmscf / 12.0

        gross_gap = _QATAR_GLOBAL_SHARE * (qatar_loss_pct / 100.0)
        if duration_months > 0:
            reserve_flow_mmscf_per_month = reserve_release_mmscf / duration_months
            reserve_share = reserve_flow_mmscf_per_month / max(
                global_monthly_mmscf, 1e-6
            )
        else:
            reserve_share = 0.0
        effective_gap = max(0.0, gross_gap - reserve_share)

        price_multiplier = 1.0 + effective_gap / abs(_HELIUM_DEMAND_ELASTICITY)
        equilibrium_price = _HELIUM_BASELINE_USD_PER_MSCF * price_multiplier
        price_change_pct = (price_multiplier - 1.0) * 100.0

        global_supply_lost_mmscf = (
            global_annual_mmscf * effective_gap * (duration_months / 12.0)
        )

        priority_weights = {
            "mri_medical": 0.5,
            "semiconductors": 0.6,
            "cryogenics_research": 1.2,
            "aerospace_defense": 1.0,
            "other": 1.5,
        }
        weighted = {
            sector: _SECTOR_DEMAND_SHARES[sector] * priority_weights[sector]
            for sector in _SECTOR_DEMAND_SHARES
        }
        total_weight = sum(weighted.values()) or 1.0
        rationing_share_by_sector = {
            sector: round(w / total_weight, 4) for sector, w in weighted.items()
        }
        sector_allocation_share = {
            sector: round(
                _SECTOR_DEMAND_SHARES[sector]
                * (1.0 - effective_gap * rationing_share_by_sector[sector]
                   / max(_SECTOR_DEMAND_SHARES[sector], 1e-6)),
                4,
            )
            for sector in _SECTOR_DEMAND_SHARES
        }

        inventory_drawdown_months = (
            reserve_release_mmscf
            / max(_QATAR_ANNUAL_SUPPLY_MMSCF / 12.0, 1.0)
            if reserve_release_mmscf > 0
            else 0.0
        )

        outputs = {
            "equilibrium_price_usd_per_mscf": round(equilibrium_price, 2),
            "baseline_price_usd_per_mscf": _HELIUM_BASELINE_USD_PER_MSCF,
            "price_change_pct": round(price_change_pct, 2),
            "effective_supply_gap_pct": round(effective_gap * 100.0, 3),
            "demand_rationing_mmscf": round(global_supply_lost_mmscf, 2),
            "sector_allocation_share": sector_allocation_share,
            "rationing_share_by_sector": rationing_share_by_sector,
            "inventory_drawdown_months": round(inventory_drawdown_months, 2),
            "qatar_helium_supply_loss_pct": qatar_loss_pct,
            "disruption_duration_months": duration_months,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "USGS Mineral Commodity Summaries 2024 (helium); "
                    "Massol & Rifaat (2018) Resource and Energy Economics 54."
                ),
                "qatar_global_share": _QATAR_GLOBAL_SHARE,
                "demand_elasticity": _HELIUM_DEMAND_ELASTICITY,
                "baseline_global_supply_mmscf": global_annual_mmscf,
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass through ModelOutput; wrap dicts.

        The analytical-MVP execute() already returns a fully formed
        ModelOutput, so this method exists only to support the abstract
        ``ModelAdapter`` contract and any future real-engine integration
        that returns raw dicts.
        """
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )
