"""AISDBAdapter — AIS vessel tracking database adapter.

AISdb processes Automatic Identification System (AIS) vessel tracking data
to calibrate rerouting distances, transit times, and fleet utilization changes
under Strait of Hormuz closure scenarios. It operates at the commodity
analytical level, producing physical disruption parameters that feed
commodity-level price and supply models.

Real implementation requirements:
- AISdb installation and database connection (PostgreSQL or SQLite backend)
- Preprocessed AIS vessel track data for the Strait of Hormuz region
- Route geometry files for alternative passages (Cape of Good Hope, Suez Canal)
- Vessel registry cross-reference for type classification
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for AISdb to run
REQUIRED_PARAMS = frozenset(
    {
        "strait_closure_flag",
        "alternative_routes",
        "vessel_types",
    }
)

# Recognized vessel type labels
VALID_VESSEL_TYPES = frozenset(
    {
        "tanker",
        "lng_carrier",
        "bulk_carrier",
        "container",
        "general_cargo",
        "chemical_tanker",
    }
)

# Recognized alternative route identifiers
VALID_ALTERNATIVE_ROUTES = frozenset(
    {
        "cape_of_good_hope",
        "suez_canal",
        "northern_sea_route",
        "none",
    }
)


class AISDBAdapter(ModelAdapter):
    """Adapter for the AISdb vessel tracking and rerouting calibration model.

    AISdb ingests historical AIS track data and computes rerouting statistics
    (additional transit days, fleet size requirements, fuel cost multipliers)
    when the Strait of Hormuz is closed and vessels must use alternative routes.
    """

    @property
    def model_id(self) -> str:
        return "aisdb"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.SHIPPING

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "AISdb: AIS vessel tracking database model for rerouting calibration. "
            "Processes historical vessel track data to estimate additional transit "
            "times, fleet utilization changes, and fuel cost multipliers when Strait "
            "of Hormuz traffic is diverted to alternative passages."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate AISdb input parameters.

        Checks that all required parameters are present, that
        strait_closure_flag is boolean, that alternative_routes is a
        non-empty list of recognized route identifiers, and that vessel_types
        is a non-empty list of recognized vessel type labels.

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
            # Cannot validate values if keys are absent
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Validate strait_closure_flag
        closure_flag = params["strait_closure_flag"]
        if not isinstance(closure_flag, bool):
            errors.append(
                f"'strait_closure_flag' must be a boolean; got {type(closure_flag).__name__}"
            )

        # Validate alternative_routes
        alt_routes = params["alternative_routes"]
        if not isinstance(alt_routes, list) or len(alt_routes) == 0:
            errors.append("'alternative_routes' must be a non-empty list of route identifiers")
        else:
            unknown = set(alt_routes) - VALID_ALTERNATIVE_ROUTES
            if unknown:
                errors.append(
                    f"'alternative_routes' contains unrecognized identifiers: {sorted(unknown)}. "
                    f"Valid options: {sorted(VALID_ALTERNATIVE_ROUTES)}"
                )

        # Validate vessel_types
        vessel_types = params["vessel_types"]
        if not isinstance(vessel_types, list) or len(vessel_types) == 0:
            errors.append("'vessel_types' must be a non-empty list of vessel type labels")
        else:
            unknown_types = set(vessel_types) - VALID_VESSEL_TYPES
            if unknown_types:
                errors.append(
                    f"'vessel_types' contains unrecognized labels: {sorted(unknown_types)}. "
                    f"Valid options: {sorted(VALID_VESSEL_TYPES)}"
                )

        # Warn if closure is False but alternative routes are specified
        if isinstance(closure_flag, bool) and not closure_flag and alt_routes:
            warnings.append(
                "'strait_closure_flag' is False but 'alternative_routes' are specified; "
                "rerouting estimates will not be meaningful."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through without transformation.

        The real implementation would serialize params into AISdb query
        configuration (e.g., a dict or config file consumed by the AISdb CLI).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute AISdb rerouting analysis.

        Not yet implemented. The real implementation will:
        1. Connect to the AISdb PostgreSQL/SQLite database
        2. Query historical track data for the Strait of Hormuz corridor
        3. Apply closure flag to filter or reroute affected vessel tracks
        4. Compute rerouting statistics per vessel type and alternative route
        5. Return transit time deltas, fleet utilization changes, and fuel multipliers

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real AISdb integration is built.
        """
        raise NotImplementedError(
            "AISdb adapter is a stub. Real implementation requires: "
            "(1) an AISdb installation with a populated vessel track database, "
            "(2) route geometry files for Cape of Good Hope and Suez Canal alternatives, "
            "(3) a vessel registry cross-reference for type classification, and "
            "(4) the AISdb Python API or CLI for programmatic query execution."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw AISdb output through without transformation.

        The real implementation would parse AISdb query results into the
        standardized ModelOutput schema, extracting rerouting distance deltas,
        additional transit days, and fleet utilization multipliers per vessel type.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
