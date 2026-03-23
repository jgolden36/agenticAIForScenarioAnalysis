"""Adapter for the POLES-JRC global energy model.

Reference:
    European Commission Joint Research Centre — POLES-JRC (Prospective Outlook on
    Long-term Energy Systems). A detailed global partial-equilibrium model covering
    energy supply, demand, and trade across all energy carriers.

Real implementation requirements:
    - Licensed POLES-JRC model installation (JRC software distribution).
    - Scenario configuration files in POLES XML/CSV input format.
    - A Windows or Linux environment with the POLES runtime (typically compiled Fortran/C++).
    - Access to the JRC baseline calibration dataset (regional energy balances, IEA data).
    - Output: regional energy supply/demand balances, oil and gas price trajectories,
      rerouting cost impacts on trade flows, energy substitution paths.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model.
_REQUIRED_PARAMS: list[tuple[str, str]] = [
    ("supply_loss_mbd", "float — barrels per day lost from Strait closure, in millions"),
    ("disruption_duration_months", "float — expected duration of the supply disruption"),
    ("rerouting_cost_multiplier", "float — multiplier on baseline shipping costs due to Cape of Good Hope rerouting (e.g., 1.35 = 35% increase)"),
    ("insurance_premium_increase_pct", "float — percentage point increase in war-risk insurance premiums on Persian Gulf routes"),
    ("substitute_energy_availability", "float — index [0, 1] representing availability of substitute energy sources (1 = full substitutability, 0 = none)"),
]

_REQUIRED_PARAM_NAMES: set[str] = {name for name, _ in _REQUIRED_PARAMS}


class POLESJRCAdapter(ModelAdapter):
    """Adapter stub for the POLES-JRC global energy partial-equilibrium model.

    POLES-JRC models detailed global energy supply and demand dynamics across all
    energy carriers (oil, gas, coal, renewables, nuclear) with regional resolution.
    In this pipeline it is the primary source for oil and LNG price trajectories
    under supply disruption, incorporating rerouting costs and insurance premiums
    as friction parameters on trade flows.

    Outputs fed downstream:
        - Brent crude oil price path ($/bbl, monthly)
        - LNG price path ($/MMBtu, by importing region)
        - Regional energy supply/demand balances
        - Trade flow rerouting volume and cost
        - Energy substitution rates by carrier and region
    """

    @property
    def model_id(self) -> str:
        return "poles_jrc"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "POLES-JRC (Prospective Outlook on Long-term Energy Systems) — European "
            "Commission JRC partial-equilibrium global energy model. Covers all energy "
            "carriers with regional detail; used here for oil and LNG price trajectories "
            "and trade-flow impacts under Strait of Hormuz disruption."
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
                "POLES-JRC calibration may not reflect structural shifts at this horizon"
            )

        rerouting = params["rerouting_cost_multiplier"]
        if not isinstance(rerouting, (int, float)):
            errors.append("'rerouting_cost_multiplier' must be a numeric value")
        elif rerouting < 1.0:
            errors.append(
                f"'rerouting_cost_multiplier' value {rerouting} is less than 1.0; "
                "rerouting always increases costs relative to baseline"
            )
        elif rerouting > 3.0:
            warnings.append(
                f"'rerouting_cost_multiplier' value {rerouting} implies a cost more than "
                "3x baseline; verify scenario assumption for Cape of Good Hope rerouting"
            )

        insurance = params["insurance_premium_increase_pct"]
        if not isinstance(insurance, (int, float)):
            errors.append("'insurance_premium_increase_pct' must be a numeric value")
        elif insurance < 0:
            errors.append("'insurance_premium_increase_pct' cannot be negative")
        elif insurance > 500:
            warnings.append(
                f"'insurance_premium_increase_pct' value {insurance}% is extremely high; "
                "historical war-risk spikes peaked around 100–200% during Gulf conflicts"
            )

        substitute = params["substitute_energy_availability"]
        if not isinstance(substitute, (int, float)):
            errors.append("'substitute_energy_availability' must be a numeric value")
        elif not (0.0 <= substitute <= 1.0):
            errors.append(
                f"'substitute_energy_availability' value {substitute} must be in [0, 1]"
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through as-is.

        The real implementation would write these values into POLES-JRC scenario
        configuration files (XML or CSV format) in the model's input directory,
        overriding the relevant baseline assumptions.
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the POLES-JRC model.

        Not yet implemented. The real implementation requires:
            1. Writing scenario parameters into POLES-JRC input configuration files.
            2. Invoking the POLES runtime via subprocess (typically a CLI call to the
               compiled binary with the scenario configuration path as argument).
            3. Monitoring execution progress via log file polling.
            4. Parsing output CSV/XML files for price paths, energy balances, and
               trade flow tables.
            5. Mapping POLES region codes to pipeline region identifiers.

        Raises:
            NotImplementedError: Always, until the JRC model distribution is integrated.
        """
        raise NotImplementedError(
            "POLESJRCAdapter.execute() is not yet implemented. "
            "Integration requires: (1) a licensed POLES-JRC model installation from "
            "the European Commission JRC, (2) scenario configuration files in POLES "
            "XML/CSV input format, (3) a compatible runtime environment (Windows or Linux "
            "with the POLES compiled binary), and (4) output parsers for POLES CSV/XML "
            "result files covering price paths, regional energy balances, and trade flows."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through, wrapping in standardized ModelOutput.

        The real implementation would parse POLES-JRC output CSV files into structured
        price path arrays, regional balance tables, and trade flow matrices keyed by
        POLES region codes.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )
