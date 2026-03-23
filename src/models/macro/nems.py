"""NEMSAdapter — EIA National Energy Modeling System adapter.

NEMS is the U.S. Energy Information Administration's integrated model of the
U.S. energy system. It projects energy supply, demand, conversion, and prices
across all fuel types under alternative policy and disruption scenarios. In this
pipeline it provides national energy-economy baseline projections and short-run
disruption impacts (inflation pass-through, sectoral demand changes, GDP effects)
driven by the oil and natural gas price paths computed by commodity-level models.

Real implementation requirements:
- Licensed NEMS installation (EIA distributes the model with registration)
- NEMS scenario input files (run control files, data modules) customized for
  disruption scenarios
- Fortran/C compilation environment for the NEMS source code
- Post-processing scripts to extract key output variables from NEMS output tables
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for NEMS to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_path",
        "natural_gas_price_path",
        "disruption_duration_months",
    }
)


class NEMSAdapter(ModelAdapter):
    """Adapter for the EIA National Energy Modeling System (NEMS).

    NEMS produces integrated projections of U.S. energy supply, demand,
    prices, and macroeconomic feedbacks. In this pipeline it operates at the
    short-run macro level, translating commodity-level oil and natural gas
    price paths into GDP, employment, inflation, and sectoral energy demand
    projections for each disruption scenario.
    """

    @property
    def model_id(self) -> str:
        return "nems"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.SHORT_RUN_MACRO

    @property
    def description(self) -> str:
        return (
            "NEMS (EIA): National Energy Modeling System. Integrated U.S. energy-economy "
            "model producing projections of energy supply, demand, prices, and "
            "macroeconomic impacts across all fuel types. Provides short-run GDP, "
            "inflation, and sectoral demand responses to oil and gas price shocks."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate NEMS input parameters.

        Checks that all required parameters are present. Validates that price
        paths are non-empty lists of positive numeric values and that
        disruption_duration_months is a positive number.

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

        # Validate oil_price_path
        oil_path = params["oil_price_path"]
        if not isinstance(oil_path, list) or len(oil_path) == 0:
            errors.append("'oil_price_path' must be a non-empty list of price values ($/bbl)")
        else:
            non_positive = [v for v in oil_path if not isinstance(v, (int, float)) or v <= 0]
            if non_positive:
                errors.append(
                    f"'oil_price_path' contains non-positive or non-numeric values: {non_positive}"
                )
            if max((v for v in oil_path if isinstance(v, (int, float))), default=0) > 500:
                warnings.append(
                    "'oil_price_path' contains values above $500/bbl. "
                    "Verify these are in nominal $/bbl and not percentage changes."
                )

        # Validate natural_gas_price_path
        gas_path = params["natural_gas_price_path"]
        if not isinstance(gas_path, list) or len(gas_path) == 0:
            errors.append(
                "'natural_gas_price_path' must be a non-empty list of price values ($/MMBtu)"
            )
        else:
            non_positive = [v for v in gas_path if not isinstance(v, (int, float)) or v <= 0]
            if non_positive:
                errors.append(
                    "'natural_gas_price_path' contains non-positive or non-numeric values: "
                    f"{non_positive}"
                )

        # Validate disruption_duration_months
        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append(
                f"'disruption_duration_months' must be numeric; got {type(duration).__name__}"
            )
        elif duration <= 0:
            errors.append(f"'disruption_duration_months' must be positive; got {duration}")
        elif duration > 24:
            warnings.append(
                f"'disruption_duration_months' is {duration}, which exceeds the "
                "expected scenario range (0–24 months). Verify this is intentional."
            )

        # Warn if price paths have different lengths
        if (
            isinstance(oil_path, list)
            and isinstance(gas_path, list)
            and len(oil_path) != len(gas_path)
        ):
            warnings.append(
                f"'oil_price_path' has {len(oil_path)} periods but "
                f"'natural_gas_price_path' has {len(gas_path)} periods. "
                "Mismatched lengths may cause interpolation errors in NEMS."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through without transformation.

        The real implementation would serialize params into NEMS run control
        files and data module overrides in the format expected by the NEMS
        Fortran source (typically fixed-format text or binary data files).

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the NEMS model.

        Not yet implemented. The real implementation will:
        1. Write price path overrides into NEMS input data modules
        2. Invoke the NEMS executable via subprocess
        3. Monitor convergence across NEMS's iterative solution modules
        4. Collect output tables (energy prices, quantities, GDP, employment)
        5. Return structured outputs for short-run macro synthesis

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real NEMS integration is built.
        """
        raise NotImplementedError(
            "NEMS adapter is a stub. Real implementation requires: "
            "(1) a licensed NEMS installation from the EIA with appropriate run "
            "control files for disruption scenarios, "
            "(2) a compiled NEMS executable (Fortran/C build environment), "
            "(3) scripts to inject oil and gas price path overrides into NEMS "
            "data modules, and "
            "(4) post-processing scripts to extract GDP, employment, inflation, "
            "and sectoral energy demand from NEMS output tables."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw NEMS output through without transformation.

        The real implementation would parse NEMS output tables into the
        standardized ModelOutput schema, extracting GDP growth, inflation rate,
        sectoral energy demand changes, and energy price projections.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
