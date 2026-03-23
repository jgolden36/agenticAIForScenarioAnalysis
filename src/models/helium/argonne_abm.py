"""Adapter stub for the Argonne Helium Agent-Based Model (AnyLogic).

The Argonne Helium ABM is an agent-based model of contemporary helium
market dynamics developed at Argonne National Laboratory. It is implemented
in AnyLogic and simulates the behavior of individual market participants —
producers, liquefiers, distributors, and end-users — to capture emergent
market dynamics that equilibrium models may miss, including hoarding,
contract renegotiation, spot market volatility, and cascading shortfalls
across downstream industries.

Under Strait of Hormuz closure scenarios, the ABM complements the World
Helium Model by capturing dynamic market responses and distributional
effects across heterogeneous buyers (e.g., semiconductor fabs vs. MRI
facilities vs. aerospace contractors).
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult


class ArgonneABMAdapter(ModelAdapter):
    """Adapter stub for the Argonne Helium ABM (AnyLogic-based).

    Real implementation requirements:
    - AnyLogic runtime environment (AnyLogic Professional or the AnyLogic
      Cloud CLI export). AnyLogic models can be exported as standalone Java
      JAR files for headless CLI execution.
    - Licensed copy of the Argonne Helium ABM model file (.alp or exported
      JAR). Contact Argonne National Laboratory (Energy Systems Division)
      for access.
    - AnyLogic CLI invocation pattern:
        java -jar argonne_helium_abm.jar --param supply_shock_pct=<val> ...
      (exact parameter passing mechanism depends on the exported model's
      experiment configuration; verify with Argonne.)
    - Baseline agent population data: producer counts, capacity distributions,
      contract structures, and end-user demand profiles for the current market.
    - Java runtime (JRE 11+) on the execution host.
    """

    @property
    def model_id(self) -> str:
        return "argonne_abm"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.HELIUM_SEMICONDUCTORS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "Argonne Helium ABM (AnyLogic): agent-based model of contemporary helium "
            "market dynamics developed at Argonne National Laboratory. Simulates "
            "heterogeneous producer, distributor, and end-user agents to capture "
            "emergent market behavior — hoarding, spot price spikes, contract "
            "renegotiation, and cascading shortfalls — under supply disruption "
            "scenarios triggered by Strait of Hormuz closure."
        )

    # ------------------------------------------------------------------
    # Required parameters and their validation rules
    # ------------------------------------------------------------------

    REQUIRED_PARAMS: dict[str, str] = {
        "supply_shock_pct": (
            "Percentage reduction in global helium supply available to market "
            "agents at shock onset (0–100). Derived from qatar_helium_supply_loss_pct "
            "scaled by Qatar's share of global supply (~30%)."
        ),
        "disruption_duration_months": (
            "Duration of the supply shock in months. Drives the simulation "
            "time horizon over which agents adapt behavior."
        ),
        "demand_response_elasticity": (
            "Price elasticity of demand for helium in the short run (negative "
            "value, e.g., -0.15). Controls how aggressively end-user agents "
            "curtail consumption in response to price signals."
        ),
    }

    PARAM_BOUNDS: dict[str, tuple[float, float]] = {
        "supply_shock_pct": (0.0, 100.0),
        "disruption_duration_months": (0.0, 36.0),
        "demand_response_elasticity": (-2.0, 0.0),
    }

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate required parameters and check value ranges.

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult with errors for missing or out-of-range parameters
            and warnings for borderline values.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check for required parameters
        for param_name in self.REQUIRED_PARAMS:
            if param_name not in params:
                errors.append(
                    f"Missing required parameter '{param_name}': "
                    f"{self.REQUIRED_PARAMS[param_name]}"
                )

        # Validate bounds for parameters that are present
        for param_name, (low, high) in self.PARAM_BOUNDS.items():
            if param_name not in params:
                continue  # already caught above
            value = params[param_name]
            try:
                fval = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"Parameter '{param_name}' must be numeric; got {value!r}."
                )
                continue
            if not (low <= fval <= high):
                errors.append(
                    f"Parameter '{param_name}' = {fval} is outside the valid "
                    f"range [{low}, {high}]."
                )

        # Scenario-specific sanity warnings
        if "supply_shock_pct" in params:
            try:
                pct = float(params["supply_shock_pct"])
                if pct > 30.0:
                    warnings.append(
                        f"supply_shock_pct = {pct}% exceeds Qatar's approximate share "
                        "of global helium supply (~30%). Confirm whether additional "
                        "supply disruptions (e.g., Russian or Algerian sources) are "
                        "included in this figure."
                    )
            except (TypeError, ValueError):
                pass

        if "demand_response_elasticity" in params:
            try:
                elast = float(params["demand_response_elasticity"])
                if elast == 0.0:
                    warnings.append(
                        "demand_response_elasticity = 0.0 implies perfectly inelastic "
                        "demand. This may be appropriate for critical uses (MRI, "
                        "semiconductor lithography) but should be confirmed as the "
                        "intended market-wide assumption."
                    )
                elif elast < -1.0:
                    warnings.append(
                        f"demand_response_elasticity = {elast} implies elastic demand. "
                        "Helium demand is typically inelastic in the short run due to "
                        "lack of substitutes in critical applications. Verify this value."
                    )
            except (TypeError, ValueError):
                pass

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through unchanged.

        The real implementation will serialize these to AnyLogic CLI arguments
        or an experiment configuration file compatible with the exported JAR.

        Example target format (subject to confirmation with Argonne):
            {
                "supply_shock_pct": 28.5,
                "disruption_duration_months": 4.0,
                "demand_response_elasticity": -0.15,
                "random_seed": 42,
                "num_replications": 50
            }

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary, passed through unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Argonne Helium ABM via the AnyLogic CLI.

        Not yet implemented. Requires AnyLogic runtime and access to the
        Argonne Helium ABM exported JAR or model file.

        Real implementation steps:
        1. Serialize inputs to AnyLogic experiment parameters (CLI flags or
           JSON config, depending on the exported model's interface).
        2. Invoke the JAR via subprocess:
               java -jar argonne_helium_abm.jar [params]
        3. Collect stdout/stderr; parse AnyLogic's simulation output (CSV
           or database export, depending on model configuration).
        4. Aggregate across replications (ABMs are stochastic; run N
           replications and summarize the distribution of outcomes).
        5. Pass aggregated output to parse_outputs.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Until the AnyLogic model is integrated.
        """
        raise NotImplementedError(
            "ArgonneABMAdapter.execute is a stub. Real implementation requires: "
            "(1) AnyLogic Professional runtime or exported JAR of the Argonne Helium "
            "ABM (contact Argonne National Laboratory, Energy Systems Division, for "
            "access); (2) Java runtime (JRE 11+) on the execution host; (3) "
            "documentation of the AnyLogic CLI parameter-passing interface for this "
            "specific model export; (4) baseline agent population calibration data "
            "(producer capacities, contract structures, end-user demand profiles). "
            "Note: AnyLogic ABMs are stochastic — plan for multiple replications "
            "and statistical aggregation of outputs."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through unchanged.

        The real implementation will parse AnyLogic's output (CSV time-series
        or database export) and extract: spot price trajectory, allocation
        by end-user category, inventory levels across distribution chain,
        number of agent stockout events, and demand rationing volume by sector.
        Stochastic outputs should be summarized as mean ± std across replications.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output, passed through as-is in this stub.
        """
        return raw
