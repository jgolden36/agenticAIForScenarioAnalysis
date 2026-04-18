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

# Allowed values for the shock_type parameter.
_VALID_SHOCK_TYPES: frozenset[str] = frozenset({
    "supply",       # Oil supply disruption (quantity-driven, e.g., Strait closure)
    "demand",       # Oil demand shock (global activity-driven)
    "speculative",  # Speculative / precautionary demand shock (inventory-driven)
})

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
        """Execute the Fed Workhorse Oil Model (Baumeister-Hamilton SVAR).

        Not yet implemented. The real implementation requires:
            1. Constructing the oil price shock vector (levels or log-differences) from
               oil_price_change_pct and disruption_duration_quarters.
            2. Setting the structural shock identification scheme (sign restrictions or
               Cholesky decomposition) appropriate to the specified shock_type.
            3. Invoking the Baumeister-Hamilton SVAR codebase (MATLAB or R) via subprocess
               or language bridge, passing the shock vector and baseline state.
            4. Extracting impulse response functions (IRFs) for GDP, CPI, federal funds
               rate, and unemployment from the model output.
            5. Extracting forecast error variance decompositions (FEVDs) attributable to
               the oil shock component.
            6. Handling zero-lower-bound episodes if fed_funds_rate_baseline is near zero.

        Raises:
            NotImplementedError: Always, until the Baumeister-Hamilton model is integrated.
        """
        raise NotImplementedError(
            "FedOilAdapter.execute() is not yet implemented. "
            "Integration requires: (1) the Baumeister-Hamilton SVAR model codebase "
            "(available from the authors' replication archives for AER 2019), (2) baseline "
            "macroeconomic time series from FRED (US CPI, GDP, federal funds rate, oil "
            "prices, industrial production), (3) a MATLAB or R execution environment with "
            "the required econometric packages, and (4) output parsers for IRF and FEVD "
            "tables covering GDP, CPI, federal funds rate, and unemployment responses."
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
