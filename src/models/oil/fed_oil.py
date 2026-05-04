"""Adapter for the Fed Workhorse Oil Model (Baumeister-Hamilton).

Reference:
    Baumeister, C., & Hamilton, J. D. — "Structural Interpretation of Vector
    Autoregressions with Incomplete Identification: Revisiting the Role of Oil
    Supply and Demand Shocks." American Economic Review, 109(5), 2019.
    The "Fed workhorse" designation reflects widespread adoption of this SVAR
    framework at the Federal Reserve for monetary policy analysis involving
    energy price shocks.

Real implementation requirements:
    - The Baumeister-Hamilton SVAR model codebase (MATLAB or R; available from
      the authors' websites or replication archives).
    - Baseline macroeconomic time series: US CPI, GDP, federal funds rate, oil
      prices, and industrial production (sourced from FRED or equivalent).
    - IRF (impulse response function) tables and FEVD (forecast error variance
      decomposition) output for the shock scenarios.
    - Output: GDP impulse response, CPI response, federal funds rate response,
      unemployment impulse response — all as quarterly paths over the forecast
      horizon.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.macro.macro_kernel import compute_macro_outcomes

# Allowed values for the shock_type parameter.
_VALID_SHOCK_TYPES: frozenset[str] = frozenset({
    "supply",       # Oil supply disruption (quantity-driven, e.g., Strait closure)
    "demand",       # Oil demand shock (global activity-driven)
    "speculative",  # Speculative / precautionary demand shock (inventory-driven)
})

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Shock-type multipliers applied on top of the macro_kernel baseline GDP /
# CPI elasticities. Calibrated against Baumeister & Hamilton (2019 AER
# Table 3) FEVD shares and Kilian (2009 AER) IRF magnitudes:
#   * supply shocks transmit to GDP almost in full and to CPI roughly 1:1
#   * demand shocks have weaker GDP / CPI pass-through (positive activity
#     largely offsets the price drag)
#   * speculative / precautionary shocks have smaller GDP impact and
#     intermediate CPI impact (inventory unwind is partially reversed)
_SHOCK_TYPE_GDP_MULTIPLIERS: dict[str, float] = {
    "supply": 1.2,
    "demand": 0.4,
    "speculative": 0.3,
}
_SHOCK_TYPE_CPI_MULTIPLIERS: dict[str, float] = {
    "supply": 1.0,
    "demand": 0.6,
    "speculative": 0.8,
}
# FEVD share of US GDP variance attributable to the oil shock, by type.
# Baumeister & Hamilton (2019) Table 3 reports comparable values.
_SHOCK_TYPE_FEVD: dict[str, float] = {
    "supply": 0.35,
    "demand": 0.20,
    "speculative": 0.15,
}

# Geometric IRF decay rates applied to the impulse-response paths.
# Standard Bayesian-VAR posterior means in the Baumeister-Hamilton
# replication: GDP responses decay rho ~ 0.85 per quarter, CPI ~ 0.75,
# FFR ~ 0.9 (Taylor-rule inertia).
_IRF_DECAY_GDP: float = 0.85
_IRF_DECAY_CPI: float = 0.75
_IRF_DECAY_FFR: float = 0.90

# Taylor-rule coefficient on inflation surprise. Conservative 0.5 to
# acknowledge ZLB / forward-guidance constraints; full Taylor (1993)
# coefficient is 1.5.
_TAYLOR_COEFF_INFLATION: float = 0.5
# Okun's-law coefficient on the GDP IRF (unemployment moves opposite GDP
# at roughly half the magnitude per quarter).
_OKUN_COEFF: float = -0.5

# Parameters required by this model. Each entry is (name, type_description).
_REQUIRED_PARAMS: list[tuple[str, str]] = [
    ("oil_price_change_pct", "float — percentage change in oil price at shock onset relative to pre-shock baseline (e.g., 50.0 = 50% increase)"),
    ("shock_type", "str — structural shock classification: 'supply', 'demand', or 'speculative'"),
    ("disruption_duration_quarters", "float — expected duration of the oil price shock in quarters"),
    ("fed_funds_rate_baseline", "float — pre-shock federal funds rate in percent (e.g., 4.5 for 4.5%)"),
]

_REQUIRED_PARAM_NAMES: set[str] = {name for name, _ in _REQUIRED_PARAMS}


class FedOilAdapter(ModelAdapter):
    """Adapter stub for the Fed Workhorse Oil Model (Baumeister-Hamilton SVAR).

    The Baumeister-Hamilton structural vector autoregression (SVAR) model is the
    standard Federal Reserve framework for analyzing the macroeconomic transmission
    of oil price shocks. It decomposes oil price movements into supply shocks, demand
    shocks, and speculative/precautionary shocks, and traces the impulse responses
    of key macroeconomic aggregates (GDP, CPI, interest rates, unemployment) to each
    shock type.

    This adapter operates at the SHORT_RUN_MACRO analytical level because it
    translates commodity-level oil price disruptions (from POLES-JRC and
    Bornstein-Krusell-Rebelo) into macroeconomic outcomes over a 2–8 quarter horizon.

    Outputs fed downstream:
        - GDP impulse response path (% deviation from baseline, quarterly)
        - CPI / inflation impulse response path (percentage points, quarterly)
        - Federal funds rate response path (percentage points, quarterly)
        - Unemployment rate response path (percentage points, quarterly)
        - Forecast error variance decomposition attributable to the oil shock
    """

    @property
    def model_id(self) -> str:
        return "fed_oil"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.SHORT_RUN_MACRO

    @property
    def description(self) -> str:
        return (
            "Fed Workhorse Oil Model (Baumeister-Hamilton SVAR) — structural vector "
            "autoregression for macroeconomic transmission of oil price shocks. "
            "Decomposes oil shocks into supply, demand, and speculative components and "
            "traces impulse responses of GDP, CPI, federal funds rate, and unemployment "
            "over a 2–8 quarter short-run horizon."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required parameters are present and within plausible bounds."""
        errors: list[str] = []
        warnings: list[str] = []

        # Check required parameters are present
        missing = _REQUIRED_PARAM_NAMES - set(params.keys())
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Bounds checks
        oil_change = params["oil_price_change_pct"]
        if not isinstance(oil_change, (int, float)):
            errors.append("'oil_price_change_pct' must be a numeric value")
        elif oil_change <= -100:
            errors.append(
                f"'oil_price_change_pct' value {oil_change}% implies a zero or negative oil "
                "price; this is not a valid input for the SVAR model"
            )
        elif oil_change > 300:
            warnings.append(
                f"'oil_price_change_pct' value {oil_change}% implies a more than 4x price "
                "increase; Baumeister-Hamilton impulse responses may be unreliable far "
                "outside the historical sample range used for estimation"
            )

        shock_type = params["shock_type"]
        if not isinstance(shock_type, str):
            errors.append("'shock_type' must be a string")
        elif shock_type not in _VALID_SHOCK_TYPES:
            errors.append(
                f"'shock_type' value '{shock_type}' is not recognized; "
                f"must be one of: {sorted(_VALID_SHOCK_TYPES)}"
            )

        duration = params["disruption_duration_quarters"]
        if not isinstance(duration, (int, float)):
            errors.append("'disruption_duration_quarters' must be a numeric value")
        elif duration <= 0:
            errors.append("'disruption_duration_quarters' must be positive")
        elif duration > 20:
            warnings.append(
                f"'disruption_duration_quarters' value {duration} exceeds 20 quarters (5 years); "
                "the Baumeister-Hamilton SVAR is estimated on quarterly data and its IRFs "
                "are not reliable at very long horizons — consider a long-run CGE model "
                "for structural shifts beyond 4–5 years"
            )

        ffr = params["fed_funds_rate_baseline"]
        if not isinstance(ffr, (int, float)):
            errors.append("'fed_funds_rate_baseline' must be a numeric value")
        elif ffr < 0:
            errors.append(
                f"'fed_funds_rate_baseline' value {ffr}% is negative; the zero lower bound "
                "constraint must be handled separately if rates are near zero"
            )
        elif ffr > 20:
            warnings.append(
                f"'fed_funds_rate_baseline' value {ffr}% is above 20%; this is outside the "
                "historical range used to estimate the Baumeister-Hamilton model and may "
                "produce unreliable impulse responses"
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through as-is.

        The real implementation would construct the oil price shock vector in the format
        expected by the SVAR model (a time-indexed price series in levels or log-differences),
        set the structural shock identification scheme corresponding to shock_type, and
        configure the baseline macroeconomic state vector from the fed_funds_rate_baseline
        and any other conditioning variables.
        """
        return dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the analytical-MVP Fed Workhorse Oil Model.

        Closed-form approximation of the Baumeister-Hamilton SVAR. The
        macro_kernel produces the headline GDP / CPI / consumption /
        welfare response to the oil price shock; this adapter then
        applies Baumeister-Hamilton shock-type multipliers
        (``_SHOCK_TYPE_GDP_MULTIPLIERS`` /
        ``_SHOCK_TYPE_CPI_MULTIPLIERS``) and constructs quarterly
        impulse-response paths (GDP, CPI, federal funds rate,
        unemployment) via geometric decay. The full SVAR replication
        requires MATLAB/R + FRED time series; this fallback gives the
        OIL short-run-macro tier a runnable model on the cluster MVP.

        The shock-type FEVD shares (``_SHOCK_TYPE_FEVD``) are returned
        as metadata so synthesis can show oil's contribution to GDP
        variance even without the full Bayesian posterior.
        """
        params = inputs if isinstance(inputs, dict) else dict(inputs)

        oil_change_pct = float(params["oil_price_change_pct"])
        shock_type = str(params["shock_type"])
        duration_quarters = float(params["disruption_duration_quarters"])
        ffr_baseline = float(params["fed_funds_rate_baseline"])
        duration_months = duration_quarters * 3.0

        # Headline macro response from the kernel (cumulative over window).
        kernel_out = compute_macro_outcomes(
            commodity_shocks={"oil": oil_change_pct},
            duration_months=duration_months,
            regime="short_run",
        )

        gdp_mult = _SHOCK_TYPE_GDP_MULTIPLIERS.get(shock_type, 1.0)
        cpi_mult = _SHOCK_TYPE_CPI_MULTIPLIERS.get(shock_type, 1.0)
        peak_gdp_pct = kernel_out["gdp_impact_pct"] * gdp_mult
        peak_cpi_pct = kernel_out["cpi_inflation_pct"] * cpi_mult

        # Quarterly IRFs. Horizon = max(8, duration + 4) so we always
        # carry several quarters past the disruption to show decay.
        horizon = max(8, int(round(duration_quarters)) + 4)
        gdp_irf: list[float] = []
        cpi_irf: list[float] = []
        ffr_irf: list[float] = []
        unemployment_irf: list[float] = []
        ffr_path: list[float] = []
        for q in range(horizon):
            gdp_q = peak_gdp_pct * (_IRF_DECAY_GDP ** q)
            cpi_q = peak_cpi_pct * (_IRF_DECAY_CPI ** q)
            # Taylor-rule FFR response with persistence rho = 0.9. The
            # geometric decay in `_IRF_DECAY_FFR` is the persistence;
            # the per-quarter forcing term is the Taylor coefficient
            # times the contemporaneous CPI deviation.
            if q == 0:
                ffr_q = _TAYLOR_COEFF_INFLATION * cpi_q
            else:
                ffr_q = _IRF_DECAY_FFR * ffr_irf[-1] + (
                    _TAYLOR_COEFF_INFLATION * (cpi_q - cpi_irf[-1])
                )
            unemp_q = _OKUN_COEFF * gdp_q
            gdp_irf.append(round(gdp_q, 4))
            cpi_irf.append(round(cpi_q, 4))
            ffr_irf.append(round(ffr_q, 4))
            unemployment_irf.append(round(unemp_q, 4))
            ffr_path.append(round(ffr_baseline + ffr_q, 4))

        peak_ffr_irf = max(ffr_irf, key=abs) if ffr_irf else 0.0
        peak_unemp_irf = max(unemployment_irf, key=abs) if unemployment_irf else 0.0

        # ZLB warning: if Taylor-implied FFR would go below zero we flag
        # it but still report the unconstrained path so analysts can see
        # the binding-constraint magnitude.
        zlb_binding = any(p < 0.0 for p in ffr_path)

        outputs: dict[str, Any] = {
            "shock_type": shock_type,
            "oil_price_change_pct": oil_change_pct,
            "disruption_duration_quarters": duration_quarters,
            "fed_funds_rate_baseline": ffr_baseline,
            "peak_gdp_impact_pct": round(peak_gdp_pct, 4),
            "peak_cpi_impact_pp": round(peak_cpi_pct, 4),
            "peak_ffr_impact_pp": round(peak_ffr_irf, 4),
            "peak_unemployment_impact_pp": round(peak_unemp_irf, 4),
            "gdp_irf_pct_quarterly": gdp_irf,
            "cpi_irf_pp_quarterly": cpi_irf,
            "fed_funds_rate_irf_pp_quarterly": ffr_irf,
            "fed_funds_rate_path_pct_quarterly": ffr_path,
            "unemployment_irf_pp_quarterly": unemployment_irf,
            "fevd_oil_share": _SHOCK_TYPE_FEVD.get(shock_type, 0.20),
            "zlb_binding": zlb_binding,
            "horizon_quarters": horizon,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "Baumeister & Hamilton (2019 AER) shock-type multipliers; "
                    "Kilian (2009 AER) oil-shock IRF magnitudes; Taylor (1993) "
                    "interest rule with conservative inflation coefficient 0.5; "
                    "Okun's-law unemployment coefficient -0.5."
                ),
                "shock_type_gdp_multipliers": dict(_SHOCK_TYPE_GDP_MULTIPLIERS),
                "shock_type_cpi_multipliers": dict(_SHOCK_TYPE_CPI_MULTIPLIERS),
                "shock_type_fevd": dict(_SHOCK_TYPE_FEVD),
                "irf_decay_gdp": _IRF_DECAY_GDP,
                "irf_decay_cpi": _IRF_DECAY_CPI,
                "irf_decay_ffr": _IRF_DECAY_FFR,
                "kernel_inputs": kernel_out.get("_inputs", {}),
                "note": (
                    "Analytical MVP path. Real Baumeister-Hamilton SVAR "
                    "integration would require: (1) the SVAR codebase from "
                    "the authors' replication archives (AER 2019), (2) "
                    "baseline FRED macro time series, (3) a MATLAB or R "
                    "execution environment, (4) IRF/FEVD output parsers."
                ),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through, wrapping in standardized ModelOutput.

        The real implementation would parse Baumeister-Hamilton SVAR output files into
        structured IRF arrays (one per endogenous variable, indexed by quarter), FEVD
        tables, and confidence bands (68% and 90% credible intervals from the Bayesian
        estimation procedure).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )
