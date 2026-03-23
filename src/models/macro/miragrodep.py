"""MIRAGRODEPAdapter — MIRAGRODEP multi-region CGE with agricultural-trade linkages.

MIRAGRODEP (Model of International Relations in Agriculture with a Global
Recursive-Dynamic framework for Economic Projections) is a multi-region
computable general equilibrium model with detailed agricultural sector
representation and global trade linkages. It is particularly well-suited to
the Hormuz pipeline because it explicitly models how fertilizer price shocks
transmit into agricultural production costs, food trade flows, and rural
household welfare across developing regions that depend on Persian Gulf
commodity exports.

MIRAGRODEP operates at the long-run macro/strategic analytical level, receiving
both energy sector shocks (oil price) and agricultural input shocks (fertilizer)
from commodity-level models and producing multi-region trade flow, food security,
and welfare estimates.

Real implementation requirements:
- MIRAGRODEP model code (available from IFPRI or Centre d'Etudes Prospectives
  et d'Informations Internationales, CEPII)
- GTAP database or MIRAGE-compatible SAM with agricultural detail
- GAMS installation and license (MIRAGRODEP is GAMS-based)
- Sector and region mapping from pipeline categories to MIRAGE aggregations
- Baseline simulation results for shock decomposition
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Parameters that must be present for MIRAGRODEP to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "fertilizer_price_shock_pct",
        "agricultural_trade_disruption_spec",
        "disruption_duration_months",
    }
)


class MIRAGRODEPAdapter(ModelAdapter):
    """Adapter for the MIRAGRODEP multi-region agricultural CGE model.

    MIRAGRODEP traces the transmission of energy and fertilizer price shocks
    through global agricultural supply chains to food trade flows, domestic
    production, and household welfare across developing regions. Its detailed
    agricultural sector representation—covering individual crops, livestock,
    and processed food products—makes it the primary model for assessing
    long-run food security implications of the Strait of Hormuz closure.
    """

    @property
    def model_id(self) -> str:
        return "miragrodep"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "MIRAGRODEP: multi-region recursive-dynamic CGE model with detailed "
            "agricultural sector representation and global trade linkages. Traces "
            "fertilizer and energy price shocks through agricultural supply chains "
            "to food trade flows, production, and household welfare across developing "
            "regions dependent on Persian Gulf commodity exports."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate MIRAGRODEP input parameters.

        Checks that all required parameters are present. Validates that
        oil_price_shock_pct and fertilizer_price_shock_pct are numeric and
        within plausible ranges, that agricultural_trade_disruption_spec is a
        non-empty dict, and that disruption_duration_months is a positive number.

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

        # Validate fertilizer_price_shock_pct
        fert_shock = params["fertilizer_price_shock_pct"]
        if not isinstance(fert_shock, (int, float)):
            errors.append(
                f"'fertilizer_price_shock_pct' must be numeric; got {type(fert_shock).__name__}"
            )
        elif fert_shock < -100.0:
            errors.append(
                f"'fertilizer_price_shock_pct' cannot be less than -100%; got {fert_shock}"
            )
        elif fert_shock > 500.0:
            warnings.append(
                f"'fertilizer_price_shock_pct' is {fert_shock}%, which implies more than "
                "a 5x price increase. Verify consistency with fertilizer model outputs."
            )

        # Cross-check: large fertilizer shock without large oil shock is unusual
        # (natural gas is the primary feedstock for nitrogen fertilizers)
        if (
            isinstance(oil_shock, (int, float))
            and isinstance(fert_shock, (int, float))
            and oil_shock < 10.0
            and fert_shock > 100.0
        ):
            warnings.append(
                f"'fertilizer_price_shock_pct' ({fert_shock}%) is large relative to "
                f"'oil_price_shock_pct' ({oil_shock}%). Fertilizer prices are strongly "
                "linked to natural gas prices; verify this combination is intentional."
            )

        # Validate agricultural_trade_disruption_spec
        trade_spec = params["agricultural_trade_disruption_spec"]
        if not isinstance(trade_spec, dict) or len(trade_spec) == 0:
            errors.append(
                "'agricultural_trade_disruption_spec' must be a non-empty dict describing "
                "the agricultural trade shock (e.g., {'affected_corridors': [...], "
                "'shipping_cost_multiplier': 1.3, 'affected_commodities': [...]})"
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

        The real implementation would serialize params into MIRAGRODEP GAMS
        shock files and scenario configuration scripts, overriding the baseline
        energy price, fertilizer cost, and shipping cost parameters in the
        MIRAGE model's shock data files.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the MIRAGRODEP model.

        Not yet implemented. The real implementation will:
        1. Write oil price, fertilizer price, and trade disruption shocks
           into MIRAGRODEP GAMS shock parameter files
        2. Invoke the MIRAGRODEP GAMS entry point via subprocess, passing
           the scenario configuration as a GAMS command-line argument
        3. Monitor GAMS solver output for convergence (MODEL STATUS and
           SOLVE STATUS codes)
        4. Parse MIRAGRODEP output GDX or CSV files for trade flows, sectoral
           output, food security indicators, and welfare changes by region
        5. Return structured ModelOutput for long-run strategic synthesis

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real MIRAGRODEP integration is built.
        """
        raise NotImplementedError(
            "MIRAGRODEPAdapter.execute() is not yet implemented. "
            "Real implementation requires: (1) the MIRAGRODEP model code (available from "
            "IFPRI or CEPII), (2) a GAMS installation and license (MIRAGRODEP is GAMS-based), "
            "(3) a GTAP database or MIRAGE-compatible SAM with agricultural sector detail, "
            "(4) sector and region mapping scripts translating pipeline commodity categories "
            "to MIRAGE aggregations, and (5) baseline simulation results for decomposition "
            "of scenario shocks relative to the no-disruption counterfactual."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw MIRAGRODEP output through without transformation.

        The real implementation would parse MIRAGRODEP GDX or CSV output files
        into the standardized ModelOutput schema, extracting bilateral trade
        flow changes, sectoral production adjustments, food security indicators
        (caloric availability by region), and household welfare changes (EV)
        by income group and region.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output unchanged (passthrough for stub).
        """
        return raw
