"""Adapter stub for WEAP-MENA (Water Evaluation And Planning — MENA configuration).

WEAP-MENA is the Persian Gulf regional configuration of the Water Evaluation And
Planning system. It performs integrated water resource planning simulations that
account for supply infrastructure, demand sites, and allocation priorities. In the
Hormuz pipeline it quantifies the consequences of desalination facility disruption
for human water security across Gulf Cooperation Council states.

Real integration requirements:
- A licensed WEAP installation (Stockholm Environment Institute) accessible on the
  execution host, typically via the WEAP COM automation interface on Windows.
- A pre-configured WEAP-MENA study area file (.weap) covering the Persian Gulf
  region with current-year baseline data.
- Python win32com or a Windows subprocess call to drive WEAP headlessly:
      weap.exe /scenario <name> /run /quit
- Scenario branch creation within the WEAP study to represent each crisis scenario,
  parameterised by desalination capacity loss and disruption duration.
- Post-run extraction of WEAP result variables (e.g., Unmet Demand, Coverage) via
  the WEAP API or by parsing exported CSV/Excel result files.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Required parameter names, sourced from WATER_MODEL_SPECS["weap_mena"].
_REQUIRED_PARAMS: list[str] = [
    "desalination_capacity_loss_pct",
    "disruption_duration_weeks",
    "affected_countries",
    "alternative_supply_available",
    "population_affected_millions",
]

# Plausibility bounds for numeric parameters.
_BOUNDS: dict[str, tuple[float, float]] = {
    "desalination_capacity_loss_pct": (0.0, 100.0),
    "disruption_duration_weeks": (0.0, 260.0),   # up to 5 years
    "population_affected_millions": (0.0, 500.0),
}


class WEAPAdapter(ModelAdapter):
    """Adapter stub for the WEAP-MENA integrated water resource planning model."""

    # ------------------------------------------------------------------
    # Identity properties
    # ------------------------------------------------------------------

    @property
    def model_id(self) -> str:
        return "weap_mena"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "WEAP-MENA: Integrated water resource planning simulation for the Persian "
            "Gulf region. Quantifies unmet demand and coverage shortfalls resulting "
            "from desalination facility disruption under Strait of Hormuz closure "
            "scenarios."
        )

    # ------------------------------------------------------------------
    # Pipeline interface
    # ------------------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Check that all required parameters are present and within plausible ranges.

        Args:
            params: Parameter dictionary from the extraction module.

        Returns:
            ValidationResult describing any errors or warnings found.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Presence check
        for name in _REQUIRED_PARAMS:
            if name not in params:
                errors.append(f"Missing required parameter: '{name}'")

        # Plausibility / type checks for parameters that are present
        for param_name, (lo, hi) in _BOUNDS.items():
            if param_name not in params:
                continue  # already flagged above if required
            value = params[param_name]
            try:
                fval = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"Parameter '{param_name}' must be numeric; got {value!r}"
                )
                continue
            if not (lo <= fval <= hi):
                warnings.append(
                    f"Parameter '{param_name}' value {fval} is outside expected "
                    f"range [{lo}, {hi}]; verify before running."
                )

        # Type check: affected_countries must be a non-empty list
        if "affected_countries" in params:
            val = params["affected_countries"]
            if not isinstance(val, list):
                errors.append(
                    f"Parameter 'affected_countries' must be a list; got {type(val).__name__}"
                )
            elif len(val) == 0:
                warnings.append(
                    "Parameter 'affected_countries' is an empty list; "
                    "model results will cover no countries."
                )

        # Type check: alternative_supply_available must be boolean
        if "alternative_supply_available" in params:
            val = params["alternative_supply_available"]
            if not isinstance(val, bool):
                errors.append(
                    f"Parameter 'alternative_supply_available' must be a boolean; "
                    f"got {type(val).__name__}"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through unchanged.

        WEAP is driven via its COM API; input translation (creating scenario branches
        and setting assumption values) is the responsibility of the real execute()
        implementation.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same dictionary, unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute WEAP-MENA. Raises NotImplementedError until model is integrated.

        Real implementation requirements:
        - Windows host with WEAP installed and a valid SEI licence.
        - Path to the WEAP-MENA study area file (.weap) set in model_configs/default.yaml
          under ``weap_mena.study_path``.
        - COM automation via win32com.client.Dispatch("WEAP.WEAPApplication") or a
          headless subprocess call to weap.exe.
        - Logic to create or update a scenario branch from the ``inputs`` dict, run
          the simulation, and export results (Unmet Demand [m³/yr], Supply Coverage
          [%]) as CSV for parse_outputs to consume.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until integration is complete.
        """
        raise NotImplementedError(
            "WEAPAdapter.execute() is a stub. To integrate WEAP-MENA: "
            "(1) configure 'weap_mena.study_path' in configs/model_configs/default.yaml; "
            "(2) implement COM automation or subprocess invocation of weap.exe on a "
            "Windows host with a valid SEI licence; "
            "(3) implement scenario branch creation from the inputs dict; "
            "(4) parse exported CSV results and return a ModelOutput."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through as a ModelOutput container.

        The real implementation should parse WEAP result CSV/Excel exports and
        populate the ``outputs`` dict with standardised keys such as:
            - ``unmet_demand_m3_per_yr``: dict mapping country -> float
            - ``supply_coverage_pct``: dict mapping country -> float
            - ``simulation_years``: list of simulated calendar years

        Args:
            raw: Raw output from execute() (passthrough for stub).

        Returns:
            ModelOutput wrapping the raw value unchanged.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
