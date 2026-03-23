"""Adapter stub for SimRLFab — RL simulation of semiconductor fabrication disruption.

SimRLFab is a reinforcement-learning-based simulation model of semiconductor
fabrication operations. It models fab-level responses to input material
shortfalls — including helium and neon, both of which are critical process
gases in lithography and wafer cleaning — and quantifies the resulting
impact on wafer output, yield, and fab utilization.

Helium is used in semiconductor manufacturing for heat transfer in ion
implantation stages and as a carrier gas in lithography systems. Neon is
used in excimer laser gas mixtures (KrF and ArF lithography). Both gases
are implicated in a Strait of Hormuz closure: Qatar supplies ~30% of global
helium, and Ukraine (the dominant neon supplier, with ~70% of global neon
supply pre-2022) presents separate but often co-analyzed supply risk.

SimRLFab captures fab scheduling decisions under scarcity using a
reinforcement learning agent trained on historical fab operational data,
allowing it to estimate adaptive responses that simpler linear models cannot
represent: gas conservation protocols, process re-sequencing, and selective
curtailment of lower-margin product lines.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

_NEON_STATUS_VALID_VALUES = {"normal", "constrained", "severely_disrupted"}


class SimRLFabAdapter(ModelAdapter):
    """Adapter stub for SimRLFab RL simulation of semiconductor fabrication.

    Real implementation requirements:
    - Access to the SimRLFab model codebase and its trained RL policy
      weights. The model is an academic research artifact; contact the
      original authors for access to the simulation environment and
      pre-trained agents.
    - Baseline fab utilization and process gas consumption data calibrated
      to the current global semiconductor manufacturing landscape (TSMC,
      Samsung, Intel, GlobalFoundries, and SMIC node mix).
    - Python environment with the SimRLFab dependencies installed
      (expected to include PyTorch or JAX for the RL policy network;
      exact requirements depend on the codebase version).
    - Execution interface: likely a Python subprocess call or direct
      import, depending on the packaging of the SimRLFab codebase.
    - Output: fab utilization trajectory, wafer output loss, yield
      degradation estimates, and estimated production shortfall by
      chip node (logic vs. memory, advanced vs. mature nodes).
    """

    @property
    def model_id(self) -> str:
        return "simrlfab"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.HELIUM_SEMICONDUCTORS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "SimRLFab: reinforcement-learning simulation of semiconductor fabrication "
            "disruption. Models fab-level adaptive responses to helium and neon supply "
            "shortfalls — including gas conservation protocols, process re-sequencing, "
            "and selective curtailment — to estimate wafer output loss, yield "
            "degradation, and utilization impacts under Strait of Hormuz closure "
            "scenarios."
        )

    # ------------------------------------------------------------------
    # Required parameters and their validation rules
    # ------------------------------------------------------------------

    REQUIRED_PARAMS: dict[str, str] = {
        "helium_supply_reduction_pct": (
            "Percentage reduction in helium available to semiconductor fabs "
            "(0–100). Derived from the global helium supply loss, weighted by "
            "the semiconductor sector's share of total helium consumption "
            "(approximately 28% of end-use demand)."
        ),
        "neon_supply_status": (
            "Categorical indicator of neon supply conditions: one of "
            "'normal', 'constrained', or 'severely_disrupted'. Neon is not "
            "directly disrupted by Strait closure but represents a correlated "
            "process gas risk. Use 'normal' if no concurrent neon disruption "
            "is assumed."
        ),
        "disruption_duration_months": (
            "Duration of the helium supply disruption in months. The RL "
            "agent's learned policy covers disruptions up to 24 months; "
            "longer horizons should be flagged as extrapolation."
        ),
        "fab_utilization_baseline": (
            "Baseline fab utilization rate at disruption onset (0.0–1.0, "
            "where 1.0 = 100% utilization). Affects inventory buffer size "
            "and the fab's ability to absorb short-term supply shocks before "
            "curtailing production."
        ),
    }

    PARAM_BOUNDS: dict[str, tuple[float, float]] = {
        "helium_supply_reduction_pct": (0.0, 100.0),
        "disruption_duration_months": (0.0, 36.0),
        "fab_utilization_baseline": (0.0, 1.0),
    }

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate required parameters and check value ranges and categorical values.

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult with errors for missing, out-of-range, or invalid
            categorical parameters and warnings for borderline values.
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

        # Validate numeric bounds for parameters that are present
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

        # Validate categorical parameter: neon_supply_status
        if "neon_supply_status" in params:
            neon_val = params["neon_supply_status"]
            if neon_val not in _NEON_STATUS_VALID_VALUES:
                errors.append(
                    f"Parameter 'neon_supply_status' = {neon_val!r} is not a recognized "
                    f"value. Must be one of: {sorted(_NEON_STATUS_VALID_VALUES)}."
                )

        # Scenario-specific sanity warnings
        if "helium_supply_reduction_pct" in params:
            try:
                pct = float(params["helium_supply_reduction_pct"])
                if pct > 28.0:
                    warnings.append(
                        f"helium_supply_reduction_pct = {pct}% applied to fab inputs. "
                        "Note that semiconductors consume ~28% of global helium; a "
                        "market-wide supply reduction does not translate one-for-one "
                        "to fab-level availability if rationing prioritizes critical "
                        "uses. Confirm whether this value is already fab-sector-specific "
                        "or reflects the aggregate market reduction."
                    )
            except (TypeError, ValueError):
                pass

        if "disruption_duration_months" in params:
            try:
                duration = float(params["disruption_duration_months"])
                if duration > 24.0:
                    warnings.append(
                        f"disruption_duration_months = {duration} exceeds the 24-month "
                        "horizon over which the SimRLFab RL policy is trained. Outputs "
                        "beyond this horizon are extrapolations and should be interpreted "
                        "with caution."
                    )
            except (TypeError, ValueError):
                pass

        if "neon_supply_status" in params and "helium_supply_reduction_pct" in params:
            neon_val = params["neon_supply_status"]
            try:
                he_pct = float(params["helium_supply_reduction_pct"])
                if neon_val == "severely_disrupted" and he_pct > 20.0:
                    warnings.append(
                        "Both helium (>{:.0f}% reduction) and neon ('severely_disrupted') "
                        "are simultaneously constrained. This compound-shortage scenario "
                        "may push fab operations outside the range of the RL agent's "
                        "training distribution. Flag outputs for analyst review.".format(he_pct)
                    )
            except (TypeError, ValueError):
                pass

        if "fab_utilization_baseline" in params:
            try:
                util = float(params["fab_utilization_baseline"])
                if util < 0.7:
                    warnings.append(
                        f"fab_utilization_baseline = {util:.2f} indicates fabs operating "
                        "below 70% capacity at disruption onset. Lower baseline utilization "
                        "increases the gas inventory buffer and may cause SimRLFab to "
                        "underestimate disruption severity relative to a high-utilization "
                        "baseline."
                    )
            except (TypeError, ValueError):
                pass

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Pass parameters through unchanged.

        The real implementation will serialize these into the SimRLFab
        simulation environment's configuration format. Based on typical
        RL simulation codebases, this is expected to be a Python dict
        passed directly to the environment's reset() or configure() method,
        or serialized to a JSON config file consumed at subprocess launch.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The parameter dictionary, passed through unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the SimRLFab RL simulation.

        Not yet implemented. Requires access to the SimRLFab codebase,
        trained RL policy weights, and a compatible Python environment.

        Real implementation steps:
        1. Initialize the SimRLFab simulation environment with the
           disruption parameters (helium reduction, neon status, duration,
           baseline utilization).
        2. Load the pre-trained RL policy weights for the fab agent.
        3. Roll out the simulation over the specified disruption duration,
           recording fab utilization, wafer output, and gas consumption
           at each time step.
        4. If the model supports multiple rollouts (stochastic policy or
           stochastic environment dynamics), aggregate across replications.
        5. Pass the collected time-series output to parse_outputs.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Until the SimRLFab codebase is integrated.
        """
        raise NotImplementedError(
            "SimRLFabAdapter.execute is a stub. Real implementation requires: "
            "(1) access to the SimRLFab model codebase and pre-trained RL policy "
            "weights (contact the SimRLFab authors for the research codebase); "
            "(2) a Python environment with SimRLFab's dependencies installed "
            "(expected to include PyTorch or JAX, plus a fab simulation environment "
            "package); (3) baseline calibration data for the global semiconductor "
            "fab landscape (node mix, utilization rates, process gas consumption "
            "per wafer start by node); (4) a validated mapping from market-level "
            "helium supply reduction to fab-level input availability, accounting "
            "for rationing and contract priorities."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw model output through unchanged.

        The real implementation will parse SimRLFab's time-series output
        into the standardized ModelOutput schema, extracting: fab utilization
        trajectory over the disruption period, cumulative wafer output loss
        (wafer starts and wafer outs), yield degradation by process node,
        estimated chip production shortfall by category (logic/memory,
        advanced/mature node), and gas consumption trajectory showing
        the RL agent's conservation policy in action.

        Args:
            raw: Raw output from execute.

        Returns:
            The raw output, passed through as-is in this stub.
        """
        return raw
