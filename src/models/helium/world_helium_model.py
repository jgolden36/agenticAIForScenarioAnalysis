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
        """Execute the World Helium Model.

        Not yet implemented. Requires access to the IFP Energies Nouvelles
        World Helium Model licensed codebase and its calibration dataset.

        Real implementation steps:
        1. Serialize inputs to the model's native input file format.
        2. Invoke the model binary or script via subprocess.
        3. Monitor convergence (equilibrium solver); capture stdout/stderr.
        4. Read output files and pass to parse_outputs.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Until the IFP EN model is integrated.
        """
        raise NotImplementedError(
            "WorldHeliumModelAdapter.execute is a stub. Real implementation requires: "
            "(1) licensed access to the IFP Energies Nouvelles World Helium Model "
            "codebase; (2) baseline calibration data for global helium supply, "
            "liquefaction, storage, and end-use demand by sector; (3) documentation "
            "of the model's native input/output file format. Contact IFP EN for "
            "licensing terms and data access."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through unchanged.

        The real implementation will parse the IFP EN model's output files
        (format TBD) into the standardized ModelOutput schema, extracting
        key variables: equilibrium helium spot price ($/Mscf), allocation
        by end-use sector, inventory trajectory, and demand rationing volume.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output, passed through as-is in this stub.
        """
        return raw
