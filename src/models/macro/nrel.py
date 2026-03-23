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

# Parameters that must be present for NREL to run
REQUIRED_PARAMS = frozenset(
    {
        "natural_gas_price_change_pct",
        "electricity_demand_change_pct",
        "disruption_duration_months",
    }
)


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
        """Execute the NREL electricity sector model.

        Not yet implemented. The real implementation will:
        1. Inject natural gas price path overrides into NREL ReEDS scenario
           configuration files
        2. Invoke the ReEDS model via subprocess or NREL's Python API
        3. Monitor run progress and collect convergence diagnostics
        4. Extract dispatch mix, capacity utilization, and retail price outputs
        5. Return structured results for downstream short-run macro models

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until the real NREL integration is built.
        """
        raise NotImplementedError(
            "NRELAdapter.execute() is not yet implemented. "
            "Real implementation requires: (1) access to the NREL ReEDS model or Cambium "
            "dataset (available via NREL's open-source repository or data API), "
            "(2) scenario configuration files specifying natural gas price overrides "
            "for the disruption period, (3) a Python environment with the NREL model "
            "dependencies, and (4) post-processing scripts to extract dispatch mix, "
            "retail electricity prices, and capacity utilization from ReEDS output files."
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
