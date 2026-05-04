"""MAgPIE model adapter.

MAgPIE (Model of Agricultural Production and its Impact on the Environment)
is a recursive-dynamic optimization model for land use and agricultural
production, developed by PIK Potsdam. It projects how fertilizer price
shocks, crop yield changes, and water availability reductions reshape
global and regional land use, food production, and environmental outcomes.

This adapter targets the MAgPIE codebase located at
``Models/Fertilizer/magpie-master/magpie-master`` in this repository.
MAgPIE's canonical entry point is R (``Rscript start.R``), which handles
configuration, data preparation, GAMS invocation, and post-processing.
A bridge R script (``magpie_bridge.R``, co-located with this module)
translates between the adapter's JSON I/O convention and MAgPIE's
``cfg`` configuration system.

Real integration requirements (see ``Models/.../magpie-master/README.md``):
    - GAMS >= 50.1.0 with CONOPT solver (license required)
    - R >= 4.3 (with Rtools on Windows)
    - pandoc >= 2.14.2, TeX >= 3.14159265
    - MAgPIE input data downloaded via ``scripts/start/download_data.R``
      (or auto-downloaded by ``start_run`` on first invocation).
    - The bridge R script at ``src/models/fertilizer/magpie_bridge.R``
    - The R packages MAgPIE relies on (lucode2, gms, magclass, gdx,
      magpie4, ...) installed via renv on the first ``Rscript start.R``.

Important caveat about shocks:
    Stock MAgPIE has no built-in switches for ad-hoc fertilizer-price,
    yield, water, or transport-cost shocks. The bridge script writes the
    shock multipliers into ``cfg$gms`` so they appear as ``$setglobal``
    entries during GAMS compilation, but the corresponding modules
    (38_factor_costs, 14_yields, 43_water_availability, 40_transport)
    must be patched to consume them. See the bridge script docstring
    for the patch points. Until those patches land, the adapter will
    still execute MAgPIE end-to-end, but with default (unshocked)
    parameter values.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.r_adapter import RAdapter, RConfig
from src.models.base import (
    ModelOutput,
    ResourceRequirements,
    ValidationResult,
)

_REQUIRED_PARAMS = {
    "fertilizer_price_shock_pct": (
        "Percentage increase in fertilizer prices",
        "percent",
    ),
    "crop_yield_impact_pct": (
        "Direct impact on crop yields (negative = reduction)",
        "percent",
    ),
    "water_availability_change_pct": (
        "Change in agricultural water availability (negative = reduction)",
        "percent",
    ),
}

_OPTIONAL_PARAMS = {
    "energy_price_shock_pct": (
        "Percentage increase in energy prices affecting transport costs",
        "percent",
    ),
    "trade_restriction_flag": (
        "Whether to tighten agricultural trade self-sufficiency constraints",
        "boolean",
    ),
    "affected_regions": (
        "List of MAgPIE h12 region codes for region-specific shocks "
        "(default: global)",
        "list",
    ),
    "time_horizon": (
        "MAgPIE c_timesteps key, e.g. 'coup2100', 'quicktest', '5year2050' "
        "(default: from cfg$gms$c_timesteps)",
        "categorical",
    ),
    "ssp_scenario": (
        "SSP/SDP scenario for drivers (default: SSP2)",
        "categorical",
    ),
}

# h12 region aggregation used by MAgPIE's default input data set
# (rev4.126_h12_magpie.tgz). Source: cfg$input in config/default.cfg.
H12_REGIONS = {
    "CAZ", "CHA", "EUR", "IND", "JPN", "LAM",
    "MEA", "NEU", "OAS", "REF", "SSA", "USA",
}

# h12 regions that overlap with Middle East / Persian Gulf area.
# - MEA: Middle East & North Africa
# - IND: India (downstream consumer of Gulf fertilizers)
# - OAS: Other Asia (includes Pakistan, Bangladesh, SE Asia)
MENA_MAGPIE_REGIONS = {"MEA", "IND", "OAS"}

# Valid SSP/SDP scenario tags accepted by module 09_drivers (aug17).
_VALID_SSP_SCENARIOS = {
    "SSP1", "SSP2", "SSP2EU", "SSP3", "SSP4", "SSP5",
    "SDP", "SDP_EI", "SDP_MC", "SDP_RC",
}

# Valid c_timesteps keys recognised by core/sets.gms.
_VALID_TIMESTEPS = {
    "less_TS", "coup2100", "coup2110", "test_TS", "TS_benni",
    "TS_WB", "5year", "5year2050", "5year2070", "quicktest",
    "quicktest2", "calib",
    # plus integer-string keys "1".."16" handled separately.
}

# Default location of the bridge script (relative to project root).
_DEFAULT_BRIDGE_SCRIPT = Path("src/models/fertilizer/magpie_bridge.R")

# Default candidate locations for the MAgPIE source tree. We try the
# nested layout first (it's what the upstream tarball produces when
# extracted under Models/Fertilizer/), then the flattened layout that
# users sometimes commit. The first candidate containing main.gms wins;
# the MAGPIE_ROOT environment variable always wins over both.
_DEFAULT_MAGPIE_ROOT_CANDIDATES: tuple[Path, ...] = (
    Path("Models/Fertilizer/magpie-master/magpie-master"),
    Path("Models/Fertilizer/magpie-master"),
    Path("Models/Fertilizer/magpie"),
)


def _resolve_default_magpie_root() -> Path | None:
    """Return the first candidate path that actually contains main.gms.

    Honours the ``MAGPIE_ROOT`` env var ahead of the candidate list so
    the SLURM driver can pin a specific tree without code changes.
    """
    import os
    env_root = os.environ.get("MAGPIE_ROOT")
    if env_root:
        p = Path(env_root)
        if (p / "main.gms").exists():
            return p
        # Even if main.gms isn't there yet, honour the explicit override
        # so downstream warnings point at the user's intended tree.
        return p
    for cand in _DEFAULT_MAGPIE_ROOT_CANDIDATES:
        if (cand / "main.gms").exists():
            return cand
    return None


# Backwards-compatible re-export — older imports referenced this name.
_DEFAULT_MAGPIE_ROOT = _DEFAULT_MAGPIE_ROOT_CANDIDATES[0]


class MAgPIEAdapter(RAdapter):
    """Adapter for the MAgPIE land-use and agricultural production model.

    Inherits from :class:`RAdapter` to invoke the bridge R script via
    ``Rscript`` subprocess. With an :class:`RConfig` pointing to
    ``magpie_bridge.R`` and ``magpie_root`` resolving to the MAgPIE
    source tree, the adapter can run MAgPIE end-to-end. Without an
    :class:`RConfig`, ``validate_inputs``, ``translate_inputs``, and
    ``parse_outputs`` still work for dry-run pipeline testing.

    Parameters
    ----------
    config:
        Optional :class:`RConfig`. If omitted, one is auto-built using
        ``_DEFAULT_BRIDGE_SCRIPT`` if it exists.
    magpie_root:
        Path to the MAgPIE source tree (containing ``main.gms``,
        ``start.R``, ``config/``). Defaults to
        ``Models/Fertilizer/magpie-master/magpie-master`` relative to
        the project root.
    """

    def __init__(
        self,
        config: RConfig | None = None,
        magpie_root: Path | str | None = None,
    ) -> None:
        # Auto-construct an RConfig pointing at the bridge script if the
        # caller did not supply one. validate_inputs / translate_inputs
        # remain usable without R/GAMS being installed.
        if config is None and _DEFAULT_BRIDGE_SCRIPT.exists():
            config = RConfig(r_script_path=_DEFAULT_BRIDGE_SCRIPT)
        super().__init__(config)
        self._magpie_root: Path | None = (
            Path(magpie_root) if magpie_root is not None
            else _resolve_default_magpie_root()
        )

    @property
    def model_id(self) -> str:
        return "magpie"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "MAgPIE (Model of Agricultural Production and its Impact on the "
            "Environment): recursive-dynamic cost-minimization model projecting "
            "global land use, crop production, and food prices under fertilizer "
            "price shocks and water availability disruptions from Hormuz closure."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        # MAgPIE is memory-hungry and the GAMS solver benefits from
        # multiple cores on larger time-step configurations. The README
        # recommends >=16 GB RAM and a Core i7-class CPU.
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=4,
            memory_gb=16.0,
            supports_multi_threading=True,
            max_threads=4,
            prefers_process_isolation=True,
        )

    @property
    def magpie_root(self) -> Path | None:
        """Resolved path to the MAgPIE source tree, if known."""
        return self._magpie_root

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        for key in _REQUIRED_PARAMS:
            if key not in params:
                errors.append(f"Missing required parameter: '{key}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        fert_val = params["fertilizer_price_shock_pct"]
        if not isinstance(fert_val, (int, float)):
            errors.append("'fertilizer_price_shock_pct' must be numeric")
        elif fert_val < 0:
            errors.append("'fertilizer_price_shock_pct' must be >= 0")
        elif fert_val > 500:
            warnings.append(
                f"'fertilizer_price_shock_pct' = {fert_val}% is unusually large; "
                "verify against historical fertilizer price spikes"
            )

        yield_val = params["crop_yield_impact_pct"]
        if not isinstance(yield_val, (int, float)):
            errors.append("'crop_yield_impact_pct' must be numeric")
        elif yield_val < -100:
            errors.append("'crop_yield_impact_pct' cannot be less than -100%")
        elif yield_val > 0:
            warnings.append(
                "'crop_yield_impact_pct' is positive (yield increase); "
                "confirm this is intended under a crisis scenario"
            )

        water_val = params["water_availability_change_pct"]
        if not isinstance(water_val, (int, float)):
            errors.append("'water_availability_change_pct' must be numeric")
        elif water_val < -100:
            errors.append("'water_availability_change_pct' cannot be less than -100%")
        elif water_val > 0:
            warnings.append(
                "'water_availability_change_pct' is positive (more water); "
                "confirm this is intended under a crisis scenario"
            )

        ssp = params.get("ssp_scenario")
        if ssp is not None and ssp not in _VALID_SSP_SCENARIOS:
            errors.append(
                f"'ssp_scenario' must be one of {sorted(_VALID_SSP_SCENARIOS)}; "
                f"got '{ssp}'"
            )

        energy_val = params.get("energy_price_shock_pct")
        if energy_val is not None:
            if not isinstance(energy_val, (int, float)):
                errors.append("'energy_price_shock_pct' must be numeric")
            elif energy_val < 0:
                errors.append("'energy_price_shock_pct' must be >= 0")

        regions = params.get("affected_regions")
        if regions:
            if not isinstance(regions, (list, tuple)):
                errors.append("'affected_regions' must be a list of region codes")
            else:
                unknown = [r for r in regions if r not in H12_REGIONS]
                if unknown:
                    warnings.append(
                        f"'affected_regions' contains non-h12 codes {unknown}; "
                        f"valid h12 regions: {sorted(H12_REGIONS)}"
                    )

        horizon = params.get("time_horizon")
        if horizon is not None:
            horizon_str = str(horizon)
            if (
                horizon_str not in _VALID_TIMESTEPS
                and not (horizon_str.isdigit() and 1 <= int(horizon_str) <= 16)
            ):
                warnings.append(
                    f"'time_horizon' = '{horizon_str}' is not a known c_timesteps "
                    f"key; valid keys: {sorted(_VALID_TIMESTEPS)} or '1'..'16'"
                )

        # Surface integration prerequisites as warnings so the analyst sees
        # them at validation time rather than at execute() time.
        if self._config is not None:
            script = self._config.r_script_path
            if not Path(script).exists():
                warnings.append(
                    f"Bridge R script not found at '{script}'. Execute will fail."
                )
        if self._magpie_root is not None and not (self._magpie_root / "main.gms").exists():
            warnings.append(
                f"MAgPIE root '{self._magpie_root}' does not contain main.gms. "
                "Set magpie_root or the MAGPIE_ROOT environment variable."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate scenario parameters into the JSON structure expected by
        the bridge R script.

        Mapping from adapter parameters to MAgPIE cfg entries (consumed
        by ``magpie_bridge.R``):

        - ``fertilizer_price_shock_pct`` → ``cfg$gms$s38_fert_cost_multiplier``
          (custom switch, see caveat in module docstring)
        - ``crop_yield_impact_pct``      → ``cfg$gms$s14_yield_shock_factor``
        - ``water_availability_change_pct`` → ``cfg$gms$s43_water_shock_factor``
        - ``energy_price_shock_pct``     → ``cfg$gms$s40_transport_cost_multiplier``
        - ``trade_restriction_flag``     → bumps ``s21_cost_import``
        - ``ssp_scenario``               → ``c09_pop_scenario`` /
          ``c09_gdp_scenario`` / ``c09_pal_scenario``
        - ``time_horizon``               → ``c_timesteps``
        """
        scenario_id = params.get("scenario_id", "default")
        translated: dict[str, Any] = {
            "scenario_id": scenario_id,
            "title": params.get("title", f"hormuz_{scenario_id}"),
            "magpie_shocks": {
                "fertilizer_price_multiplier": (
                    1.0 + params["fertilizer_price_shock_pct"] / 100.0
                ),
                "yield_scaling_factor": (
                    1.0 + params["crop_yield_impact_pct"] / 100.0
                ),
                "water_availability_factor": (
                    1.0 + params["water_availability_change_pct"] / 100.0
                ),
            },
            "cfg_overrides": {},
        }

        ssp = params.get("ssp_scenario", "SSP2")
        translated["cfg_overrides"]["c09_pop_scenario"] = ssp
        translated["cfg_overrides"]["c09_gdp_scenario"] = ssp
        translated["cfg_overrides"]["c09_pal_scenario"] = ssp

        if params.get("trade_restriction_flag", False):
            # s21_trade_tariff is a 0/1 switch; tighten by enabling and
            # raising the cost-of-additional-imports lever (USD17MER per tDM).
            translated["cfg_overrides"]["s21_trade_tariff"] = 1
            translated["cfg_overrides"]["s21_cost_import"] = 3000

        energy_shock = params.get("energy_price_shock_pct", 0)
        if energy_shock and energy_shock > 0:
            translated["magpie_shocks"]["transport_cost_multiplier"] = (
                1.0 + energy_shock / 100.0
            )

        horizon = params.get("time_horizon")
        if horizon is not None:
            translated["cfg_overrides"]["c_timesteps"] = str(horizon)

        translated["affected_regions"] = list(params.get("affected_regions", []))

        return translated

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute MAgPIE via ``Rscript magpie_bridge.R``.

        Overrides :meth:`RAdapter._execute_subprocess` to inject the
        ``MAGPIE_ROOT`` environment variable so the bridge script can
        locate the model tree.
        """
        if self._config is None:
            raise NotImplementedError(
                "MAgPIEAdapter.execute requires an RConfig pointing to the "
                "bridge R script. Integration prerequisites:\n"
                "  1. GAMS >= 50.1.0 with CONOPT solver\n"
                "  2. R >= 4.3 with Rtools (Windows)\n"
                "  3. MAgPIE input data (auto-fetched on first start_run "
                "or via scripts/start/download_data.R)\n"
                "  4. Bridge R script at src/models/fertilizer/magpie_bridge.R\n"
                "  5. RConfig with r_script_path pointing to that bridge\n"
                "  6. magpie_root (constructor arg) or MAGPIE_ROOT env var\n"
                "See field_guide_model_integration_v2.md for detailed steps."
            )

        bridge_script = Path(self._config.r_script_path)
        if not bridge_script.exists():
            # NotImplementedError → SLURM runner classifies as SKIPPED.
            raise NotImplementedError(
                f"MAgPIE bridge R script not found at '{bridge_script}'."
            )

        if self._magpie_root is None or not (self._magpie_root / "main.gms").exists():
            tried = self._magpie_root if self._magpie_root is not None else (
                "none of " + ", ".join(str(p) for p in _DEFAULT_MAGPIE_ROOT_CANDIDATES)
            )
            raise NotImplementedError(
                "MAgPIE source tree not found. Pass magpie_root to the "
                "adapter constructor or set the MAGPIE_ROOT environment "
                f"variable. Tried: {tried}"
            )

        # Likewise treat a missing Rscript binary as a skip.
        from shutil import which
        if which(self._config.r_executable) is None:
            raise NotImplementedError(
                f"MAgPIE adapter requires the '{self._config.r_executable}' binary on PATH "
                "(R >= 4.3). Install R and retry."
            )

        return self._run_bridge_subprocess(inputs)

    def _run_bridge_subprocess(self, inputs: dict[str, Any]) -> ModelOutput:
        """Subprocess invocation that adds MAGPIE_ROOT to the env."""
        config = self.r_config

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(inputs, f, default=str)
            input_path = f.name

        try:
            cmd = [config.r_executable, "--vanilla", *config.extra_args,
                   str(config.r_script_path), input_path]

            if config.srun_enabled:
                cmd = ["srun", *config.srun_args, *cmd]

            env = {**os.environ}
            if config.r_libs_path:
                env["R_LIBS_USER"] = str(config.r_libs_path)
            if self._magpie_root is not None:
                env["MAGPIE_ROOT"] = str(self._magpie_root.resolve())

            threads = str(config.num_threads)
            env["OMP_NUM_THREADS"] = threads
            env["MKL_NUM_THREADS"] = threads
            env["OPENBLAS_NUM_THREADS"] = threads

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                env=env,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"MAgPIE bridge failed (rc={result.returncode}): "
                    f"{result.stderr[-1000:] if result.stderr else 'no stderr'}"
                )

            try:
                raw = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "MAgPIE bridge did not return JSON on stdout. "
                    f"stderr tail: {result.stderr[-500:] if result.stderr else ''}"
                ) from exc

            return self.parse_outputs(raw)

        finally:
            os.unlink(input_path)

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse MAgPIE bridge output into a standardized :class:`ModelOutput`.

        The bridge R script returns a JSON dict with keys:
            - production: agricultural production by crop group (Mt/yr)
            - prices: food/commodity prices ($/t)
            - land_use: land cover by type (Mha)
            - emissions: GHG emissions from land use (Mt CO2eq/yr)
            - water_use: agricultural water use (km^3/yr)
            - fertilizer_use: nitrogen fertilizer use (Mt N/yr)
            - convergence: 'completed' | 'failed' | 'unknown'
            - error / traceback: present only on failure
        """
        if isinstance(raw, ModelOutput):
            return raw

        outputs = raw if isinstance(raw, dict) else {"raw": raw}

        convergence: str | None = None
        diagnostics: dict[str, Any] = {}
        if isinstance(raw, dict):
            convergence = raw.pop("convergence", None)
            for diag_key in ("error", "traceback", "fertilizer_use_error",
                             "warnings", "log_tail"):
                if diag_key in raw:
                    diagnostics[diag_key] = raw.pop(diag_key)

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status=convergence,
            diagnostics=diagnostics,
            metadata={
                "unit_notes": {
                    "production": "Mt/yr (million tonnes per year)",
                    "prices": "$/t (US dollars per tonne)",
                    "land_use": "Mha (million hectares)",
                    "water_use": "km^3/yr",
                    "fertilizer_use": "Mt N/yr",
                    "emissions": "Mt CO2eq/yr",
                },
                "source": "MAgPIE via magpie_bridge.R",
                "magpie_root": (
                    str(self._magpie_root) if self._magpie_root else None
                ),
            },
        )
