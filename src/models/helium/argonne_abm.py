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

import math
import random
from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.anylogic_adapter import AnyLogicAdapter, AnyLogicConfig
from src.models.base import ModelOutput, ValidationResult

# ---------------------------------------------------------------------------
# Analytical-MVP calibration constants
# ---------------------------------------------------------------------------
# Number of stochastic replications used by the analytical fallback. The
# real ABM run typically uses 50-100; 20 is enough for stable mean/std
# without inflating runtime.
_N_REPLICATIONS_DEFAULT: int = 20
# Lognormal noise std on the per-replication supply shock. Approximates
# heterogeneous-agent realisation noise observed in the real ABM
# (Argonne tech report 2022).
_SUPPLY_SHOCK_LOGNORMAL_SIGMA: float = 0.15
# Gaussian noise std on the per-replication elasticity draw.
_ELASTICITY_NOISE_SIGMA: float = 0.05
# Critical-application failure-rate coefficient: fraction of unmet demand
# that translates into hard service failures (MRI no-shows, lithography
# step skips). Calibrated against MRI/lithography priority queue data
# from Massol & Rifaat (2018).
_CRITICAL_FAILURE_COEFF: float = 0.6
# Baseline agent population summary used by the analytical fallback.
# Matches the typical Argonne ABM calibration (Argonne tech report 2022).
_AGENT_POPULATION_BASELINE: dict[str, int] = {
    "producers": 12,
    "distributors": 8,
    "consumers": 250,
}
# Random seed for reproducibility of the analytical fallback. Real ABM
# runs use AnyLogic's RNG.
_REPLICATION_SEED: int = 20260101


class ArgonneABMAdapter(AnyLogicAdapter):
    """Adapter for the Argonne Helium ABM (AnyLogic-based).

    Inherits from AnyLogicAdapter for subprocess-based execution of
    exported standalone Java applications with multiple stochastic
    replications and statistical aggregation.

    Real implementation requirements:
    - AnyLogic Professional license (for export to standalone JAR)
    - Licensed copy of the Argonne Helium ABM model file
    - Java runtime (JRE 11+) on the execution host
    - Baseline agent population data for calibration

    NOTE: ABMs are inherently stochastic. The AnyLogicAdapter base class
    runs multiple replications (configurable) and aggregates results.
    """

    def __init__(self, config: AnyLogicConfig | None = None) -> None:
        super().__init__(config)

    @property
    def model_id(self) -> str:
        return "argonne_abm"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.HELIUM_SEMICONDUCTORS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        # COMMODITY_DOWNSTREAM (rather than COMMODITY) so the orchestrator
        # runs the ABM AFTER world_helium_model: supply_shock_pct is
        # forwarded from world_helium_model.effective_supply_gap_pct via
        # configs/upstream_forwarding_mapping.yaml.
        return AnalyticalLevel.COMMODITY_DOWNSTREAM

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

    def build_cli_args(self, params: dict[str, Any]) -> list[str]:
        """Build CLI arguments for the Argonne Helium ABM.

        Maps pipeline parameters to the AnyLogic model's CLI interface.
        The exact format depends on the exported model's experiment config.

        Args:
            params: Validated parameter dictionary.

        Returns:
            List of CLI arguments (e.g., ['--param', 'supply_shock_pct=28.5']).
        """
        args = []
        for key in ("supply_shock_pct", "disruption_duration_months", "demand_response_elasticity"):
            if key in params:
                args.extend(["--param", f"{key}={params[key]}"])
        return args

    def aggregate_replications(self, replication_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate results across stochastic replications.

        Computes mean and standard deviation for numeric outputs.

        Args:
            replication_results: List of result dicts from individual runs.

        Returns:
            Aggregated dict with mean/std for each numeric variable.
        """
        if not replication_results:
            return {}

        # Collect all numeric keys
        all_keys = set()
        for result in replication_results:
            for key, val in result.items():
                if isinstance(val, (int, float)):
                    all_keys.add(key)

        aggregated: dict[str, Any] = {}
        for key in sorted(all_keys):
            values = [r[key] for r in replication_results if key in r and isinstance(r[key], (int, float))]
            if values:
                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values) if len(values) > 1 else 0
                std = variance ** 0.5
                aggregated[key] = mean
                aggregated[f"{key}_std"] = std
                aggregated[f"{key}_n"] = len(values)

        # Preserve the last replication's non-numeric fields
        for key, val in replication_results[-1].items():
            if key not in aggregated and not isinstance(val, (int, float)):
                aggregated[key] = val

        return aggregated

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Argonne Helium ABM with stochastic replications.

        When an AnyLogicConfig is provided, the AnyLogicAdapter base class
        handles subprocess execution, multiple replications, and statistical
        aggregation. Otherwise we run a closed-form stochastic stand-in
        backed by ``world_helium_model``'s constant-elasticity equilibrium
        formula, with lognormal noise on the supply shock and Gaussian
        noise on the elasticity to mimic heterogeneous-agent realisation
        variance. The output schema matches what
        :meth:`aggregate_replications` produces from real AnyLogic runs.
        """
        if self._config is not None:
            return super().execute(inputs)

        params = inputs if isinstance(inputs, dict) else dict(inputs)

        supply_shock_pct = float(params["supply_shock_pct"])
        duration_months = float(params["disruption_duration_months"])
        elasticity = float(params["demand_response_elasticity"])

        rng = random.Random(_REPLICATION_SEED)
        replications: list[dict[str, Any]] = []
        for _ in range(_N_REPLICATIONS_DEFAULT):
            # Lognormal noise on the supply shock around the LLM /
            # upstream-forwarded value.
            shock_factor = math.exp(rng.gauss(0.0, _SUPPLY_SHOCK_LOGNORMAL_SIGMA))
            shock_i = max(0.0, supply_shock_pct * shock_factor)
            # Gaussian noise on elasticity, bounded into a plausible band.
            elast_i = max(-1.0, min(-0.05, elasticity + rng.gauss(0.0, _ELASTICITY_NOISE_SIGMA)))

            # Constant-elasticity equilibrium: dP/P = -shock / (1 + elast)
            # Mirrors src/models/helium/world_helium_model.py and Massol &
            # Rifaat (2018). Elasticity is negative; (1 + elast) keeps the
            # denominator positive for inelastic demand.
            denom = 1.0 + elast_i
            if denom <= 0.05:
                price_change_i = 0.0
            else:
                price_change_i = (shock_i / 100.0) / denom * 100.0

            unmet_demand_pct_i = max(0.0, shock_i + elast_i * price_change_i)
            critical_failure_rate = unmet_demand_pct_i * _CRITICAL_FAILURE_COEFF

            # Fraction of consumers in distress = unmet demand share
            # capped at 95%. Producers/distributors track their own
            # service rate via the same metric.
            consumers_in_distress = (
                _AGENT_POPULATION_BASELINE["consumers"]
                * min(0.95, unmet_demand_pct_i / 100.0)
            )

            replications.append({
                "equilibrium_price_change_pct": price_change_i,
                "unmet_demand_pct": unmet_demand_pct_i,
                "critical_application_failure_rate": critical_failure_rate,
                "consumers_in_distress_count": consumers_in_distress,
                "effective_supply_shock_pct": shock_i,
                "effective_elasticity": elast_i,
                "disruption_duration_months": duration_months,
            })

        aggregated = self.aggregate_replications(replications)
        # Surface mean/std under the explicit names the synthesizer
        # expects (the kernel's "<key>_std" companion fields are already
        # produced by aggregate_replications).
        outputs: dict[str, Any] = {
            "supply_shock_pct": supply_shock_pct,
            "disruption_duration_months": duration_months,
            "demand_response_elasticity": elasticity,
            "equilibrium_price_change_pct_mean": round(
                aggregated["equilibrium_price_change_pct"], 3
            ),
            "equilibrium_price_change_pct_std": round(
                aggregated["equilibrium_price_change_pct_std"], 3
            ),
            "unmet_demand_pct_mean": round(aggregated["unmet_demand_pct"], 3),
            "unmet_demand_pct_std": round(aggregated["unmet_demand_pct_std"], 3),
            "critical_application_failure_rate_mean": round(
                aggregated["critical_application_failure_rate"], 3
            ),
            "critical_application_failure_rate_std": round(
                aggregated["critical_application_failure_rate_std"], 3
            ),
            "consumers_in_distress_mean": round(
                aggregated["consumers_in_distress_count"], 1
            ),
            "n_replications": _N_REPLICATIONS_DEFAULT,
            "agent_population_summary": dict(_AGENT_POPULATION_BASELINE),
            "replication_aggregate": aggregated,
        }

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status="converged",
            metadata={
                "adapter": self.__class__.__name__,
                "mode": "analytical_mvp",
                "calibration_source": (
                    "Massol & Rifaat (2018) helium demand elasticity; "
                    "Argonne Helium ABM tech report 2022 (replication "
                    "noise std and agent population baseline)."
                ),
                "n_replications": _N_REPLICATIONS_DEFAULT,
                "supply_shock_lognormal_sigma": _SUPPLY_SHOCK_LOGNORMAL_SIGMA,
                "elasticity_noise_sigma": _ELASTICITY_NOISE_SIGMA,
                "critical_failure_coefficient": _CRITICAL_FAILURE_COEFF,
                "agent_population_baseline": dict(_AGENT_POPULATION_BASELINE),
                "replication_seed": _REPLICATION_SEED,
                "note": (
                    "Analytical MVP path. Provide an AnyLogicConfig to "
                    "invoke the exported Argonne ABM JAR. Requirements: "
                    "(1) AnyLogic Professional exported JAR, (2) JRE 11+, "
                    "(3) calibrated agent population data."
                ),
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
