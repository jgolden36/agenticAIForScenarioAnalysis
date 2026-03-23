"""Adapter stub for the Energy Flux US Gas Power Build-Out Constraint Model v1.0.

This proprietary model analyzes how LNG supply disruptions propagate into US
gas-to-power capacity constraints. It assesses whether domestic gas-fired power
generation capacity can absorb demand shifts caused by LNG export reductions
following a Strait of Hormuz closure.

Real integration requirements:
- License and binary access from Energy Flux
- Input: structured scenario parameters as JSON or CSV
- Output: capacity utilization curves, constraint flags, and price signals by
  region and time step
- No public API; execution will require a local binary or vendor-supplied runner
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model. Each entry is (name, description, unit).
_REQUIRED_PARAMS: list[tuple[str, str, str]] = [
    (
        "lng_supply_disruption_pct",
        "Percentage reduction in LNG supply reaching the US market",
        "percent",
    ),
    (
        "us_gas_price_change_pct",
        "Percentage change in US natural gas spot price relative to baseline",
        "percent",
    ),
    (
        "disruption_duration_months",
        "Duration of the Strait closure and associated LNG supply disruption",
        "months",
    ),
]

_REQUIRED_PARAM_NAMES: frozenset[str] = frozenset(p[0] for p in _REQUIRED_PARAMS)


class EnergyFluxGasPowerAdapter(ModelAdapter):
    """Adapter for the Energy Flux US Gas Power Build-Out Constraint Model v1.0.

    Assesses US gas-to-power capacity constraints arising from LNG supply
    disruptions. Required parameters capture the supply shock magnitude, the
    resulting domestic price response, and the disruption timeline.
    """

    @property
    def model_id(self) -> str:
        return "energy_flux_gas_power"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Energy Flux US Gas Power Build-Out Constraint Model v1.0: assesses "
            "US domestic gas-to-power capacity constraints under LNG supply "
            "disruption scenarios."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Check that all required parameters are present and within plausible ranges.

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult listing any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        missing = _REQUIRED_PARAM_NAMES - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if not missing:
            pct = params["lng_supply_disruption_pct"]
            if not isinstance(pct, (int, float)):
                errors.append("'lng_supply_disruption_pct' must be numeric")
            elif not (0.0 <= pct <= 100.0):
                errors.append(
                    f"'lng_supply_disruption_pct' must be in [0, 100]; got {pct}"
                )

            gas_pct = params["us_gas_price_change_pct"]
            if not isinstance(gas_pct, (int, float)):
                errors.append("'us_gas_price_change_pct' must be numeric")
            elif gas_pct < -50.0 or gas_pct > 500.0:
                warnings.append(
                    f"'us_gas_price_change_pct' of {gas_pct}% is outside the "
                    "historically plausible range [-50, 500]"
                )

            duration = params["disruption_duration_months"]
            if not isinstance(duration, (int, float)):
                errors.append("'disruption_duration_months' must be numeric")
            elif duration <= 0:
                errors.append(
                    f"'disruption_duration_months' must be positive; got {duration}"
                )
            elif duration > 24:
                warnings.append(
                    f"'disruption_duration_months' of {duration} exceeds 24 months; "
                    "verify this is intentional"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through unchanged.

        The real implementation will serialize these to the format expected by
        the Energy Flux binary (likely JSON or a structured CSV template).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same parameter dictionary (passthrough).
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Energy Flux Gas Power model.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: This stub is not yet integrated with the
                Energy Flux proprietary binary. Integration requires: (1) a
                valid Energy Flux license, (2) the model binary or vendor API
                endpoint, and (3) an agreed input/output schema from the vendor.
        """
        raise NotImplementedError(
            "EnergyFluxGasPowerAdapter.execute is not yet implemented. "
            "Integration requires the proprietary Energy Flux US Gas Power "
            "Build-Out Constraint Model v1.0 binary and vendor-supplied "
            "input/output schema. Contact Energy Flux to obtain access."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse raw model output into a standardized ModelOutput.

        The real implementation will decode vendor-specific output formats
        (CSV, JSON, or binary) into the ModelOutput schema. Expected output
        fields include capacity utilization by region, constraint flags, and
        implied gas price paths.

        Args:
            raw: Raw output from execute (passthrough for now).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"parse_status": "passthrough"},
        )
