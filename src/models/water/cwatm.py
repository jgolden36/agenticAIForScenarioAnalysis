"""Adapter for CWatM — Community Water Model (IIASA).

CWatM is an open-source Python global hydrological model developed at IIASA.
It simulates water availability, water demand, and sectoral water use at 0.5
degree and 5 arcmin spatial resolutions, with explicit representation of
human water management (reservoirs, irrigation, domestic / industrial demand).
In the Hormuz pipeline it provides community- and sector-scale assessments of
water-availability shortfalls under crisis-induced infrastructure disruption.

Execution architecture
----------------------
CWatM is configured via an INI-style settings file (sections like
``[OPTIONS]``, ``[FILE_PATHS]``, ``[OUTPUT]``) and is invoked as
``python run_cwatm.py <settings_file>`` from the CWatM repository root.
NetCDF input forcing data (climate, land-use, soil, reservoir
characteristics) is referenced via paths inside the settings file.

The adapter:

  1. Validates that ``cwatm_root`` contains a runnable CWatM entry point
     (``run_cwatm.py`` or the legacy ``cwatm.py``).
  2. Loads the baseline settings file with ``configparser``, applies the
     scenario shocks, writes a per-scenario settings copy into an isolated
     working directory, and points its ``[OUTPUT].PathOut`` at a per-scenario
     output subdirectory.
  3. Invokes CWatM via subprocess and captures stdout/stderr.
  4. Reads the standard output NetCDFs (``discharge.nc``, ``unmetDemand.nc``,
     ``actualET.nc``, ``storGroundwater.nc``) and aggregates them into
     standardized basin / domain-level summaries.

Scenario shocks applied in ``translate_inputs``:
  * ``water_demand_change_pct`` -> scales demand multipliers
    (``domesticDemandMultiplier``, ``industryDemandMultiplier``,
    ``irrigationDemandMultiplier``) by ``1 + pct/100``.
  * ``supply_infrastructure_status`` -> looks up a numeric multiplier from
    ``_INFRA_STATUS_MULTIPLIERS`` and applies it to
    ``desalinationCapacity``, ``useWaterTransfers`` and
    ``reservoirReleaseFactor``.
  * ``disruption_duration_months`` -> sets ``StepEnd`` (or
    ``SpinUp``/``StepEnd`` pair) so the simulation covers the disruption
    window starting from ``StepStart``.

Real integration requirements
-----------------------------
* ``git clone https://github.com/iiasa/CWatM`` into ``Models/Water/CWatM/``.
* A working CWatM Python venv with ``numpy``, ``scipy``, ``netCDF4``, ``gdal``
  and ``rasterio``. The adapter does NOT install CWatM; it invokes whatever
  ``python_executable`` you point it at.
* A regional input dataset (e.g. the Persian Gulf or Rhine sample bundle from
  the IIASA CWatM data portal). Path goes in ``data_path``.
* A baseline settings file referencing the dataset above.
"""

from __future__ import annotations

import configparser
import io
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parameter specifications
# ---------------------------------------------------------------------------

_REQUIRED_PARAMS: list[str] = [
    "water_demand_change_pct",
    "supply_infrastructure_status",
    "disruption_duration_months",
]

_BOUNDS: dict[str, tuple[float, float]] = {
    "water_demand_change_pct": (-50.0, 200.0),
    "disruption_duration_months": (0.0, 60.0),
}

_VALID_INFRASTRUCTURE_STATUSES: frozenset[str] = frozenset(
    {"intact", "partially_damaged", "severely_damaged", "destroyed"}
)

_INFRA_STATUS_MULTIPLIERS: dict[str, float] = {
    "intact": 1.0,
    "partially_damaged": 0.6,
    "severely_damaged": 0.25,
    "destroyed": 0.0,
}

# CWatM settings keys we mutate. These match the canonical names used in the
# IIASA CWatM 1.x sample settings files. If your baseline uses different
# casing, set ``settings_overrides_demand_keys`` / ``settings_overrides_infra_keys``
# in the config to override.
_DEFAULT_DEMAND_KEYS: list[str] = [
    "domesticDemandMultiplier",
    "industryDemandMultiplier",
    "irrigationDemandMultiplier",
    "livestockDemandMultiplier",
]

_DEFAULT_INFRA_KEYS: list[str] = [
    "desalinationCapacity",
    "useWaterTransfers",
    "reservoirReleaseFactor",
]

# CWatM output variable name -> standardized pipeline key.
_OUTPUT_VAR_KEYS: dict[str, str] = {
    "discharge": "river_discharge_m3_per_s",
    "unmetDemand": "unmet_demand_m3_per_s",
    "actualET": "actual_evapotranspiration_mm_per_day",
    "storGroundwater": "groundwater_storage_mm",
    "totalDemand": "total_water_demand_m3_per_s",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class CWatMConfig(BaseModel):
    """Configuration for the CWatM adapter."""

    model_config = {"protected_namespaces": ()}

    cwatm_root: Path = Field(
        description=(
            "Path to a CWatM checkout (must contain run_cwatm.py or cwatm.py)."
        ),
    )
    baseline_settings_path: Path = Field(
        description="Path to the baseline CWatM settings INI file.",
    )
    data_path: Path = Field(
        description=(
            "Path to the directory containing the NetCDF forcing/static input "
            "data referenced by the settings file."
        ),
    )
    output_dir: Path = Field(
        default=Path("data/outputs/cwatm"),
        description="Base directory for per-scenario output subfolders.",
    )
    python_executable: str = Field(
        default="python",
        description="Python interpreter that has CWatM and its deps installed.",
    )
    entry_point: str = Field(
        default="run_cwatm.py",
        description="CWatM entry script (run_cwatm.py or cwatm.py).",
    )
    timeout_seconds: int = Field(
        default=14400,
        description="Maximum wall-clock seconds for a CWatM run.",
    )
    keep_working_copy: bool = Field(
        default=False,
        description="If True, keep the per-scenario working directory.",
    )
    extra_env: dict[str, str] = Field(
        default_factory=dict,
        description="Extra env vars (e.g. GDAL_DATA, PROJ_LIB).",
    )
    omp_num_threads: int = Field(
        default=1,
        description="Threads for OMP/MKL/OpenBLAS in CWatM dependencies.",
    )
    demand_keys: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_DEMAND_KEYS),
        description=(
            "Settings keys (case-insensitive) treated as demand multipliers "
            "and scaled by (1 + water_demand_change_pct/100)."
        ),
    )
    infra_keys: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_INFRA_KEYS),
        description=(
            "Settings keys treated as infrastructure-capacity multipliers and "
            "scaled by the supply_infrastructure_status multiplier."
        ),
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class CWatMAdapter(ModelAdapter):
    """Adapter for the CWatM (Community Water Model) global hydrological model."""

    def __init__(self, config: CWatMConfig | None = None) -> None:
        self._config = config

    # -- Identity properties ------------------------------------------------

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

    # -- Input translation --------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply scenario shocks to the baseline settings and return a dict
        consumed by ``execute()``.

        If no config is set, the params are passed through with
        ``mutation_applied=False`` so ``execute()`` can raise a clean error.
        """
        scenario_id = str(params.get("scenario_id", "default"))

        baseline_text = ""
        baseline_settings: configparser.RawConfigParser | None = None
        n_demand_keys_scaled = 0
        n_infra_keys_scaled = 0
        modified_text = ""
        period_start: str | None = None
        period_end: str | None = None
        mutation_applied = False

        demand_factor = 1.0 + float(params.get("water_demand_change_pct", 0.0)) / 100.0
        status = str(params.get("supply_infrastructure_status", "intact"))
        infra_factor = _INFRA_STATUS_MULTIPLIERS.get(status, 1.0)
        duration_months = float(params.get("disruption_duration_months", 0.0))

        if self._config is not None and self._config.baseline_settings_path.is_file():
            baseline_text = self._config.baseline_settings_path.read_text(
                encoding="utf-8", errors="replace"
            )
            baseline_settings = self._read_settings(baseline_text)

            n_demand_keys_scaled = self._scale_settings_section(
                baseline_settings, self._config.demand_keys, demand_factor
            )
            n_infra_keys_scaled = self._scale_settings_section(
                baseline_settings, self._config.infra_keys, infra_factor
            )

            period_start, period_end = self._set_simulation_period(
                baseline_settings, duration_months
            )

            buf = io.StringIO()
            baseline_settings.write(buf)
            modified_text = buf.getvalue()
            mutation_applied = True

        return {
            "scenario_id": scenario_id,
            "modified_settings_text": modified_text,
            "mutation_applied": mutation_applied,
            "mutation_summary": {
                "demand_factor": demand_factor,
                "infra_factor": infra_factor,
                "demand_keys_scaled": n_demand_keys_scaled,
                "infra_keys_scaled": n_infra_keys_scaled,
                "period_start": period_start,
                "period_end": period_end,
            },
            "params_in": dict(params),
        }

    # -- Execution ----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        if self._config is None:
            raise NotImplementedError(
                "CWatMAdapter.execute() requires a CWatMConfig. To integrate "
                "CWatM:\n"
                "  1. git clone https://github.com/iiasa/CWatM into "
                "Models/Water/CWatM/.\n"
                "  2. Install CWatM's Python deps (numpy, scipy, netCDF4, gdal, "
                "rasterio) into a venv.\n"
                "  3. Configure cwatm_root, baseline_settings_path, data_path "
                "and python_executable in configs/model_configs/cwatm.yaml.\n"
                "  4. Re-build the registry via build_default_registry(config_dir=...)."
            )

        if not isinstance(inputs, dict):
            raise TypeError(
                f"CWatM inputs must be a dict from translate_inputs(); got {type(inputs)}"
            )

        config = self._config
        self._validate_prerequisites(config)

        scenario_id = str(inputs.get("scenario_id", "default"))
        scenario_output_dir = (
            config.output_dir / f"scenario_{scenario_id}"
        ).resolve()
        scenario_output_dir.mkdir(parents=True, exist_ok=True)

        work_dir = Path(tempfile.mkdtemp(prefix=f"cwatm_{scenario_id}_"))
        try:
            settings_text = inputs.get("modified_settings_text", "") or ""
            if not settings_text:
                # Fallback to baseline if mutation didn't run (no parser).
                settings_text = config.baseline_settings_path.read_text(
                    encoding="utf-8", errors="replace"
                )

            # Inject scenario output directory in [OUTPUT] PathOut so per-scenario
            # outputs go to a known location.
            settings_text = self._inject_output_path(settings_text, scenario_output_dir)

            settings_file = work_dir / "scenario_settings.ini"
            settings_file.write_text(settings_text, encoding="utf-8")

            t_start = time.time()
            run_result = self._run_cwatm(config, settings_file)
            elapsed = time.time() - t_start

            netcdf_files = self._discover_netcdfs(scenario_output_dir)

            raw = {
                "scenario_id": scenario_id,
                "settings_path": str(settings_file),
                "output_dir": str(scenario_output_dir),
                "netcdf_files": [str(p) for p in netcdf_files],
            }

            output = self.parse_outputs(raw)
            output.metadata.update({
                "scenario_id": scenario_id,
                "params_in": inputs.get("params_in", {}),
                "mutation_applied": inputs.get("mutation_applied", False),
                "mutation_summary": inputs.get("mutation_summary", {}),
                "settings_path": str(settings_file),
                "scenario_output_dir": str(scenario_output_dir),
                "elapsed_seconds": round(elapsed, 2),
                "cwatm_returncode": run_result.returncode,
                "stdout_tail": run_result.stdout[-2000:] if run_result.stdout else "",
                "stderr_tail": run_result.stderr[-2000:] if run_result.stderr else "",
            })
            return output

        finally:
            if not config.keep_working_copy:
                shutil.rmtree(work_dir, ignore_errors=True)

    # -- Output parsing -----------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse CWatM NetCDF outputs into standardized basin-aggregate dicts.

        For each known CWatM variable found in the output dir, computes a
        time-mean and a domain-aggregate, plus a basin-mean time series.
        Derives a dimensionless ``water_availability_index`` from the ratio of
        unmet to total demand when both are present.

        If ``netCDF4`` is not installed, returns an empty outputs dict and
        records the error in metadata so downstream synthesis flags the run.
        """
        if not isinstance(raw, dict):
            raw = {"netcdf_files": []}

        outputs: dict[str, Any] = {}
        diagnostics: dict[str, Any] = {}

        try:
            import netCDF4  # noqa: F401
        except ImportError:
            diagnostics["netcdf_parse_error"] = (
                "netCDF4 is not installed; cannot parse CWatM outputs. "
                "pip install netCDF4 to enable parsing."
            )
            return ModelOutput(
                model_id=self.model_id,
                convergence_status="completed_unparsed",
                outputs={"netcdf_files": raw.get("netcdf_files", [])},
                diagnostics=diagnostics,
                metadata={"unit_notes": _unit_notes()},
            )

        from netCDF4 import Dataset  # type: ignore

        time_means: dict[str, dict[str, float]] = {}
        time_series: dict[str, list[float]] = {}
        time_axis: list[str] = []

        for nc_path_str in raw.get("netcdf_files", []):
            nc_path = Path(nc_path_str)
            var_stem = nc_path.stem
            std_key = _OUTPUT_VAR_KEYS.get(var_stem, var_stem)

            try:
                with Dataset(str(nc_path), mode="r") as ds:
                    # CWatM convention: the variable name often matches the file stem.
                    # Find the principal data variable (the one that's not a
                    # coordinate).
                    coords = set(ds.dimensions.keys())
                    candidates = [
                        name for name in ds.variables
                        if name not in coords and name not in ("lat", "lon", "time", "x", "y")
                    ]
                    var_name = (
                        var_stem if var_stem in ds.variables
                        else (candidates[0] if candidates else None)
                    )
                    if var_name is None:
                        continue

                    var = ds.variables[var_name]
                    arr = var[:]

                    # Domain aggregate (time-mean over space, then over time)
                    try:
                        spatial_mean = arr.mean(axis=tuple(range(1, arr.ndim))) \
                            if arr.ndim > 1 else arr
                        spatial_mean = spatial_mean.compressed() \
                            if hasattr(spatial_mean, "compressed") else spatial_mean
                        time_series[std_key] = [float(v) for v in spatial_mean]
                        time_means[std_key] = {
                            "mean": float(spatial_mean.mean())
                            if len(spatial_mean) > 0 else float("nan"),
                            "min": float(spatial_mean.min())
                            if len(spatial_mean) > 0 else float("nan"),
                            "max": float(spatial_mean.max())
                            if len(spatial_mean) > 0 else float("nan"),
                            "n_steps": int(len(spatial_mean)),
                        }
                    except Exception as exc:  # noqa: BLE001
                        diagnostics[f"aggregation_error_{std_key}"] = str(exc)

                    # Capture time axis once
                    if not time_axis and "time" in ds.variables:
                        try:
                            t_var = ds.variables["time"]
                            time_axis = [str(v) for v in t_var[:]]
                        except Exception:  # noqa: BLE001
                            pass
            except Exception as exc:  # noqa: BLE001
                diagnostics[f"read_error_{var_stem}"] = str(exc)

        outputs.update({
            "time_means": time_means,
            "time_series": time_series,
            "time_axis": time_axis,
            "netcdf_files": raw.get("netcdf_files", []),
        })

        # Derived: water availability index (basin-mean), per time step.
        unmet = time_series.get("unmet_demand_m3_per_s", [])
        total = time_series.get("total_water_demand_m3_per_s", [])
        if unmet and total and len(unmet) == len(total):
            wai = []
            for u, t in zip(unmet, total):
                if t and t > 0:
                    wai.append(max(0.0, min(1.0, 1.0 - (u / t))))
                else:
                    wai.append(1.0)
            outputs["water_availability_index_time_series"] = wai
            outputs["water_availability_index_mean"] = (
                sum(wai) / len(wai) if wai else float("nan")
            )

        return ModelOutput(
            model_id=self.model_id,
            convergence_status="completed",
            outputs=outputs,
            diagnostics=diagnostics,
            metadata={"unit_notes": _unit_notes()},
        )

    # ======================================================================
    # Private helpers
    # ======================================================================

    def _validate_prerequisites(self, config: CWatMConfig) -> None:
        if not config.cwatm_root.is_dir():
            raise FileNotFoundError(
                f"CWatM root directory not found: {config.cwatm_root}. "
                "git clone https://github.com/iiasa/CWatM into Models/Water/CWatM/."
            )
        entry = config.cwatm_root / config.entry_point
        if not entry.is_file():
            # Try fallback names
            alternatives = ["run_cwatm.py", "cwatm.py", "cwatm/run_cwatm.py"]
            found = next(
                (config.cwatm_root / a for a in alternatives
                 if (config.cwatm_root / a).is_file()),
                None,
            )
            if found is None:
                raise FileNotFoundError(
                    f"CWatM entry script not found at {entry}. Tried alternatives: "
                    f"{alternatives}. Set 'entry_point' in the config to match your CWatM checkout."
                )
        if not config.baseline_settings_path.is_file():
            raise FileNotFoundError(
                f"CWatM baseline settings file not found: {config.baseline_settings_path}."
            )
        if not config.data_path.is_dir():
            raise FileNotFoundError(
                f"CWatM data directory not found: {config.data_path}."
            )

    @staticmethod
    def _read_settings(text: str) -> configparser.RawConfigParser:
        """Read a CWatM INI settings file.

        Uses RawConfigParser (no interpolation) because CWatM settings often
        contain ``%`` characters that would otherwise be parsed as interpolation
        references.
        """
        parser = configparser.RawConfigParser(strict=False, allow_no_value=True)
        parser.optionxform = str  # preserve case
        parser.read_string(text)
        return parser

    @staticmethod
    def _scale_settings_section(
        parser: configparser.RawConfigParser,
        keys: list[str],
        factor: float,
    ) -> int:
        """Scan all sections for the given keys (case-insensitive) and multiply
        their numeric value by ``factor``. Returns the number of keys updated.
        """
        n_updated = 0
        keys_lower = {k.lower() for k in keys}
        for section in parser.sections():
            for opt in list(parser.options(section)):
                if opt.lower() not in keys_lower:
                    continue
                raw = parser.get(section, opt)
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    continue
                new_val = val * factor
                parser.set(section, opt, f"{new_val:g}")
                n_updated += 1
        return n_updated

    @staticmethod
    def _set_simulation_period(
        parser: configparser.RawConfigParser,
        duration_months: float,
    ) -> tuple[str | None, str | None]:
        """Set CWatM ``StepEnd`` based on ``StepStart`` + duration_months.

        Returns the (start, end) date strings as written. Both are formatted
        ``DD/MM/YYYY`` to match CWatM's default convention.
        """
        if duration_months <= 0:
            return None, None

        start_str: str | None = None
        for section in parser.sections():
            if parser.has_option(section, "StepStart"):
                start_str = parser.get(section, "StepStart")
                break

        if not start_str:
            return None, None

        start_dt = _parse_cwatm_date(start_str)
        if start_dt is None:
            return start_str, None

        end_dt = start_dt + timedelta(days=int(round(duration_months * 30.4375)))
        end_str = end_dt.strftime("%d/%m/%Y")

        for section in parser.sections():
            if parser.has_option(section, "StepEnd"):
                parser.set(section, "StepEnd", end_str)
                return start_str, end_str

        return start_str, None

    @staticmethod
    def _inject_output_path(settings_text: str, output_dir: Path) -> str:
        """Ensure the [OUTPUT] section's PathOut points at output_dir.

        We re-parse, set, and re-serialize so any existing PathOut is overwritten;
        if [OUTPUT] doesn't exist we append it.
        """
        parser = configparser.RawConfigParser(strict=False, allow_no_value=True)
        parser.optionxform = str
        try:
            parser.read_string(settings_text)
        except configparser.Error:
            return settings_text

        if "OUTPUT" not in parser.sections():
            parser.add_section("OUTPUT")
        parser.set("OUTPUT", "PathOut", str(output_dir).replace("\\", "/"))

        buf = io.StringIO()
        parser.write(buf)
        return buf.getvalue()

    def _run_cwatm(
        self,
        config: CWatMConfig,
        settings_file: Path,
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, **config.extra_env}
        threads = str(config.omp_num_threads)
        env.setdefault("OMP_NUM_THREADS", threads)
        env.setdefault("MKL_NUM_THREADS", threads)
        env.setdefault("OPENBLAS_NUM_THREADS", threads)

        cmd = [
            config.python_executable,
            config.entry_point,
            str(settings_file),
        ]
        logger.info("Running CWatM: %s (cwd=%s)", " ".join(cmd), config.cwatm_root)
        try:
            result = subprocess.run(
                cmd,
                cwd=str(config.cwatm_root),
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"CWatM timed out after {config.timeout_seconds}s "
                f"(cwd={config.cwatm_root})."
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"CWatM failed (rc={result.returncode}). "
                f"stderr tail: {result.stderr[-1500:] if result.stderr else ''} "
                f"stdout tail: {result.stdout[-1500:] if result.stdout else ''}"
            )
        return result

    @staticmethod
    def _discover_netcdfs(output_dir: Path) -> list[Path]:
        """Return all NetCDF files written under output_dir (recursive)."""
        if not output_dir.is_dir():
            return []
        return sorted(output_dir.rglob("*.nc"))


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _unit_notes() -> dict[str, str]:
    return {
        "river_discharge_m3_per_s": "Discharge in m^3/s, basin-mean per time step.",
        "unmet_demand_m3_per_s": "Unmet water demand, m^3/s, basin-mean.",
        "actual_evapotranspiration_mm_per_day": "Actual ET, mm/day.",
        "groundwater_storage_mm": "Groundwater storage, mm.",
        "total_water_demand_m3_per_s": "Total demand, m^3/s.",
        "water_availability_index": (
            "Derived: clip(1 - unmet_demand / total_demand, 0, 1). 1.0 = fully met."
        ),
    }


def _parse_cwatm_date(date_str: str) -> datetime | None:
    """Parse a CWatM date string. CWatM accepts DD/MM/YYYY, YYYY-MM-DD, and step
    numbers (we don't support step numbers here)."""
    s = date_str.strip().strip('"').strip("'")
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
