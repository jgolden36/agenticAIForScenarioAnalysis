"""GTAP model adapter.

GTAP (Global Trade Analysis Project) is a multi-region, multi-sector computable
general equilibrium model of global trade. It is the standard framework for
analyzing how trade policy changes, supply shocks, and market disruptions
propagate through the global economy via trade linkages. Under Strait of Hormuz
closure scenarios, GTAP captures the long-run structural reallocation of
agricultural and commodity trade flows, welfare impacts by country, and changes
in production patterns as markets adapt to sustained disruption.

Real integration requirements:
    - GTAP model software (RunGTAP or FlexGTAP, typically Fortran-based)
    - GTAP database (version 10 or later, licensed from the GTAP Center at Purdue)
    - GAMS or GTAPAgg for data aggregation and shock parameterization
    - Access to the GTAP model repository and regional/sectoral aggregation schemes
    - Shock files specifying oil price, fertilizer price, and trade route disruptions
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_REQUIRED_PARAMS = [
    "oil_price_shock_pct",
    "fertilizer_price_shock_pct",
    "trade_route_disruption_spec",
    "disruption_duration_months",
]


class GTAPAdapter(ModelAdapter):
    """Adapter for the GTAP global trade CGE model.

    GTAP solves for general equilibrium prices, quantities, and trade flows
    across all globally traded goods and services, with detailed regional
    disaggregation. Under Strait of Hormuz closure scenarios, it captures
    long-run structural effects: how oil and fertilizer price shocks combined
    with trade route disruptions shift comparative advantage, alter agricultural
    and commodity trade patterns, and affect welfare across importing and
    exporting regions. GTAP operates at the LONG_RUN_MACRO_STRATEGIC level
    because its results reflect structural market adjustments rather than
    short-run disequilibrium dynamics.

    Outputs fed downstream:
        - Welfare changes by region (equivalent variation, $bn)
        - Changes in bilateral trade flows by commodity and region pair
        - Producer and consumer price changes by sector and region
        - GDP impacts by region
        - Terms-of-trade effects
    """

    @property
    def model_id(self) -> str:
        return "gtap"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "GTAP (Global Trade Analysis Project): multi-region, multi-sector CGE model "
            "of global trade capturing long-run structural reallocation of agricultural and "
            "commodity trade flows, welfare impacts, and production pattern shifts under "
            "sustained oil price, fertilizer price, and trade route disruptions."
        )

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that all required GTAP parameters are present and in range.

        Args:
            params: Parameter dictionary from the extraction module.

        Returns:
            ValidationResult with errors for missing or out-of-range values.
        """
        errors: list[str] = []
        warnings: list[str] = []

        for key in _REQUIRED_PARAMS:
            if key not in params:
                errors.append(f"Missing required parameter: '{key}'")

        if "oil_price_shock_pct" in params:
            val = params["oil_price_shock_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'oil_price_shock_pct' must be numeric")
            elif val > 500:
                warnings.append(
                    f"'oil_price_shock_pct' = {val}% is extreme; "
                    "verify this is consistent with commodity-level model outputs"
                )

        if "fertilizer_price_shock_pct" in params:
            val = params["fertilizer_price_shock_pct"]
            if not isinstance(val, (int, float)):
                errors.append("'fertilizer_price_shock_pct' must be numeric")
            elif val < 0:
                errors.append("'fertilizer_price_shock_pct' must be >= 0")
            elif val > 500:
                warnings.append(
                    f"'fertilizer_price_shock_pct' = {val}% is unusually large; "
                    "verify consistency with World Fertilizer Model output"
                )

        if "trade_route_disruption_spec" in params:
            val = params["trade_route_disruption_spec"]
            if not isinstance(val, (str, dict)):
                errors.append(
                    "'trade_route_disruption_spec' must be a string description or "
                    "a dict mapping bilateral trade pairs to disruption fractions"
                )

        if "disruption_duration_months" in params:
            val = params["disruption_duration_months"]
            if not isinstance(val, (int, float)):
                errors.append("'disruption_duration_months' must be numeric")
            elif val <= 0:
                errors.append("'disruption_duration_months' must be > 0")
            elif val > 36:
                warnings.append(
                    f"'disruption_duration_months' = {val} exceeds 36 months; "
                    "GTAP static equilibrium results do not capture dynamic adjustment paths "
                    "at this horizon — consider supplementing with recursive-dynamic GTAP"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through; real implementation writes GTAP shock files.

        The real implementation would construct a GTAP shock file specifying
        percentage changes to endowment prices (oil), intermediate input costs
        (fertilizer), and trade cost augmenting technical change parameters for
        Hormuz-routed bilateral flows, then invoke RunGTAP or FlexGTAP.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary unchanged (passthrough for stub).
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute GTAP — not yet implemented.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: GTAP integration is pending. Real implementation
                must write GTAP shock and closure files, invoke RunGTAP or
                FlexGTAP via subprocess, and parse the resulting solution file
                (SOL or HAR format) for welfare, trade, and price results.
        """
        raise NotImplementedError(
            "GTAPAdapter.execute is not yet implemented. "
            "Real integration requires: (1) a licensed GTAP database (version 10+, "
            "from the GTAP Center at Purdue University), (2) a GTAP model software "
            "installation (RunGTAP or FlexGTAP), (3) writing shock and closure files "
            "specifying oil price, fertilizer cost, and trade-route disruption shocks, "
            "(4) invoking the GTAP executable via subprocess, and (5) parsing the HAR/SOL "
            "solution file for welfare (EV by region), bilateral trade flows, and "
            "producer/consumer price changes by sector."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through; real implementation parses GTAP solution files.

        The real implementation would read the GTAP HAR or SOL output file,
        extract welfare changes (equivalent variation) by region, bilateral trade
        flow changes by commodity, and sectoral price results, then map GTAP
        region and sector codes to pipeline identifiers.

        Args:
            raw: Raw output from execute (passthrough for stub).

        Returns:
            The raw value wrapped in a ModelOutput (passthrough for stub).
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
