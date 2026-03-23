"""Adapter stub for CWatM — Community Water Model.

CWatM (Community Water Model) is an open-source global hydrological model
developed at IIASA (International Institute for Applied Systems Analysis). It
simulates water availability, water demand, and water use at 0.5° and 5-arcmin
spatial resolutions, with explicit representation of human water management
including reservoirs, irrigation, and domestic/industrial demand. In the Hormuz
pipeline it provides community- and sector-scale assessments of water availability
shortfalls under crisis-induced disruption, complementing WaterGAP2's basin-scale
perspective with finer-grained demand-side dynamics.

Real integration requirements:
- A Python environment with CWatM installed (available from the IIASA GitHub
  repository: https://github.com/iiasa/CWatM) and all required geospatial
  dependencies (numpy, netCDF4, scipy, gdal/rasterio).
- Pre-downloaded global input data (climate forcing, land use, soil parameters,
  reservoir characteristics) for the simulation domain, referenced via CWatM's
  settings XML file.
- Logic to modify the CWatM settings file (XML) or input parameter NetCDFs to
  reflect the ``water_demand_change_pct`` and ``supply_infrastructure_status``
  parameters for each crisis scenario.
- Subprocess invocation of the CWatM model (python cwatm.py <settings.xml>)
  or programmatic execution via CWatM's Python API if available.
- Post-run extraction of output NetCDF variables (actual water consumption,
  unmet demand, reservoir storage) for parse_outputs to consume.
"""

from __future__ import annotations

from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

# Required parameter names, sourced from WATER_MODEL_SPECS["cwatm"].
_REQUIRED_PARAMS: list[str] = [
    "water_demand_change_pct",
    "supply_infrastructure_status",
    "disruption_duration_months",
]

# Plausibility bounds for numeric parameters.
_BOUNDS: dict[str, tuple[float, float]] = {
    "water_demand_change_pct": (-50.0, 200.0),  # demand can spike or fall
    "disruption_duration_months": (0.0, 60.0),  # up to 5 years
}

# Valid categorical values for supply_infrastructure_status.
_VALID_INFRASTRUCTURE_STATUSES: frozenset[str] = frozenset(
    {
        "intact",
        "partially_damaged",
        "severely_damaged",
        "destroyed",
    }
)


class CWatMAdapter(ModelAdapter):
    """Adapter stub for the CWatM (Community Water Model) global hydrological model."""

    # ------------------------------------------------------------------
    # Identity properties
    # ------------------------------------------------------------------

    @property
    def model_id(self) -> str:
        return "cwatm"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "CWatM: Community Water Model (IIASA). Simulates water availability, "
            "sectoral water demand, and unmet demand at community and basin scale "
            "under crisis-induced supply infrastructure disruption. Complements "
            "WaterGAP2 with demand-side dynamics and reservoir management under "
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

        # Categorical check: supply_infrastructure_status must be a recognised value
        if "supply_infrastructure_status" in params:
            val = params["supply_infrastructure_status"]
            if not isinstance(val, str):
                errors.append(
                    f"Parameter 'supply_infrastructure_status' must be a string; "
                    f"got {type(val).__name__}"
                )
            elif val not in _VALID_INFRASTRUCTURE_STATUSES:
                warnings.append(
                    f"Parameter 'supply_infrastructure_status' value {val!r} is not "
                    f"one of the recognised categories "
                    f"{sorted(_VALID_INFRASTRUCTURE_STATUSES)}. CWatM damage "
                    f"translation logic may not handle this value correctly."
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pass parameters through unchanged.

        CWatM is configured via an XML settings file and NetCDF input overlays.
        Translation of the ``inputs`` dict into modified settings and raster
        masks is the responsibility of the real execute() implementation.

        Args:
            params: Validated parameter dictionary.

        Returns:
            The same dictionary, unmodified.
        """
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute CWatM. Raises NotImplementedError until model is integrated.

        Real implementation requirements:
        - A Python environment with CWatM and its geospatial dependencies installed;
          path to the CWatM entry point set in model_configs/default.yaml under
          ``cwatm.script_path``.
        - Path to the baseline CWatM settings XML file set under
          ``cwatm.settings_path``, and to the global input data directory under
          ``cwatm.data_path``.
        - Logic to create a scenario-specific copy of the settings XML and modify
          demand multipliers (from ``water_demand_change_pct``) and infrastructure
          capacity overlays (from ``supply_infrastructure_status``) for the
          ``disruption_duration_months`` simulation period.
        - Subprocess invocation:
              python cwatm.py <scenario_settings.xml>
          or programmatic call if CWatM exposes a Python API.
        - Capture of stdout/stderr and any convergence diagnostics written to log
          files.
        - Post-run extraction of NetCDF output variables for parse_outputs.

        Args:
            inputs: Translated inputs from translate_inputs.

        Raises:
            NotImplementedError: Always, until integration is complete.
        """
        raise NotImplementedError(
            "CWatMAdapter.execute() is a stub. To integrate CWatM: "
            "(1) configure 'cwatm.script_path', 'cwatm.settings_path', and "
            "'cwatm.data_path' in configs/model_configs/default.yaml; "
            "(2) implement logic to write a scenario-specific settings XML with "
            "demand multipliers and infrastructure status overlays derived from "
            "the inputs dict; "
            "(3) invoke CWatM via subprocess (python cwatm.py <settings.xml>) and "
            "capture stdout/stderr and log diagnostics; "
            "(4) extract NetCDF output variables and return a ModelOutput."
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through as a ModelOutput container.

        The real implementation should extract variables from CWatM's NetCDF output
        files and populate the ``outputs`` dict with standardised keys such as:
            - ``unmet_demand_m3_per_s``: gridded array or basin-level aggregates
            - ``actual_water_consumption_km3``: sectoral breakdown by region
            - ``reservoir_storage_m3``: time series of reservoir storage
            - ``water_availability_index``: dimensionless stress indicator (0–1)

        Args:
            raw: Raw output from execute() (passthrough for stub).

        Returns:
            ModelOutput wrapping the raw value unchanged.
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
