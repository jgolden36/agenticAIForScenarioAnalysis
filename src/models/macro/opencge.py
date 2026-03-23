"""OpenCGEAdapter — OpenCGE computable general equilibrium model adapter.

OpenCGE is an open-source Python implementation of a static computable general
equilibrium (CGE) model. It is used in this pipeline as a cross-validation
instrument for MPSGE.jl and PyCGE: running the same commodity price shocks
through multiple CGE implementations and comparing outputs identifies
model-specific artefacts versus robust structural findings.

OpenCGE operates at the long-run macro/strategic analytical level, receiving
commodity price shocks from the commodity tier and producing multi-sector
welfare and trade flow results for synthesis.

Real implementation requirements:
- OpenCGE Python package (available on PyPI or GitHub)
- Social accounting matrix (SAM) calibrated to the relevant economy/region
- Sector mapping from pipeline commodity categories to CGE sectors
- Configuration specifying closure rules (e.g., full employment vs. fixed
  capital, numeraire choice)
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for OpenCGE to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "commodity_price_shocks",
        "disruption_duration_months",
    }
)


class OpenCGEAdapter(ModelAdapter):
    """Adapter for the OpenCGE computable general equilibrium model.

    OpenCGE provides an open-source CGE implementation for cross-validating
    long-run general equilibrium results. It takes commodity-level price
    shocks as exogenous perturbations and solves for the resulting equilibrium
    adjustments in factor markets, sectoral output, and household welfare.
    Its open-source nature makes it suitable for sensitivity analysis and
    reproducibility verification alongside licensed CGE models.
    """

    @property
    def model_id(self) -> str:
        return "opencge"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "OpenCGE: open-source Python computable general equilibrium model. Used as a "
            "cross-validation instrument for MPSGE.jl and PyCGE, applying the same "
            "commodity price shocks through an independent CGE implementation to identify "
            "robust structural findings versus model-specific artefacts."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate OpenCGE input parameters.

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
        to OpenCGE's sector indexing (which depends on the SAM being used),
        constructing the exogenous shock vector in the format expected by the
        OpenCGE solver.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the OpenCGE model.

        Not yet implemented. The real implementation will:
        1. Load the calibrated social accounting matrix (SAM) for the target
           economy/region
        2. Map pipeline commodity price shocks to CGE sector indices
        3. Invoke the OpenCGE solver to compute the new equilibrium
        4. Extract welfare changes (EV/CV), sectoral output changes, and
           factor price adjustments
        5. Return structured ModelOutput for comparison with MPSGE.jl and PyCGE

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real OpenCGE integration is built.
        """
        raise NotImplementedError(
            "OpenCGEAdapter.execute() is not yet implemented. "
            "Real implementation requires: (1) the OpenCGE Python package (installable "
            "from PyPI or the OpenCGE GitHub repository), (2) a social accounting matrix "
            "(SAM) calibrated to the relevant economy or region, (3) a sector mapping file "
            "translating pipeline commodity categories to CGE sector indices in the SAM, "
            "and (4) configuration specifying model closure rules (full employment or fixed "
            "capital, numeraire choice, household income closure)."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw OpenCGE output through without transformation.

        The real implementation would parse OpenCGE solver output (typically
        a pandas DataFrame or dict of equilibrium variable values) into the
        standardized ModelOutput schema, extracting welfare changes, sectoral
        output adjustments, and factor price responses.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
