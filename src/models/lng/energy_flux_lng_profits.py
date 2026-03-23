"""Adapter stub for the Energy Flux US LNG War Profits Model v1.0.

This proprietary model quantifies LNG export revenue windfalls accruing to US
LNG exporters under conflict-driven supply scarcity. It estimates how spot
price premiums and capacity utilization changes translate into export revenue
gains for US terminals during Strait of Hormuz closure scenarios.

Real integration requirements:
- License and binary access from Energy Flux
- Input: spot price premium, capacity utilization rate, and disruption timeline
- Output: incremental export revenue by terminal, market share shifts, and
  implied profit margins under each scenario
- No public API; execution will require a local binary or vendor-supplied runner
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model. Each entry is (name, description, unit).
_REQUIRED_PARAMS: list[tuple[str, str, str]] = [
    (
        "lng_spot_price_premium_pct",
        "Percentage premium of LNG spot price over baseline contract price",
        "percent",
    ),
    (
        "us_export_capacity_utilization",
        "Fraction of US LNG export capacity actively utilized (0.0–1.0)",
        "fraction",
    ),
    (
        "disruption_duration_months",
        "Duration of the Strait closure and associated LNG supply disruption",
        "months",
    ),
]

_REQUIRED_PARAM_NAMES: frozenset[str] = frozenset(p[0] for p in _REQUIRED_PARAMS)


class EnergyFluxLNGProfitsAdapter(ModelAdapter):
    """Adapter for the Energy Flux US LNG War Profits Model v1.0.

    Estimates incremental export revenues and profit margins for US LNG
    exporters under conflict-driven price spikes. Required parameters capture
    the spot market premium, the utilization rate of export terminals, and the
    disruption duration.
    """

    @property
    def model_id(self) -> str:
        return "energy_flux_lng_profits"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Energy Flux US LNG War Profits Model v1.0: quantifies incremental "
            "US LNG export revenues and profit margins arising from conflict-driven "
            "LNG spot price premiums under Strait of Hormuz closure scenarios."
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
            premium = params["lng_spot_price_premium_pct"]
            if not isinstance(premium, (int, float)):
                errors.append("'lng_spot_price_premium_pct' must be numeric")
            elif premium < 0.0:
                errors.append(
                    f"'lng_spot_price_premium_pct' must be non-negative; got {premium}"
                )
            elif premium > 1000.0:
                warnings.append(
                    f"'lng_spot_price_premium_pct' of {premium}% is extremely high; "
                    "verify this is intentional"
                )

            utilization = params["us_export_capacity_utilization"]
            if not isinstance(utilization, (int, float)):
                errors.append("'us_export_capacity_utilization' must be numeric")
            elif not (0.0 <= utilization <= 1.0):
                errors.append(
                    f"'us_export_capacity_utilization' must be in [0.0, 1.0]; "
                    f"got {utilization}"
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

        The real implementation will serialize these into the format expected by
        the Energy Flux binary (likely JSON or a structured CSV template).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same parameter dictionary (passthrough).
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Energy Flux LNG War Profits model.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: This stub is not yet integrated with the
                Energy Flux proprietary binary. Integration requires: (1) a
                valid Energy Flux license, (2) the model binary or vendor API
                endpoint, and (3) an agreed input/output schema from the vendor.
        """
        raise NotImplementedError(
            "EnergyFluxLNGProfitsAdapter.execute is not yet implemented. "
            "Integration requires the proprietary Energy Flux US LNG War Profits "
            "Model v1.0 binary and vendor-supplied input/output schema. "
            "Contact Energy Flux to obtain access."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse raw model output into a standardized ModelOutput.

        The real implementation will decode vendor-specific output formats into
        the ModelOutput schema. Expected output fields include incremental
        revenue by terminal, implied profit margins, and market share shifts
        relative to baseline.

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
