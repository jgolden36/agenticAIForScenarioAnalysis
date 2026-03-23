"""Adapter stub for the Global Gas Model (GGM).

GGM is a global gas trade flow optimization model that solves for least-cost
allocation of LNG and pipeline gas across regions subject to capacity
constraints. Under Strait of Hormuz closure scenarios, it determines how global
LNG flows re-route around the Persian Gulf supply gap, which buyers bear the
highest price exposure, and what residual supply-demand imbalances persist.

Real integration requirements:
- Access to the GGM model codebase or executable (typically GAMS or Python)
- A calibrated baseline reflecting current (2026) LNG trade flows and
  infrastructure capacities
- Input: binary closure flag, Qatar and UAE export loss fractions, rerouting
  availability flag, and disruption duration
- Output: regional price paths, trade flow matrices, rerouting cost estimates,
  and market clearing status by time step
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters required by this model. Each entry is (name, description, unit).
_REQUIRED_PARAMS: list[tuple[str, str, str]] = [
    (
        "strait_closure_flag",
        "Whether the Strait of Hormuz is closed (True) or open (False)",
        "boolean",
    ),
    (
        "qatar_lng_export_loss_pct",
        "Percentage reduction in Qatari LNG exports due to the closure",
        "percent",
    ),
    (
        "rerouting_available",
        "Whether alternative LNG supply routes or sources are available (True/False)",
        "boolean",
    ),
    (
        "disruption_duration_months",
        "Duration of the Strait closure and associated LNG supply disruption",
        "months",
    ),
]

_REQUIRED_PARAM_NAMES: frozenset[str] = frozenset(p[0] for p in _REQUIRED_PARAMS)


class GGMAdapter(ModelAdapter):
    """Adapter for the Global Gas Model (GGM).

    Optimizes global LNG and pipeline gas trade flows under supply disruptions.
    GGM is the primary tool for determining how Persian Gulf LNG shortfalls are
    absorbed globally: which regions substitute toward pipeline gas, which face
    unmet demand, and at what cost.
    """

    @property
    def model_id(self) -> str:
        return "ggm"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.LNG

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Global Gas Model (GGM): optimization model for global LNG and pipeline "
            "gas trade flow allocation under Strait of Hormuz closure, determining "
            "regional price paths, rerouting costs, and residual supply gaps."
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
            closure_flag = params["strait_closure_flag"]
            if not isinstance(closure_flag, bool):
                errors.append(
                    f"'strait_closure_flag' must be a boolean; got {type(closure_flag).__name__}"
                )

            qatar_loss = params["qatar_lng_export_loss_pct"]
            if not isinstance(qatar_loss, (int, float)):
                errors.append("'qatar_lng_export_loss_pct' must be numeric")
            elif not (0.0 <= qatar_loss <= 100.0):
                errors.append(
                    f"'qatar_lng_export_loss_pct' must be in [0, 100]; got {qatar_loss}"
                )
            elif qatar_loss == 0.0 and params.get("strait_closure_flag") is True:
                warnings.append(
                    "'qatar_lng_export_loss_pct' is 0 while 'strait_closure_flag' is True; "
                    "verify that Qatar's exports are unaffected by the closure"
                )

            rerouting = params["rerouting_available"]
            if not isinstance(rerouting, bool):
                errors.append(
                    f"'rerouting_available' must be a boolean; got {type(rerouting).__name__}"
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
        GGM (typically a GAMS data file or structured Python config dict),
        mapping scenario parameters onto specific supply nodes and capacity
        constraint overrides in the model's network topology.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same parameter dictionary (passthrough).
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Global Gas Model optimization.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: This stub is not yet integrated with the GGM
                executable or codebase. Integration requires: (1) access to the
                GGM model (GAMS license or Python codebase), (2) a calibrated
                2026 baseline trade flow matrix, (3) network topology data for
                LNG terminals and pipeline interconnects, and (4) a runner
                script that injects scenario parameters into the model's data
                layer.
        """
        raise NotImplementedError(
            "GGMAdapter.execute is not yet implemented. "
            "Integration requires access to the Global Gas Model (GGM) codebase "
            "or compiled executable, a calibrated 2026 LNG trade flow baseline, "
            "and a GAMS license (if the model is GAMS-based). Obtain access "
            "through the model's institutional host."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse raw GGM output into a standardized ModelOutput.

        The real implementation will read GGM solution files (GAMS .gdx or
        CSV exports) and extract: regional LNG prices, bilateral trade flow
        matrices, rerouting cost estimates, capacity utilization by terminal,
        and market clearing status for each time step.

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
