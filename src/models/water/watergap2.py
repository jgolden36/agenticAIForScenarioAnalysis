"""Adapter stub for WaterGAP2 — Global gridded hydrological model.

WaterGAP2 (Water — Global Assessment and Prognosis, version 2) is a global
gridded hydrological model operating at 0.5° spatial resolution. It simulates
continental water resources (river discharge, groundwater recharge, lake and
wetland storage) and water use across all major sectors. In the Hormuz pipeline
it provides a globally consistent picture of how water infrastructure damage —
particularly destruction of desalination plants and freshwater distribution
networks — propagates through the hydrological system beyond the immediate
conflict zone.

Real integration requirements:
- A compiled WaterGAP2 binary or the Fortran source distribution, accessible on
  the execution host. Alternatively the WaterGAP2 team provides a web-service API
  for external users; this adapter can be implemented against either interface.
- Pre-processed global climate forcing data (precipitation, temperature) for the
  simulation period in NetCDF format.
- A grid-level infrastructure damage mask derived from the ``affected_grid_cells``
  and ``infrastructure_damage_index`` parameters, formatted as a NetCDF or ASCII
  raster compatible with WaterGAP2's input conventions.
- Post-run extraction of gridded output variables (discharge [m³/s], water
  withdrawal [km³/yr], water stress index [-]) from WaterGAP2's NetCDF outputs.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Required parameter names, sourced from WATER_MODEL_SPECS["watergap2"].
_REQUIRED_PARAMS: list[str] = [
    "infrastructure_damage_index",
    "affected_grid_cells",
    "disruption_duration_months",
]

# Plausibility bounds for numeric parameters.
_BOUNDS: dict[str, tuple[float, float]] = {
    "infrastructure_damage_index": (0.0, 1.0),
    "disruption_duration_months": (0.0, 60.0),  # up to 5 years
}


class WaterGAP2Adapter(ModelAdapter):
    """Adapter stub for the WaterGAP2 global gridded hydrological model."""

    # ------------------------------------------------------------------
    # Identity properties
    # ------------------------------------------------------------------

    @property
    def model_id(self) -> str:
        return "watergap2"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "WaterGAP2: Global gridded hydrological model (0.5° resolution). "
            "Simulates the propagation of water infrastructure damage through "
            "continental water resources and sectoral water use globally under "
            "Strait of Hormuz closure scenarios."
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

        # Numeric plausibility checks
        for param_name, (lo, hi) in _BOUNDS.items():
            if param_name not in params:
                continue
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

        # Structural check: affected_grid_cells must be a non-empty region specification
        if "affected_grid_cells" in params:
            val = params["affected_grid_cells"]
            # Accept either a list of (lat, lon) tuples, a bounding-box dict, or a
            # string path to a raster mask; reject None/empty.
            if val is None:
                errors.append(
                    "Parameter 'affected_grid_cells' must not be None; provide a list "
                    "of grid-cell coordinates, a bounding-box dict, or a raster path."
                )
            elif isinstance(val, (list, dict)) and len(val) == 0:
                warnings.append(
                    "Parameter 'affected_grid_cells' is empty; WaterGAP2 will apply "
                    "no spatial mask and treat the entire globe as unaffected."
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through unchanged.

        WaterGAP2 reads NetCDF forcing files and ASCII/NetCDF parameter overlays.
        Translation of the ``inputs`` dict into a grid-level damage mask NetCDF is
        the responsibility of the real execute() implementation.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same dictionary, unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute WaterGAP2. Raises NotImplementedError until model is integrated.

        Real implementation requirements:
        - Path to the WaterGAP2 binary or API endpoint set in
          model_configs/default.yaml under ``watergap2.executable_path`` or
          ``watergap2.api_url``.
        - Path to global climate forcing data (NetCDF) set under
          ``watergap2.forcing_data_path``.
        - Logic to construct a grid-level infrastructure damage mask from
          ``affected_grid_cells`` and ``infrastructure_damage_index`` and write it
          as a NetCDF raster in WaterGAP2's expected format.
        - Subprocess invocation of the WaterGAP2 binary with the modified parameter
          set, or equivalent API call, covering the ``disruption_duration_months``
          simulation period.
        - Capture of stdout/stderr and convergence diagnostics.
        - Post-run extraction of gridded NetCDF outputs for parse_outputs.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until integration is complete.
        """
        raise NotImplementedError(
            "WaterGAP2Adapter.execute() is a stub. To integrate WaterGAP2: "
            "(1) configure 'watergap2.executable_path' (or 'watergap2.api_url') and "
            "'watergap2.forcing_data_path' in configs/model_configs/default.yaml; "
            "(2) implement logic to build a NetCDF infrastructure damage mask from "
            "the 'affected_grid_cells' and 'infrastructure_damage_index' parameters; "
            "(3) invoke WaterGAP2 via subprocess or API and capture diagnostics; "
            "(4) extract gridded NetCDF outputs and return a ModelOutput."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through as a ModelOutput container.

        The real implementation should extract variables from WaterGAP2's NetCDF
        output files and populate the ``outputs`` dict with standardised keys such
        as:
            - ``river_discharge_m3_per_s``: gridded array or regional aggregates
            - ``water_stress_index``: gridded array or basin-level summary (0–1)
            - ``water_withdrawal_km3_per_yr``: sectoral breakdown by region
            - ``groundwater_depletion_km3``: cumulative over simulation period

        Args:
            raw: Raw output from execute() (passthrough for stub).

        Returns:
            ModelOutput wrapping the raw value unchanged.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
