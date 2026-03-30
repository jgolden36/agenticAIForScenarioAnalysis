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
- juliacall (preferred) or Julia subprocess for Python invocation
- MPSGE model file (.jl) encoding the trade and production structure
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.julia_adapter import JuliaAdapter, JuliaConfig
from src.models.base import ModelOutput, ValidationResult

# Parameters that must be present for MPSGE.jl to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "trade_disruption_spec",
        "commodity_price_shocks",
        "disruption_duration_months",
    }
)


class MPSGEJLAdapter(JuliaAdapter):
    """Adapter for MPSGE.jl general equilibrium model with GTAP data.

    Inherits from JuliaAdapter for juliacall in-process execution with
    zero-copy NumPy array transfer. Falls back to subprocess if juliacall
    is unavailable.

    MPSGE.jl models the long-run general equilibrium response to commodity
    price shocks originating from the Strait of Hormuz closure. Using GTAP
    multi-region social accounting data, it traces factor reallocation,
    terms-of-trade effects, and welfare changes across trading blocs.
    """

    def __init__(self, config: JuliaConfig | None = None) -> None:
        super().__init__(config)

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

    @property
    def julia_function_name(self) -> str:
        return "solve_mpsge"

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

    def translate_inputs_for_julia(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert parameters to Julia-compatible keyword arguments.

        The real implementation would structure these as the shock vectors
        and elasticity parameters expected by the MPSGE.jl solve function.

        Args:
            params: Validated parameter dictionary.

        Returns:
            Dict of keyword arguments for the Julia solve_mpsge function.
        """
        return {
            "oil_price_shock_pct": params["oil_price_shock_pct"],
            "trade_disruption_spec": params["trade_disruption_spec"],
            "commodity_price_shocks": params["commodity_price_shocks"],
            "disruption_duration_months": params["disruption_duration_months"],
        }

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Delegate to translate_inputs_for_julia."""
        return self.translate_inputs_for_julia(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the MPSGE.jl general equilibrium model.

        Not yet implemented. When a JuliaConfig is provided, the JuliaAdapter
        base class handles execution via juliacall (in-process, zero-copy
        array transfer) or subprocess fallback. Until then, raises
        NotImplementedError.

        The real implementation will:
        1. Call solve_mpsge() via juliacall with shock vectors as NumPy arrays
        2. Receive welfare changes, trade flows, and sectoral results zero-copy
        3. Parse into structured ModelOutput for long-run strategic synthesis

        Note: Import juliacall BEFORE torch to avoid libstdc++ conflicts.
        Use PackageCompiler.jl sysimages to eliminate JIT latency.
        """
        if self._config is not None:
            return super().execute(inputs)

        raise NotImplementedError(
            "MPSGEJLAdapter.execute() is not yet implemented. "
            "Provide a JuliaConfig to enable execution via juliacall or subprocess. "
            "Requirements: (1) Julia >=1.9 with MPSGE.jl and JuMP packages, "
            "(2) GTAP database v10+ with calibration scripts, "
            "(3) juliacall (pip install juliacall) or Julia subprocess. "
            "Consider custom sysimages via PackageCompiler.jl to eliminate JIT latency."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse MPSGE.jl output into standardized ModelOutput.

        The real implementation extracts equivalent variation welfare changes
        by region, bilateral trade flow adjustments, and sectoral output
        changes from the Julia result dict.
        """
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
