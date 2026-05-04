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
from src.models.macro.macro_kernel import (
    compute_macro_outcomes,
    compute_regional_macro_outcomes,
)

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Capex pass-through coefficient when ``trade_disruption_spec`` carries a
# ``trade_cost_multiplier``. Mirrors the energy-adapter helper in
# macro_kernel: a 1.0 multiplier (no shock) maps to zero, each unit above
# 1.0 maps to a +30 pp synthetic capex price-shock channel.
_TRADE_COST_TO_CAPEX_PASSTHROUGH: float = 0.3

# Bilateral trade-flow elasticity to a trade-cost multiplier. Standard
# Anderson-van Wincoop / log-gravity literature reports trade elasticities
# in the 4-7 range; -0.4 here is the bilateral-flow response per 1pp of
# trade-cost shock and is deliberately conservative.
_TRADE_FLOW_ELASTICITY: float = -0.4

# Region-pair trade exposure to Strait of Hormuz disruption. Used to scale
# the bilateral_trade_flow_change_pct heuristic. Calibrated from IMF DOTS
# 2024 to capture the share of bilateral trade that transits Hormuz.
_HORMUZ_TRADE_EXPOSURE: dict[tuple[str, str], float] = {
    ("MENA_GCC", "CHN"): 0.85,
    ("MENA_GCC", "IND"): 0.75,
    ("MENA_GCC", "EU"): 0.55,
    ("MENA_GCC", "US"): 0.20,
    ("MENA_GCC", "ROW"): 0.50,
    ("CHN", "MENA_GCC"): 0.65,
    ("IND", "MENA_GCC"): 0.55,
    ("EU", "MENA_GCC"): 0.45,
    ("US", "MENA_GCC"): 0.15,
}

# Terms-of-trade response per percent oil price shock, by region.
# Positive values mean the region's terms of trade improve on a positive
# oil shock (it exports oil); negative means they deteriorate. Calibrated
# from IMF (2022) Regional Outlook ME / IEA (2023) WEO.
_TERMS_OF_TRADE_OIL_RESPONSE: dict[str, float] = {
    "US": -0.0005,
    "CHN": -0.0030,
    "IND": -0.0050,
    "EU": -0.0040,
    "MENA_GCC": 0.0090,
    "MENA_OTHER": 0.0030,
    "SSA": -0.0035,
    "LAC": -0.0010,
    "ROW": -0.0010,
}

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

        When a ``JuliaConfig`` is supplied the ``JuliaAdapter`` base class
        invokes the real ``solve_mpsge`` Julia function via juliacall (or
        a subprocess fallback). Otherwise this method runs a closed-form
        long-run macro fallback backed by ``macro_kernel`` so the
        long-run / strategic tier always has a runnable model on the
        cluster MVP.

        Mechanics of the analytical fallback:

          * Build a ``commodity_shocks`` dict from
            ``commodity_price_shocks`` plus the explicit
            ``oil_price_shock_pct`` (the explicit oil shock takes
            precedence over any ``commodity_price_shocks['oil']``).
          * If ``trade_disruption_spec.trade_cost_multiplier`` is
            present and != 1.0, add a synthetic ``capex`` shock equal
            to ``(mult - 1) * 100 * 0.3`` to capture the capital-good
            inflation channel. Mirrors ``macro_kernel
            .derive_macro_from_energy_shocks``.
          * Forward the shocks to ``compute_macro_outcomes`` /
            ``compute_regional_macro_outcomes`` with
            ``regime="long_run"``. Long-run scaling is linear in
            ``duration_months``.
          * Augment with bilateral trade-flow change estimates
            (gravity-style attenuation by trade-cost multiplier and
            Hormuz-trade exposure) and terms-of-trade per region.
        """
        if self._config is not None:
            return super().execute(inputs)

        params = inputs if isinstance(inputs, dict) else dict(inputs)

        oil_shock_pct = float(params["oil_price_shock_pct"])
        trade_spec = params.get("trade_disruption_spec") or {}
        commodity_shocks_in = params.get("commodity_price_shocks") or {}
        duration_months = float(params["disruption_duration_months"])

        # Build the commodity-shocks dict used by the kernel. Explicit
        # oil shock takes precedence; remaining keys are passed through
        # (lowercased; the kernel re-normalises again defensively).
        commodity_shocks: dict[str, float] = {}
        for k, v in commodity_shocks_in.items():
            try:
                commodity_shocks[str(k).lower()] = float(v)
            except (TypeError, ValueError):
                continue
        commodity_shocks["oil"] = oil_shock_pct

        # Trade-cost shock -> synthetic capex channel.
        trade_cost_mult = 1.0
        try:
            trade_cost_mult = float(
                trade_spec.get("trade_cost_multiplier", 1.0)
            )
        except (TypeError, ValueError):
            trade_cost_mult = 1.0
        if abs(trade_cost_mult - 1.0) > 1e-6:
            commodity_shocks["capex"] = (
                (trade_cost_mult - 1.0) * 100.0 * _TRADE_COST_TO_CAPEX_PASSTHROUGH
            )

        kernel_out = compute_macro_outcomes(
            commodity_shocks,
            duration_months,
            regime="long_run",
        )
        regional_rows = compute_regional_macro_outcomes(
            commodity_shocks,
            duration_months,
            regime="long_run",
        )

        # Per-region GDP / CPI dicts surfaced as flat keys for the
        # synthesizer (matches the long-run-strategic schema).
        gdp_by_region = {
            row["region"]: row["gdp_impact_pct"] for row in regional_rows
        }
        cpi_by_region = {
            row["region"]: row["cpi_inflation_pct"] for row in regional_rows
        }
        welfare_by_region = {
            row["region"]: row["welfare_pct_change"] for row in regional_rows
        }
        consumption_by_region = {
            row["region"]: row["consumption_impact_pct"]
            for row in regional_rows
        }

        # Terms-of-trade impact per region (oil-driven only; sufficient
        # for a long-run heuristic since oil is the dominant Hormuz
        # commodity).
        terms_of_trade = {
            region: round(coef * oil_shock_pct, 4)
            for region, coef in _TERMS_OF_TRADE_OIL_RESPONSE.items()
        }

        # Bilateral trade-flow change heuristic (gravity attenuation).
        bilateral: dict[str, dict[str, float]] = {}
        for (origin, dest), exposure in _HORMUZ_TRADE_EXPOSURE.items():
            change = (
                _TRADE_FLOW_ELASTICITY
                * (trade_cost_mult - 1.0)
                * 100.0
                * exposure
            )
            bilateral.setdefault(origin, {})[dest] = round(change, 3)

        outputs: dict[str, Any] = {
            "oil_price_shock_pct": oil_shock_pct,
            "trade_cost_multiplier": trade_cost_mult,
            "commodity_price_shocks": commodity_shocks,
            "disruption_duration_months": duration_months,
            "gdp_impact_pct": kernel_out["gdp_impact_pct"],
            "cpi_inflation_pct": kernel_out["cpi_inflation_pct"],
            "consumption_impact_pct": kernel_out["consumption_impact_pct"],
            "welfare_pct_change": kernel_out["welfare_pct_change"],
            "wage_impact_pct": kernel_out["wage_impact_pct"],
            "interest_rate_impact_pct": kernel_out["interest_rate_impact_pct"],
            "sectoral_output_pct_change": kernel_out["sectoral_output_pct_change"],
            "regional_vars": regional_rows,
            "gdp_impact_pct_by_region": gdp_by_region,
            "cpi_inflation_pct_by_region": cpi_by_region,
            "consumption_impact_pct_by_region": consumption_by_region,
            "welfare_pct_change_by_region": welfare_by_region,
            "equivalent_variation_pct_by_region": welfare_by_region,
            "terms_of_trade_pct_change_by_region": terms_of_trade,
            "bilateral_trade_flow_change_pct": bilateral,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "macro_kernel long-run regime (Hamilton/Kilian/Blanchard-"
                    "Galí/Baffes/Massol-Rifaat); IMF Regional Economic Outlook "
                    "Middle East (2022) for terms-of-trade response; "
                    "Anderson & van Wincoop (2003) gravity elasticities."
                ),
                "trade_cost_to_capex_passthrough": _TRADE_COST_TO_CAPEX_PASSTHROUGH,
                "trade_flow_elasticity": _TRADE_FLOW_ELASTICITY,
                "terms_of_trade_oil_response": dict(_TERMS_OF_TRADE_OIL_RESPONSE),
                "_macro_source": "mpsge_jl_kernel_fallback",
                "kernel_inputs": kernel_out.get("_inputs", {}),
                "note": (
                    "Analytical MVP path. Provide a JuliaConfig in "
                    "configs/model_configs/mpsge_jl.yaml to invoke the "
                    "real solve_mpsge() Julia function. Real path needs: "
                    "(1) Julia >=1.9 with MPSGE.jl + JuMP, (2) GTAP v10+ "
                    "database, (3) juliacall or Julia subprocess."
                ),
            },
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
