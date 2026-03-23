"""Adapter for the Bornstein-Krusell-Rebelo World Equilibrium Model of the Oil Market.

Reference:
    Bornstein, G., Krusell, P., & Rebelo, S. — World Equilibrium Model of the Oil Market.
    A structural general-equilibrium model for supply disruption analysis.

Real implementation requirements:
    - Access to the original Bornstein-Krusell-Rebelo model codebase (MATLAB or Fortran).
    - Calibration data files (steady-state equilibrium, preference parameters, production
      cost schedules for all major producing regions).
    - A solver capable of handling nonlinear GE equilibrium conditions (e.g., KNITRO or
      MATLAB's fsolve).
    - Output: equilibrium oil price path, producer/consumer welfare, SPR drawdown schedule,
      OPEC response function realization.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model. Each entry is (name, type_description).
_REQUIRED_PARAMS: list[tuple[str, str]] = [
    ("supply_loss_mbd", "float — barrels per day lost from Strait closure, in millions"),
    ("disruption_duration_months", "float — expected duration of the supply disruption"),
    ("spr_release_mbd", "float — strategic petroleum reserve release rate, in mb/d"),
    ("opec_spare_capacity_mbd", "float — available OPEC spare capacity that can be activated, in mb/d"),
    ("demand_elasticity_override", "float — short-run price elasticity of demand override; use None to apply model default"),
]

_REQUIRED_PARAM_NAMES: set[str] = {name for name, _ in _REQUIRED_PARAMS}


class BornsteinKrusellRebeloAdapter(ModelAdapter):
    """Adapter stub for the Bornstein-Krusell-Rebelo World Equilibrium Model of the Oil Market.

    This is a structural general-equilibrium model that characterizes the global oil market
    as an intertemporal optimization problem with exhaustible resources, heterogeneous producers,
    and a strategic OPEC bloc. It is used here to produce equilibrium oil price paths and
    welfare decompositions under supply disruption scenarios.

    Outputs fed downstream:
        - Equilibrium Brent crude price path ($/bbl, quarterly)
        - Consumer welfare loss (billion USD)
        - Producer surplus change by region
        - SPR drawdown trajectory
        - OPEC production response path
    """

    @property
    def model_id(self) -> str:
        return "bornstein_krusell_rebelo"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Bornstein-Krusell-Rebelo World Equilibrium Model of the Oil Market. "
            "Structural GE model for oil supply disruption analysis with intertemporal "
            "optimization, exhaustible resource dynamics, and strategic OPEC behavior."
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
        supply_loss = params["supply_loss_mbd"]
        if not isinstance(supply_loss, (int, float)):
            errors.append("'supply_loss_mbd' must be a numeric value")
        elif not (0.0 <= supply_loss <= 20.0):
            errors.append(
                f"'supply_loss_mbd' value {supply_loss} is outside plausible range [0, 20] mb/d"
            )

        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append("'disruption_duration_months' must be a numeric value")
        elif duration <= 0:
            errors.append("'disruption_duration_months' must be positive")
        elif duration > 36:
            warnings.append(
                f"'disruption_duration_months' value {duration} exceeds 36 months; "
                "model calibration may not be reliable at this horizon"
            )

        spr = params["spr_release_mbd"]
        if not isinstance(spr, (int, float)):
            errors.append("'spr_release_mbd' must be a numeric value")
        elif spr < 0:
            errors.append("'spr_release_mbd' cannot be negative")
        elif spr > 4.0:
            warnings.append(
                f"'spr_release_mbd' value {spr} mb/d exceeds typical IEA coordinated release "
                "ceiling of ~4 mb/d; verify scenario assumption"
            )

        opec_spare = params["opec_spare_capacity_mbd"]
        if not isinstance(opec_spare, (int, float)):
            errors.append("'opec_spare_capacity_mbd' must be a numeric value")
        elif opec_spare < 0:
            errors.append("'opec_spare_capacity_mbd' cannot be negative")
        elif opec_spare > 10.0:
            warnings.append(
                f"'opec_spare_capacity_mbd' value {opec_spare} mb/d is implausibly large; "
                "historical maximum is roughly 5–6 mb/d"
            )

        elasticity = params["demand_elasticity_override"]
        if elasticity is not None:
            if not isinstance(elasticity, (int, float)):
                errors.append("'demand_elasticity_override' must be numeric or None")
            elif not (-2.0 <= elasticity <= 0.0):
                warnings.append(
                    f"'demand_elasticity_override' value {elasticity} is outside the "
                    "typical short-run range [-2.0, 0.0]; confirm this is intentional"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through as-is.

        The real implementation would serialize these to the model's native input format
        (e.g., a MATLAB .mat file or a structured text configuration file).
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Bornstein-Krusell-Rebelo model.

        Not yet implemented. The real implementation requires:
            1. Serializing inputs to the model's native format (MATLAB struct or equivalent).
            2. Invoking the solver (MATLAB engine or compiled binary) via subprocess or
               MATLAB Engine API for Python (matlab.engine).
            3. Polling for convergence of the nonlinear GE equilibrium conditions.
            4. Reading the equilibrium price path and welfare decomposition from output files.
            5. Handling non-convergence gracefully and returning a failed ModelOutput.

        Raises:
            NotImplementedError: Always, until the model binary/codebase is integrated.
        """
        raise NotImplementedError(
            "BornsteinKrusellRebeloAdapter.execute() is not yet implemented. "
            "Integration requires: (1) access to the Bornstein-Krusell-Rebelo model "
            "codebase and calibration files, (2) a MATLAB or compiled-binary execution "
            "environment, (3) a solver for the nonlinear GE equilibrium system, and "
            "(4) output parsers for the equilibrium price path and welfare decomposition."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through, wrapping in standardized ModelOutput.

        The real implementation would parse MATLAB output structs or text files into
        the standardized fields: equilibrium price path, welfare changes, SPR trajectory,
        and OPEC response path.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )
