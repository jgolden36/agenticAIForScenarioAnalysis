"""CAPRI model adapter.

CAPRI (Common Agricultural Policy Regionalised Impact) is a partial-equilibrium
model for regional agricultural policy impact analysis. It assesses how
fertilizer price shocks and energy cost increases propagate through regional
agricultural production and trade under crisis scenarios.

Real integration requirements:
    - CAPRI software installation (GAMS-based, Windows or Linux CLI)
    - CAPRI data directory with baseline scenario data
    - GAMS license and installation
    - Access to CAPRI model repository and regional database (CAPREG)
    - Configuration of CAPRI run scripts with scenario-specific shocks
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "fertilizer_price_shock_pct",
    "energy_price_change_pct",
    "disruption_duration_months",
]


class CAPRIAdapter(ModelAdapter):
    """Adapter for the CAPRI partial-equilibrium agricultural policy model.

    CAPRI models regional agricultural production, consumption, and trade
    responses to input price shocks. Under Strait of Hormuz closure scenarios,
    it captures how fertilizer cost increases (driven by natural gas supply
    disruption) reduce crop yields and alter regional food trade balances.
    """

    @property
    def model_id(self) -> str:
        return "capri"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "CAPRI (Common Agricultural Policy Regionalised Impact): partial-equilibrium "
            "model assessing regional agricultural production and trade responses to "
            "fertilizer price shocks and energy cost increases."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required CAPRI parameters are present and in range.

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

        if "energy_price_change_pct" in params:
            val = params["energy_price_change_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'energy_price_change_pct' must be numeric")

        if "disruption_duration_months" in params:
            val = params["disruption_duration_months"]
            if not isinstance(val, (int, float)):
                errors.append("'disruption_duration_months' must be numeric")
            elif val <= 0:
                errors.append("'disruption_duration_months' must be > 0")
            elif val > 24:
                warnings.append(
                    f"'disruption_duration_months' = {val} exceeds typical CAPRI "
                    "scenario horizon; results may extrapolate beyond calibrated range"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation writes CAPRI scenario files.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute CAPRI — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: CAPRI integration is pending. Real implementation
                must invoke the CAPRI GAMS run script via subprocess, passing
                scenario shock parameters through CAPRI's scenario configuration
                interface, and collect output from the CAPRI results database.
        """
        raise NotImplementedError(
            "CAPRIAdapter.execute is not yet implemented. "
            "Real integration requires: (1) a GAMS installation with the CAPRI model "
            "repository, (2) writing scenario shock files to the CAPRI scenario directory, "
            "(3) invoking the CAPRI GAMS entry point via subprocess, and "
            "(4) parsing the CAPRI results database (GDX or CSV output)."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses CAPRI result files.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
