"""NRELAdapter — NREL electricity sector baseline and disruption model adapter.

The National Renewable Energy Laboratory (NREL) baseline modeling framework
projects electricity sector dynamics under energy supply disruptions. It
captures how natural gas price increases (driven by LNG supply interruption
from Strait of Hormuz closure) propagate into electricity generation costs,
dispatch switching, renewable acceleration, and retail electricity prices.
This adapter operates at the short-run macro analytical level, with outputs
feeding into economy-wide macro models (NEMS, CGE) as energy cost inputs.

Real implementation requirements:
- NREL Regional Energy Deployment System (ReEDS) or Cambium dataset access
- Scenario configuration specifying natural gas price path overrides
- Python environment with NREL model API or CLI invocation capability
- Baseline capacity and generation data from NREL's Annual Technology Baseline
- Post-processing scripts to extract dispatch, price, and emissions outputs
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.macro.macro_kernel import compute_macro_outcomes

# Parameters that must be present for NREL to run
REQUIRED_PARAMS = frozenset(
    {
        "natural_gas_price_change_pct",
        "electricity_demand_change_pct",
        "disruption_duration_months",
    }
)

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Share of US generation by fuel, EIA AEO 2024 reference case.
_GEN_SHARE_BASELINE: dict[str, float] = {
    "natural_gas": 0.43,
    "coal": 0.16,
    "nuclear": 0.18,
    "renewables": 0.21,
    "other": 0.02,
}
# Retail-price pass-through coefficient on generation cost. Roughly
# half of wholesale moves into retail over a year (EIA AEO 2024 reference
# scenario).
_RETAIL_PASSTHROUGH: float = 0.5
# Retail price impulse per percent natural-gas price change (combines
# generation share and pass-through). 0.45 ~ 0.43 * 1.0 (gas-on-margin
# bid-stack approximation, EIA AEO 2024).
_RETAIL_PRICE_GAS_COEFF: float = 0.45
# Retail price impulse per percent electricity demand change.
_RETAIL_PRICE_DEMAND_COEFF: float = 0.05
# Cap on short-run renewable dispatch shift (fraction of generation
# share). Capacity factors and curtailment limits prevent renewables
# from absorbing more than ~15 pp of dispatch share over a year.
_RENEWABLES_DISPATCH_CAP_PP: float = 15.0
# Coal-substitution coefficient: a 100% gas price shock pulls roughly
# 12 pp of dispatch share toward coal in the short run before regulatory
# limits bind (EIA AEO 2024 elasticities).
_COAL_DISPATCH_COEFF: float = 0.12
# Gas-dispatch contraction per 100% gas price shock.
_GAS_DISPATCH_COEFF: float = -0.07
# CO2 emissions per MWh by fuel, EPA 2024 (kg/MWh).
_CO2_KG_PER_MWH: dict[str, float] = {
    "natural_gas": 400.0,
    "coal": 950.0,
    "nuclear": 0.0,
    "renewables": 0.0,
    "other": 600.0,
}


class NRELAdapter(ModelAdapter):
    """Adapter for the NREL electricity sector baseline and disruption model.

    The NREL framework (ReEDS / Cambium) models electricity generation
    dispatch, capacity investment, and retail price formation under natural
    gas supply disruptions. In this pipeline it translates LNG price shocks
    into electricity sector cost impacts, identifying dispatch switching to
    alternative generation sources and the resulting retail price changes
    that feed into short-run macroeconomic models.
    """

    @property
    def model_id(self) -> str:
        return "nrel"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.SHORT_RUN_MACRO

    @property
    def description(self) -> str:
        return (
            "NREL electricity sector model (ReEDS/Cambium): projects generation dispatch, "
            "capacity investment, and retail electricity price changes under natural gas "
            "supply disruption. Captures fuel switching and renewable acceleration "
            "responses to LNG price shocks from Strait of Hormuz closure."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate NREL input parameters.

        Checks that all required parameters are present. Validates that
        natural_gas_price_change_pct and electricity_demand_change_pct are
        numeric and within plausible ranges, and that
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

        # Validate natural_gas_price_change_pct
        gas_pct = params["natural_gas_price_change_pct"]
        if not isinstance(gas_pct, (int, float)):
            errors.append(
                f"'natural_gas_price_change_pct' must be numeric; got {type(gas_pct).__name__}"
            )
        elif gas_pct < -100.0:
            errors.append(
                f"'natural_gas_price_change_pct' cannot be less than -100%; got {gas_pct}"
            )
        elif gas_pct > 1000.0:
            warnings.append(
                f"'natural_gas_price_change_pct' is {gas_pct}%, which implies more than a "
                "10x price increase. Verify this is consistent with commodity-level LNG outputs."
            )

        # Validate electricity_demand_change_pct
        elec_pct = params["electricity_demand_change_pct"]
        if not isinstance(elec_pct, (int, float)):
            errors.append(
                f"'electricity_demand_change_pct' must be numeric; got {type(elec_pct).__name__}"
            )
        elif not (-50.0 <= elec_pct <= 50.0):
            warnings.append(
                f"'electricity_demand_change_pct' is {elec_pct}%, which is outside the "
                "plausible short-run range of [-50%, +50%]. Verify scenario assumption."
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

        The real implementation would write the natural gas price override and
        demand adjustment into NREL ReEDS scenario input files (CSV or JSON
        configuration) consumed by the ReEDS model run script.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the analytical-MVP NREL electricity sector model.

        Closed-form merit-order / dispatch math. Real implementation
        invokes NREL ReEDS or Cambium; the fallback below replicates the
        first-order outputs (retail price impulse, dispatch shift, CO2
        change, capacity utilisation) using EIA AEO 2024 calibration.

        Mechanics:

          * Retail price impulse =
            ``0.45 * gas_pct + 0.05 * elec_demand_pct``.
          * Coal dispatch share gain = ``0.12 * gas_pct/100`` (capped at
            available coal headroom 0.10 of generation).
          * Renewables dispatch share gain = ``min(15 pp,
            0.10 * gas_pct)``.
          * Gas dispatch share loss absorbs the remainder.
          * CO2 emissions impulse from EPA 2024 fuel intensities.
          * A macro-companion block (gdp/cpi/consumption/welfare) is
            derived via macro_kernel using ``commodity_shocks={'lng':
            gas_pct}`` so the output is comparable to other macro
            adapters; tagged ``_macro_source: nrel_derived``.
        """
        params = inputs if isinstance(inputs, dict) else dict(inputs)

        gas_pct = float(params["natural_gas_price_change_pct"])
        demand_pct = float(params["electricity_demand_change_pct"])
        duration_months = float(params["disruption_duration_months"])

        retail_price_change_pct = round(
            _RETAIL_PRICE_GAS_COEFF * gas_pct
            + _RETAIL_PRICE_DEMAND_COEFF * demand_pct,
            3,
        )

        # Per-fuel dispatch-share changes (percentage points). Sign:
        # positive gas shock pushes dispatch away from gas toward coal
        # and renewables. Headroom caps prevent unphysical reallocation.
        renew_gain_pp = max(
            0.0, min(_RENEWABLES_DISPATCH_CAP_PP, 0.10 * gas_pct)
        )
        coal_gain_pp = max(0.0, min(10.0, _COAL_DISPATCH_COEFF * gas_pct))
        gas_loss_pp = max(
            -_GAS_DISPATCH_COEFF * gas_pct, renew_gain_pp + coal_gain_pp
        )
        # Force conservation: gas loss = renewables gain + coal gain.
        gas_loss_pp = renew_gain_pp + coal_gain_pp

        dispatch_change_pp: dict[str, float] = {
            "natural_gas": -round(gas_loss_pp, 3),
            "coal": round(coal_gain_pp, 3),
            "renewables": round(renew_gain_pp, 3),
            "nuclear": 0.0,
            "other": 0.0,
        }
        # Resulting dispatch shares (re-normalised to sum to 1.0 in case
        # rounding drifts).
        new_share = {
            fuel: max(0.0, _GEN_SHARE_BASELINE[fuel] + dispatch_change_pp.get(fuel, 0.0) / 100.0)
            for fuel in _GEN_SHARE_BASELINE
        }
        share_total = sum(new_share.values()) or 1.0
        new_share = {fuel: round(s / share_total, 4) for fuel, s in new_share.items()}

        # Capacity-utilisation impulse: percent change relative to baseline
        # capacity factor for each fuel. Gas CCs lose utilisation, coal /
        # renewables gain.
        capacity_util_change_pct: dict[str, float] = {
            "natural_gas": round(-7.0 * gas_pct / 100.0, 3),
            "coal": round(12.0 * gas_pct / 100.0, 3),
            "renewables": round(renew_gain_pp / max(_GEN_SHARE_BASELINE["renewables"], 0.01), 3),
            "nuclear": 0.0,
            "other": 0.0,
        }

        # CO2 emissions impulse: weighted sum of fuel-share changes
        # times EPA fuel intensities, expressed as percent change in
        # power-sector CO2 vs. baseline.
        baseline_emissions = sum(
            _GEN_SHARE_BASELINE[f] * _CO2_KG_PER_MWH.get(f, 0.0)
            for f in _GEN_SHARE_BASELINE
        )
        new_emissions = sum(
            new_share[f] * _CO2_KG_PER_MWH.get(f, 0.0)
            for f in _GEN_SHARE_BASELINE
        )
        if baseline_emissions > 0:
            co2_change_pct = (
                (new_emissions / baseline_emissions - 1.0) * 100.0
            )
        else:
            co2_change_pct = 0.0

        # Macro companion outputs (LNG / gas channel). Lets synthesis see
        # a macro-flavoured response from this adapter even before
        # PyCGE / OpenCGE run.
        macro_kernel_out = compute_macro_outcomes(
            commodity_shocks={"lng": gas_pct},
            duration_months=duration_months,
            regime="short_run",
        )

        outputs: dict[str, Any] = {
            "natural_gas_price_change_pct": gas_pct,
            "electricity_demand_change_pct": demand_pct,
            "disruption_duration_months": duration_months,
            "retail_electricity_price_change_pct": retail_price_change_pct,
            "retail_passthrough_coefficient": _RETAIL_PASSTHROUGH,
            "generation_share_baseline": dict(_GEN_SHARE_BASELINE),
            "generation_share_new": new_share,
            "generation_dispatch_pct_change": dispatch_change_pp,
            "capacity_utilization_pct_change": capacity_util_change_pct,
            "co2_emissions_pct_change": round(co2_change_pct, 3),
            "renewables_dispatch_gain_pp": round(renew_gain_pp, 3),
            "coal_dispatch_gain_pp": round(coal_gain_pp, 3),
            # Macro companion (kernel-derived).
            "gdp_impact_pct": macro_kernel_out["gdp_impact_pct"],
            "cpi_inflation_pct": macro_kernel_out["cpi_inflation_pct"],
            "consumption_impact_pct": macro_kernel_out["consumption_impact_pct"],
            "welfare_pct_change": macro_kernel_out["welfare_pct_change"],
            "_macro_source": "nrel_derived",
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "EIA AEO 2024 reference case (generation shares, "
                    "retail pass-through); NREL Cambium 2023 (capacity "
                    "factors); EPA eGRID 2024 (CO2 intensities); "
                    "macro_kernel for the macro companion block."
                ),
                "retail_price_gas_coeff": _RETAIL_PRICE_GAS_COEFF,
                "retail_price_demand_coeff": _RETAIL_PRICE_DEMAND_COEFF,
                "renewables_dispatch_cap_pp": _RENEWABLES_DISPATCH_CAP_PP,
                "co2_kg_per_mwh": dict(_CO2_KG_PER_MWH),
                "_macro_source": "nrel_derived",
                "kernel_inputs": macro_kernel_out.get("_inputs", {}),
                "note": (
                    "Analytical MVP path. Real ReEDS / Cambium "
                    "integration would require: (1) NREL ReEDS install "
                    "with the Cambium dataset, (2) scenario inputs for "
                    "gas-price overrides, (3) ReEDS Python API or CLI."
                ),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw NREL output through without transformation.

        The real implementation would parse ReEDS output CSV/HDF5 files into
        the standardized ModelOutput schema, extracting electricity price paths,
        generation dispatch by fuel type, and capacity utilization rates.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
