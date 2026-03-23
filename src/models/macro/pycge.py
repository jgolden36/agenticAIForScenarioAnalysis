"""PyCGEAdapter — pycge / cge_modeling computable general equilibrium adapter.

pycge (and related cge_modeling packages) provide Python-native CGE
implementations that complement OpenCGE and MPSGE.jl in the pipeline's
long-run macro/strategic tier. Running multiple CGE implementations with
identical shock inputs enables cross-model consistency checking and
sensitivity analysis: results that appear across all implementations are
more robust than those specific to a single model's parameterization or
numerical solver.

Real implementation requirements:
- pycge or cge_modeling Python package
- Social accounting matrix (SAM) compatible with the chosen package
- Sector mapping from pipeline commodity categories to SAM sectors
- Solver configuration (tolerance, iteration limits, closure rules)
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for PyCGE to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "commodity_price_shocks",
        "disruption_duration_months",
    }
)


class PyCGEAdapter(ModelAdapter):
    """Adapter for the pycge / cge_modeling general equilibrium model.

    PyCGE provides an additional Python-native CGE implementation for
    cross-validation and sensitivity analysis alongside OpenCGE and MPSGE.jl.
    It accepts commodity-level price shocks as exogenous perturbations and
    solves for factor market clearing, sectoral output adjustments, and
    household welfare changes in a long-run equilibrium framework.
    """

    @property
    def model_id(self) -> str:
        return "pycge"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "pycge/cge_modeling: Python computable general equilibrium model for "
            "additional CGE cross-validation. Provides an independent long-run equilibrium "
            "solution for commodity price shocks, enabling sensitivity analysis and "
            "identification of results robust across multiple CGE implementations."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate PyCGE input parameters.

        Checks that all required parameters are present. Validates that
        oil_price_shock_pct is numeric, commodity_price_shocks is a dict
        mapping commodity names to numeric shock percentages, and
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

        # Validate oil_price_shock_pct
        oil_shock = params["oil_price_shock_pct"]
        if not isinstance(oil_shock, (int, float)):
            errors.append(
                f"'oil_price_shock_pct' must be numeric; got {type(oil_shock).__name__}"
            )
        elif oil_shock < -100.0:
            errors.append(
                f"'oil_price_shock_pct' cannot be less than -100%; got {oil_shock}"
            )
        elif oil_shock > 500.0:
            warnings.append(
                f"'oil_price_shock_pct' is {oil_shock}%, implying more than a 5x price "
                "increase. Verify consistency with commodity-level oil model outputs."
            )

        # Validate commodity_price_shocks
        price_shocks = params["commodity_price_shocks"]
        if not isinstance(price_shocks, dict) or len(price_shocks) == 0:
            errors.append(
                "'commodity_price_shocks' must be a non-empty dict mapping commodity "
                "names to percentage price shocks (e.g., {'lng': 40.0, 'fertilizer': 25.0})"
            )
        else:
            for commodity, shock in price_shocks.items():
                if not isinstance(shock, (int, float)):
                    errors.append(
                        f"'commodity_price_shocks[{commodity!r}]' must be numeric; "
                        f"got {type(shock).__name__}"
                    )
                elif shock < -100.0:
                    errors.append(
                        f"'commodity_price_shocks[{commodity!r}]' cannot be less than "
                        f"-100%; got {shock}"
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

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through without transformation.

        The real implementation would map the standardized price shock dict
        to pycge's sector indexing convention and construct the exogenous
        shock vector in the format expected by the pycge solver interface.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the PyCGE model.

        Not yet implemented. The real implementation will:
        1. Load the calibrated SAM compatible with the pycge package
        2. Map pipeline commodity price shocks to pycge sector indices
        3. Invoke the pycge solver (typically a nonlinear system solver
           via scipy.optimize or a dedicated CGE solver)
        4. Extract welfare changes (EV/CV), sectoral output changes, and
           factor price adjustments
        5. Return structured ModelOutput for comparison with OpenCGE and MPSGE.jl

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real PyCGE integration is built.
        """
        raise NotImplementedError(
            "PyCGEAdapter.execute() is not yet implemented. "
            "Real implementation requires: (1) the pycge or cge_modeling Python package "
            "(available on PyPI or GitHub), (2) a social accounting matrix (SAM) in the "
            "format expected by the chosen package, (3) a sector mapping file translating "
            "pipeline commodity categories to SAM sectors, and (4) solver configuration "
            "specifying tolerance, iteration limits, and model closure rules (e.g., full "
            "employment, fixed government balance, or Johansen closure)."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw PyCGE output through without transformation.

        The real implementation would parse pycge solver output (typically
        a dict or DataFrame of equilibrium variable values) into the
        standardized ModelOutput schema, extracting welfare changes, sectoral
        output adjustments, and factor price responses by sector.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
