"""MPSGEJLAdapter — MPSGE.jl / GTAP general equilibrium model adapter.

MPSGE.jl is a Julia implementation of the Mathematical Programming System for
General Equilibrium (MPSGE), used here in conjunction with GTAP social accounting
data to model long-run trade and welfare effects of the Strait of Hormuz disruption.
It captures factor market adjustments, terms-of-trade shifts, and welfare
redistribution across regions that short-run models cannot address.

MPSGE.jl operates at the long-run macro/strategic analytical level, receiving
commodity price shock summaries from commodity-level models and producing
multi-region trade flow adjustments, GDP welfare losses, and sectoral employment
shifts as its primary outputs.

Real implementation requirements:
- Julia installation (>=1.9) with MPSGE.jl and JuMP packages
- GTAP database (version 10 or later) in Julia-readable format (GTAPinGAMS or CSV)
- Calibration scripts mapping GTAP sectors to pipeline commodity categories
- Julia subprocess interface or PyJulia (juliacall) for Python invocation
- MPSGE model file (.jl) encoding the trade and production structure
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for MPSGE.jl to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "trade_disruption_spec",
        "commodity_price_shocks",
        "disruption_duration_months",
    }
)


class MPSGEJLAdapter(ModelAdapter):
    """Adapter for MPSGE.jl general equilibrium model with GTAP data.

    MPSGE.jl models the long-run general equilibrium response to commodity
    price shocks originating from the Strait of Hormuz closure. Using GTAP
    multi-region social accounting data, it traces factor reallocation,
    terms-of-trade effects, and welfare changes across trading blocs. In
    this pipeline it provides the long-run trade and welfare baseline against
    which scenario-specific structural shifts are measured.
    """

    @property
    def model_id(self) -> str:
        return "mpsge_jl"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "MPSGE.jl / GTAP: Julia-based Mathematical Programming System for General "
            "Equilibrium with GTAP multi-region social accounting data. Models long-run "
            "factor reallocation, terms-of-trade shifts, and multi-region welfare changes "
            "from sustained commodity price shocks under Strait of Hormuz closure scenarios."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate MPSGE.jl input parameters.

        Checks that all required parameters are present. Validates that
        oil_price_shock_pct is numeric, trade_disruption_spec is a non-empty
        dict describing the trade shock structure, commodity_price_shocks is a
        dict mapping commodity names to numeric shock percentages, and
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

        # Validate trade_disruption_spec
        trade_spec = params["trade_disruption_spec"]
        if not isinstance(trade_spec, dict) or len(trade_spec) == 0:
            errors.append(
                "'trade_disruption_spec' must be a non-empty dict describing the trade "
                "shock (e.g., {'affected_regions': [...], 'trade_cost_multiplier': 1.2})"
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

        The real implementation would serialize params into a Julia Dict or
        a JSON file consumed by the MPSGE.jl model script, overriding the
        calibrated benchmark equilibrium price vectors and trade cost parameters.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the MPSGE.jl general equilibrium model.

        Not yet implemented. The real implementation will:
        1. Serialize input parameters into a Julia-readable configuration
           (JSON file or Julia Dict literal)
        2. Invoke the MPSGE.jl model script via Julia subprocess or juliacall
           (PyJulia), passing the configuration path as an argument
        3. Monitor Julia process output for convergence diagnostics
        4. Parse output JSON/CSV files containing welfare changes, trade flow
           adjustments, and sectoral reallocation results by GTAP region
        5. Return structured ModelOutput for long-run strategic synthesis

        Note: Julia startup time (~10–30 seconds for JIT compilation) should
        be accounted for in pipeline timeout settings. Consider using a
        persistent Julia session (DaemonMode.jl) to amortize startup costs
        across multiple scenario runs.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real MPSGE.jl integration is built.
        """
        raise NotImplementedError(
            "MPSGEJLAdapter.execute() is not yet implemented. "
            "Real implementation requires: (1) a Julia installation (>=1.9) with the "
            "MPSGE.jl and JuMP packages, (2) the GTAP database (v10+) in GTAPinGAMS "
            "or CSV format with calibration scripts mapping GTAP sectors to pipeline "
            "commodity categories, (3) a Julia subprocess interface (via subprocess module) "
            "or juliacall (PyJulia) for Python-to-Julia invocation, and (4) a MPSGE model "
            "file (.jl) encoding the trade and production structure for Hormuz scenarios. "
            "Account for Julia JIT compilation time (~10–30 seconds) in pipeline timeouts."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw MPSGE.jl output through without transformation.

        The real implementation would parse Julia output files (JSON or CSV)
        into the standardized ModelOutput schema, extracting equivalent variation
        welfare changes by region, bilateral trade flow adjustments, and sectoral
        output changes by GTAP region and commodity.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
