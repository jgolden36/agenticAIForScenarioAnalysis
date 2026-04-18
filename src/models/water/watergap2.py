"""Adapter for WaterGAP2 — Global gridded hydrological model.

WaterGAP2 (Water — Global Assessment and Prognosis, version 2) is a global
gridded hydrological model operating at 0.5 degree spatial resolution. It
simulates continental water resources (river discharge, groundwater recharge,
lake and wetland storage) and water use across all major sectors. In the
Hormuz pipeline it provides a globally consistent picture of how water
infrastructure damage -- particularly destruction of desalination plants and
freshwater distribution networks -- propagates through the hydrological
system beyond the immediate conflict zone.

Status: **config-aware stub.** The repository ships only the WaterGAP2 C++
sources (``Models/Water/WaterGAP2-v2.2d/HydrologyFrankfurt-WaterGAP2-65f306b/source/``);
no compiled binary, no climate forcing data. Until those prerequisites are
in place the adapter validates the config and then raises
``NotImplementedError``.

Real integration requirements
-----------------------------
* A compiled WaterGAP2 binary, built from the bundled C++ sources via CMake,
  OR access to the WaterGAP2 web-service API operated by the
  Goethe-University Frankfurt team.
* Pre-processed global climate forcing data (precipitation, temperature) for
  the simulation period in NetCDF format.
* A grid-level infrastructure damage mask derived from the
  ``affected_grid_cells`` and ``infrastructure_damage_index`` parameters,
  formatted as a NetCDF or ASCII raster compatible with WaterGAP2.
* Post-run extraction of gridded NetCDF output variables (discharge,
  withdrawal, water-stress index).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

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
    "disruption_duration_months": (0.0, 60.0),
}


class WaterGAP2Config(BaseModel):
    """Configuration for the WaterGAP2 adapter.

    Exactly one of ``executable_path`` and ``api_url`` must be provided. The
    adapter validates this in a model_validator at instantiation time.
    """

    model_config = {"protected_namespaces": ()}

    executable_path: Path | None = Field(
        default=None,
        description=(
            "Path to a compiled WaterGAP2 binary built from the C++ sources at "
            "Models/Water/WaterGAP2-v2.2d/HydrologyFrankfurt-WaterGAP2-65f306b/source/."
        ),
    )
    api_url: str | None = Field(
        default=None,
        description=(
            "URL of a WaterGAP2 web-service endpoint (Goethe-University Frankfurt). "
            "Used as an alternative to a local executable."
        ),
    )
    forcing_data_path: Path = Field(
        description=(
            "Path to the directory containing precipitation/temperature NetCDF "
            "forcing data for the simulation period."
        ),
    )
    output_dir: Path = Field(
        default=Path("data/outputs/watergap2"),
        description="Base directory for per-scenario output subfolders.",
    )
    simulation_period_years: int = Field(
        default=5,
        description="Length of the WaterGAP2 simulation in calendar years.",
    )
    timeout_seconds: int = Field(
        default=7200,
        description="Maximum wall-clock seconds for a WaterGAP2 run.",
    )
    extra_env: dict[str, str] = Field(
        default_factory=dict,
        description="Extra env vars (e.g. NETCDF_DIR, OMP_NUM_THREADS).",
    )

    @model_validator(mode="after")
    def _exactly_one_endpoint(self) -> "WaterGAP2Config":
        has_exec = self.executable_path is not None
        has_api = self.api_url is not None
        if has_exec == has_api:
            raise ValueError(
                "WaterGAP2Config requires exactly one of "
                "'executable_path' or 'api_url' to be set, not both / neither."
            )
        return self


class WaterGAP2Adapter(ModelAdapter):
    """Adapter (stub) for the WaterGAP2 global gridded hydrological model."""

    def __init__(self, config: WaterGAP2Config | None = None) -> None:
        self._config = config

    # -- Identity properties ------------------------------------------------

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
            "WaterGAP2: Global gridded hydrological model (0.5 degree resolution). "
            "Simulates the propagation of water infrastructure damage through "
            "continental water resources and sectoral water use globally under "
            "Strait of Hormuz closure scenarios."
        )

    # -- Validation ---------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        for name in _REQUIRED_PARAMS:
            if name not in params:
                errors.append(f"Missing required parameter: '{name}'")

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

        if "affected_grid_cells" in params:
            val = params["affected_grid_cells"]
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

    # -- Input translation --------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        return params

    # -- Execution ----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Stub execute(). Validates the config (if any) before raising."""
        if self._config is None:
            raise NotImplementedError(
                "WaterGAP2Adapter.execute() requires a WaterGAP2Config. To "
                "integrate WaterGAP2:\n"
                "  1. Build the binary from the C++ sources at "
                "Models/Water/WaterGAP2-v2.2d/HydrologyFrankfurt-WaterGAP2-65f306b/source/ "
                "via CMake, OR obtain access to the Frankfurt WaterGAP2 web service.\n"
                "  2. Stage global climate forcing NetCDFs (precipitation, temperature) "
                "under forcing_data_path.\n"
                "  3. Configure the adapter via configs/model_configs/watergap2.yaml.\n"
                "  4. Implement either subprocess invocation of the compiled binary or "
                "a REST client against the web service inside this method.\n"
                "  5. Build a NetCDF damage mask from 'affected_grid_cells' and "
                "'infrastructure_damage_index' and pass it to WaterGAP2.\n"
                "  6. Parse gridded NetCDF outputs in parse_outputs."
            )

        self._validate_prerequisites(self._config)

        endpoint_desc = (
            f"executable {self._config.executable_path}"
            if self._config.executable_path is not None
            else f"API {self._config.api_url}"
        )
        raise NotImplementedError(
            "WaterGAP2Adapter.execute() is config-validated but the run driver "
            f"is not yet implemented. Endpoint: {endpoint_desc}. Required next "
            "steps: (a) construct a NetCDF infrastructure-damage mask from the "
            "scenario inputs, (b) drive WaterGAP2 over a "
            f"{self._config.simulation_period_years}-year window, (c) parse "
            "gridded NetCDF outputs in parse_outputs."
        )

    # -- Output parsing -----------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Pass raw outputs through as a ModelOutput container.

        The real implementation should extract variables from WaterGAP2's NetCDF
        output files and populate ``outputs`` with standardised keys such as:

            * ``river_discharge_m3_per_s``: gridded array or regional aggregates
            * ``water_stress_index``: gridded array or basin-level summary (0-1)
            * ``water_withdrawal_km3_per_yr``: sectoral breakdown by region
            * ``groundwater_depletion_km3``: cumulative over simulation period
        """
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _validate_prerequisites(config: WaterGAP2Config) -> None:
        """Check filesystem prerequisites without exercising the binary itself."""
        if config.executable_path is not None and not config.executable_path.is_file():
            raise FileNotFoundError(
                f"WaterGAP2 executable not found: {config.executable_path}. "
                "Build it from the bundled C++ sources via CMake, or set "
                "'api_url' instead of 'executable_path'."
            )
        if not config.forcing_data_path.is_dir():
            raise FileNotFoundError(
                f"WaterGAP2 forcing data directory not found: "
                f"{config.forcing_data_path}."
            )
