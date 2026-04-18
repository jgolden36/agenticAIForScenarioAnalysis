"""AISProjectAdapter — AIS spatial analysis for transit time and fleet utilization.

AIS_project performs spatial analysis of AIS vessel track data to estimate
transit time changes and fleet size requirements when Strait of Hormuz traffic
is rerouted via the Cape of Good Hope. It operates at the commodity analytical
level, complementing AISdb by focusing on fleet-level utilization impacts rather
than per-vessel track calibration.

Real implementation requirements:
- Processed AIS track dataset for vessels transiting the Strait of Hormuz
- Cape of Good Hope route geometry and distance tables
- Fleet composition data (number of active vessels by type)
- Voyage simulation logic to estimate additional days at sea and repositioning costs
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for AIS_project to run
REQUIRED_PARAMS = frozenset(
    {
        "strait_closure_flag",
        "rerouting_via_cape",
        "fleet_size_change_pct",
        "disruption_duration_months",
    }
)


class AISProjectAdapter(ModelAdapter):
    """Adapter for the AIS_project spatial analysis model.

    AIS_project estimates fleet utilization changes and transit time penalties
    when Strait of Hormuz traffic is redirected. The primary rerouting scenario
    is via the Cape of Good Hope, which adds approximately 9–10 days of transit
    time per voyage and effectively removes vessels from the active fleet during
    the extended voyage.
    """

    @property
    def model_id(self) -> str:
        return "ais_project"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.SHIPPING

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "AIS_project: Spatial analysis of AIS vessel track data for transit "
            "time and fleet utilization estimation under Strait closure. Computes "
            "additional voyage days and effective fleet capacity reduction when "
            "vessels reroute via the Cape of Good Hope."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate AIS_project input parameters.

        Checks that all required parameters are present. Validates types and
        plausible ranges for numeric parameters and flags logical inconsistencies
        (e.g., closure is False but Cape rerouting is True).

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult with errors for any missing or invalid parameters.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check required parameters exist
        missing = REQUIRED_PARAMS - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Validate strait_closure_flag
        closure_flag = params["strait_closure_flag"]
        if not isinstance(closure_flag, bool):
            errors.append(
                f"'strait_closure_flag' must be a boolean; got {type(closure_flag).__name__}"
            )

        # Validate rerouting_via_cape
        cape_flag = params["rerouting_via_cape"]
        if not isinstance(cape_flag, bool):
            errors.append(
                f"'rerouting_via_cape' must be a boolean; got {type(cape_flag).__name__}"
            )

        # Validate fleet_size_change_pct
        fleet_change = params["fleet_size_change_pct"]
        if not isinstance(fleet_change, (int, float)):
            errors.append(
                f"'fleet_size_change_pct' must be numeric; got {type(fleet_change).__name__}"
            )
        elif not (-100.0 <= fleet_change <= 100.0):
            errors.append(
                f"'fleet_size_change_pct' must be in [-100, 100]; got {fleet_change}"
            )

        # Validate disruption_duration_months
        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append(
                f"'disruption_duration_months' must be numeric; got {type(duration).__name__}"
            )
        elif duration <= 0:
            errors.append(
                f"'disruption_duration_months' must be positive; got {duration}"
            )
        elif duration > 24:
            warnings.append(
                f"'disruption_duration_months' is {duration}, which exceeds the "
                "expected scenario range (0–24 months). Verify this is intentional."
            )

        # Logical consistency check
        if (
            isinstance(closure_flag, bool)
            and isinstance(cape_flag, bool)
            and not closure_flag
            and cape_flag
        ):
            warnings.append(
                "'strait_closure_flag' is False but 'rerouting_via_cape' is True; "
                "Cape rerouting is only meaningful when the Strait is closed."
            )

        if (
            isinstance(closure_flag, bool)
            and isinstance(cape_flag, bool)
            and closure_flag
            and not cape_flag
        ):
            warnings.append(
                "'strait_closure_flag' is True but 'rerouting_via_cape' is False; "
                "model will assume no rerouting, which may understate disruption costs."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through without transformation.

        The real implementation would convert params into the spatial analysis
        configuration expected by AIS_project (e.g., a JSON config or CLI flags
        specifying closure region, rerouting corridor, and fleet inventory snapshot).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute AIS_project spatial analysis.

        Not yet implemented. The real implementation will:
        1. Load AIS vessel track data for the Strait of Hormuz corridor
        2. Apply the closure flag to identify affected voyage legs
        3. Reroute affected voyages via the Cape of Good Hope (adding ~9–10 days)
        4. Compute fleet utilization reduction as a function of rerouting days
           and disruption duration
        5. Return additional transit days, fleet utilization multiplier, and
           implied tanker rate changes

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real AIS_project integration is built.
        """
        raise NotImplementedError(
            "AIS_project adapter is a stub. Real implementation requires: "
            "(1) a processed AIS vessel track dataset covering Strait of Hormuz transits, "
            "(2) route geometry and distance tables for the Cape of Good Hope corridor, "
            "(3) a fleet composition inventory (vessel counts by type and deadweight tonnage), "
            "and (4) voyage simulation logic to compute additional sea days and tanker rate impacts."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw AIS_project output through without transformation.

        The real implementation would parse spatial analysis results into the
        standardized ModelOutput schema, extracting transit time deltas, fleet
        utilization multipliers, and tanker freight rate changes by vessel type.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
