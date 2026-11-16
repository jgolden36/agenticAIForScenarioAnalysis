"""APSIM-GTAP coupled model adapter (AgResilience).

Couples the AgResilience Julia GTAPv7 model (levels form, JuMP/Ipopt;
18 regions x 8 sectors, investment closure ``rdlt``) with the AgResilience
APSIM maize emulator (PyTorch MLP trained on 1M APSIM runs, held-out
R^2 = 0.997) through an iterated fixed point:

    Hormuz shock -> GTAP -> US chemicals consumption change
                 -> field nitrogen (coupling.consumption_to_nitrogen)
                 -> emulator maize yield ratio
                 -> GTAP grain productivity (production_shock gro/usa)
                 -> re-solve ... until the yield ratio stops changing.

The Hormuz shock enters GTAP as (all annualised by min(duration/12, 1),
because GTAP is an annual comparative-static model):

* output loss in the Gulf chemicals sector: ``production_shock chm/wasia``
  x (1 - middle_east_fertilizer_production_loss_pct/100 x chm_fertilizer_weight);
* output loss in the Gulf extraction sector: ``production_shock extract/wasia``
  x (1 - gulf_oil_supply_loss_mbd / wasia_baseline_oil_mbd);
* optional import wedge on Gulf chemicals and extraction exports to every
  other region: ``tms`` x [1 + (trade_cost_multiplier - 1) x freight share].

``wasia`` is the GTAP West Asia composite (GTAP regions 99-116), which holds
the Gulf producers.

Real integration requirements (all on the cluster in ~/Agresiliency):
    * AgResilience checkout (branch ``experiments-and-slurm-setup``) with
      ``src/tools/gtap_server.jl`` and ``src/tools/saved_artifacts/``
      (emulator checkpoint and scalers)
    * the ``agres`` conda env (torch, requests) and Julia via juliaup with
      the packages from ``slurm/jobs/setup_julia_deps.jl``
    * licensed GTAP data (``src/tools/Data/gsdf*.har``) and the repaired
      calibration ``results/shock_repair/calibration/calibrated_mc2.jld``
      (calibration id ``shock-repair-v2``)
    * ``configs/model_configs/apsim_gtap.yaml`` (see the ``.example``)

Without a config, ``execute`` raises ``NotImplementedError`` and the
executor records the cell as SKIPPED.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.subprocess_adapter import SubprocessAdapter, SubprocessConfig
from src.models.base import (
    ModelOutput,
    ResourceRequirements,
    UncertaintyReport,
    ValidationResult,
)

DRIVER_PATH = Path(__file__).resolve().parent / "apsim_gtap_driver.py"

# Solver settings of the AgResilience shock-repair / full-suite jobs
# (slurm/jobs/16_direct_suite.sbatch, results/shock_repair/run_status.json).
AGRES_SOLVER_ENV: dict[str, str] = {
    "GTAP_LOG_NEWTON": "1",
    "GTAP_HESSIAN_APPROXIMATION": "limited-memory",
    "GTAP_MU_STRATEGY": "monotone",
    "GTAP_MU_INIT": "1e-12",
    "GTAP_MAX_ITER": "2000",
    "GTAP_MAX_CPU_TIME": "3600",
    "OPENBLAS_NUM_THREADS": "1",
}

_REQUIRED_PARAMS = [
    "middle_east_fertilizer_production_loss_pct",
    "gulf_oil_supply_loss_mbd",
    "trade_cost_multiplier",
    "disruption_duration_months",
]

# Headline output keys (also used by templated synthesis and robustness checks).
HEADLINE_OUTPUTS = [
    "us_gdp_pct",
    "gulf_gdp_pct",
    "us_maize_yield_change_pct",
    "us_gro_price_pct",
    "us_chm_consumption_pct",
]


class APSIMGTAPConfig(BaseModel):
    """Paths and coupling constants for the AgResilience APSIM-GTAP model."""

    agres_root: Path = Field(description="AgResilience checkout (working directory of the driver)")
    python_executable: str = Field(default="python", description="Python of the agres env")
    julia_executable: str = Field(default="julia")
    gtap_calib_file: Path | None = Field(default=None, description="GTAP_CALIB_FILE for gtap_server.jl")
    calib_id: str = Field(default="shock-repair-v2", description="AGRES_CALIB_ID (cache namespace)")
    cache_dir: Path | None = Field(default=None, description="AGRES_CACHE_DIR; GTAP solves are cached under <dir>/gtap")
    run_dir_base: Path | None = None
    wasia_baseline_oil_mbd: float = Field(
        default=28.0,
        description=(
            "Pre-crisis liquids production of the GTAP West Asia composite (mb/d), "
            "used to turn gulf_oil_supply_loss_mbd into an output-loss share"
        ),
    )
    freight_share_of_import_value: float = Field(
        default=0.08,
        description="Share of freight in the landed value of Gulf chm/extract imports (scales the tms wedge)",
    )
    chm_fertilizer_weight: float = Field(
        default=1.0,
        description="Fraction of the fertilizer production loss applied to the whole wasia chm sector",
    )
    apply_trade_wedge: bool = True
    max_output_loss_share: float = 0.95
    timeout_seconds: int = 7200
    server_startup_timeout_s: int = 1800
    extra_env: dict[str, str] = Field(default_factory=dict)
    server_env: dict[str, str] = Field(
        default_factory=lambda: dict(AGRES_SOLVER_ENV),
        description="Environment of gtap_server.jl (Ipopt settings the shock-repair-v2 calibration was validated with)",
    )

    def to_subprocess_config(self) -> SubprocessConfig:
        cmd = (
            f'"{self.python_executable}" "{DRIVER_PATH.as_posix()}" '
            '--in "{input_path}" --out "{output_path}"'
        )
        kwargs: dict[str, Any] = {
            "command_template": cmd,
            "working_directory": self.agres_root,
            "timeout_seconds": self.timeout_seconds,
            "extra_env": dict(self.extra_env),
            "num_threads": 4,
        }
        if self.run_dir_base is not None:
            kwargs["run_dir_base"] = self.run_dir_base
        return SubprocessConfig(**kwargs)


def annualisation_factor(duration_months: float) -> float:
    """Share of a year the disruption lasts (GTAP solves are annual)."""
    return max(0.0, min(float(duration_months) / 12.0, 1.0))


def compute_shocks(params: dict[str, Any], cfg: APSIMGTAPConfig) -> dict[str, Any]:
    """Annualised GTAP shock magnitudes from the pipeline parameters."""
    scale = annualisation_factor(params["disruption_duration_months"])
    cap = cfg.max_output_loss_share
    fert = float(params["middle_east_fertilizer_production_loss_pct"]) / 100.0
    chm_share = min(max(fert * cfg.chm_fertilizer_weight, 0.0), cap) * scale
    oil_share = 0.0
    if cfg.wasia_baseline_oil_mbd > 0:
        oil_share = min(max(float(params["gulf_oil_supply_loss_mbd"]) / cfg.wasia_baseline_oil_mbd, 0.0), cap) * scale
    wedge = 1.0
    if cfg.apply_trade_wedge:
        mult = float(params["trade_cost_multiplier"])
        wedge = 1.0 + max(mult - 1.0, 0.0) * cfg.freight_share_of_import_value * scale
    return {
        "gulf_region": "wasia",
        "annualisation_factor": scale,
        "chm_output_loss_share": round(chm_share, 8),
        "extract_output_loss_share": round(oil_share, 8),
        "trade_wedge": round(wedge, 8),
    }


class APSIMGTAPAdapter(SubprocessAdapter):
    """Coupled AgResilience GTAPv7 + APSIM maize emulator (fixed point)."""

    def __init__(self, config: APSIMGTAPConfig | None = None) -> None:
        self._agres_config = config
        super().__init__(config.to_subprocess_config() if config is not None else None)

    @property
    def model_id(self) -> str:
        return "apsim_gtap"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.FERTILIZER_AGRICULTURE

    @property
    def analytical_level(self) -> AnalyticalLevel:
        # Macro tier: runs after every commodity and commodity-downstream
        # model, so trade_cost_multiplier can be forwarded from aisdb.
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "APSIM-GTAP (AgResilience): Julia GTAPv7 global CGE (18 regions x 8 sectors) "
            "coupled to an APSIM maize emulator through a GTAP<->crop fixed point. Gulf "
            "chemicals and extraction output losses plus a rerouting trade wedge give "
            "regional GDP, grain/food/chemical prices and the US maize yield response."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=4,
            memory_gb=16.0,
            supports_multi_threading=True,
            max_threads=4,
            prefers_process_isolation=True,
        )

    @property
    def agres_config(self) -> APSIMGTAPConfig | None:
        return self._agres_config

    # ------------------------------------------------------------ validation

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        for key in _REQUIRED_PARAMS:
            if key not in params or params[key] is None:
                errors.append(f"Missing required parameter: '{key}'")

        def num(key: str) -> float | None:
            if key not in params or params[key] is None:
                return None
            val = params[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                errors.append(f"'{key}' must be numeric, got {val!r}")
                return None
            return float(val)

        fert = num("middle_east_fertilizer_production_loss_pct")
        if fert is not None and not 0.0 <= fert <= 100.0:
            errors.append(f"'middle_east_fertilizer_production_loss_pct' = {fert} must be in [0, 100]")
        oil = num("gulf_oil_supply_loss_mbd")
        if oil is not None:
            if oil < 0:
                errors.append(f"'gulf_oil_supply_loss_mbd' = {oil} must be >= 0")
            elif oil > 30:
                errors.append(f"'gulf_oil_supply_loss_mbd' = {oil} exceeds total Gulf liquids output (~30 mb/d)")
        mult = num("trade_cost_multiplier")
        if mult is not None:
            if mult < 1.0:
                errors.append(f"'trade_cost_multiplier' = {mult} must be >= 1.0 (1.0 = no rerouting)")
            elif mult > 4.0:
                warnings.append(f"'trade_cost_multiplier' = {mult} is above the Cape-route range (1.4-1.8x)")
        dur = num("disruption_duration_months")
        if dur is not None:
            if dur <= 0:
                errors.append(f"'disruption_duration_months' = {dur} must be > 0")
            elif dur > 12:
                warnings.append(
                    f"'disruption_duration_months' = {dur} > 12: GTAP is annual, the shock is capped at one full year"
                )
        eps = num("coupling_elasticity") if "coupling_elasticity" in params else None
        if eps is not None and not 0.0 <= eps <= 3.0:
            errors.append(f"'coupling_elasticity' = {eps} must be in [0, 3]")
        if "max_fixed_point_iter" in params:
            it = params["max_fixed_point_iter"]
            if not isinstance(it, int) or isinstance(it, bool) or not 1 <= it <= 50:
                errors.append(f"'max_fixed_point_iter' = {it!r} must be an integer in [1, 50]")
        edits = params.get("gtap_parameter_edits")
        if edits is not None and not isinstance(edits, list):
            errors.append("'gtap_parameter_edits' must be a list of {name, indices, operation, value}")
        return ValidationResult(valid=not errors, errors=errors, warnings=warnings)

    # ------------------------------------------------------------ translation

    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        cfg = self._agres_config or APSIMGTAPConfig(agres_root=Path("."))
        payload: dict[str, Any] = {
            "scenario_id": params.get("scenario_id", "default"),
            "shocks": compute_shocks(params, cfg),
            "coupling_elasticity": float(params.get("coupling_elasticity", 1.0)),
            "max_fixed_point_iter": int(params.get("max_fixed_point_iter", 12)),
            "inputs_echo": {k: params.get(k) for k in _REQUIRED_PARAMS},
            "config": {
                "agres_root": str(cfg.agres_root),
                "julia_executable": cfg.julia_executable,
                "gtap_calib_file": str(cfg.gtap_calib_file) if cfg.gtap_calib_file else None,
                "calib_id": cfg.calib_id,
                "cache_dir": str(cfg.cache_dir) if cfg.cache_dir else None,
                "server_startup_timeout_s": cfg.server_startup_timeout_s,
                "server_env": dict(cfg.server_env),
            },
        }
        if params.get("gtap_parameter_edits"):
            payload["gtap_parameter_edits"] = params["gtap_parameter_edits"]
        return payload

    # ------------------------------------------------------------ execution

    def execute(self, inputs: Any) -> ModelOutput:
        if self._agres_config is None:
            raise NotImplementedError(
                "apsim_gtap needs configs/model_configs/apsim_gtap.yaml pointing at an "
                "AgResilience checkout (agres_root) with the GTAP calibration "
                "(gtap_calib_file, licensed GTAP data), the APSIM emulator artifacts "
                "(src/tools/saved_artifacts/), the agres Python env and Julia. "
                "See configs/model_configs/apsim_gtap.yaml.example."
            )
        root = Path(self._agres_config.agres_root)
        if not (root / "src" / "tools" / "gtap_server.jl").exists():
            raise FileNotFoundError(f"apsim_gtap: {root}/src/tools/gtap_server.jl not found")
        return super().execute(inputs)

    def parse_outputs(self, raw: Any) -> ModelOutput:
        outputs = dict(raw) if isinstance(raw, dict) else {"raw": raw}
        converged = bool(outputs.get("converged"))
        gate = outputs.get("zero_shock_gate_passed")
        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            metadata={"mode": "julia", "engine": "julia", "coupling": "gtap_apsim_fixed_point"},
            convergence_status="converged" if converged else "not_converged",
            diagnostics={
                "fixed_point_iterations": outputs.get("fixed_point_iterations"),
                "zero_shock_residual_gdp_pct": outputs.get("zero_shock_residual_gdp_pct"),
                "zero_shock_gate_passed": gate,
                "open_loop_gap": outputs.get("open_loop_gap"),
            },
            # Each perturbation replicate would be a full coupled GTAP solve;
            # parametric uncertainty is covered by the Armington-elasticity
            # LHS job (slurm/jobs/apsim_gtap_ssa.sbatch) instead.
            uncertainty=UncertaintyReport(
                method="none",
                notes=(
                    "Input perturbation disabled for apsim_gtap; see the Armington "
                    "elasticity Latin-hypercube (apsim_gtap_ssa) for parametric bands."
                ),
            ),
        )


def config_from_mapping(raw: dict[str, Any] | None) -> APSIMGTAPConfig | None:
    """Build a config from YAML values, with HORMUZ_APSIM_GTAP_* env overrides."""
    raw = dict(raw or {})
    env_map = {
        "agres_root": "HORMUZ_APSIM_GTAP_ROOT",
        "python_executable": "HORMUZ_APSIM_GTAP_PYTHON",
        "julia_executable": "HORMUZ_APSIM_GTAP_JULIA",
        "gtap_calib_file": "HORMUZ_APSIM_GTAP_CALIB_FILE",
        "cache_dir": "HORMUZ_APSIM_GTAP_CACHE_DIR",
    }
    for key, env in env_map.items():
        if os.environ.get(env):
            raw[key] = os.environ[env]
    if not raw.get("agres_root"):
        return None
    allowed = set(APSIMGTAPConfig.model_fields)
    kwargs = {k: v for k, v in raw.items() if k in allowed and v is not None}
    for key in ("agres_root", "gtap_calib_file", "cache_dir", "run_dir_base"):
        if kwargs.get(key):
            kwargs[key] = Path(os.path.expanduser(str(kwargs[key])))
    for key in ("python_executable", "julia_executable"):
        if kwargs.get(key):
            kwargs[key] = os.path.expanduser(str(kwargs[key]))
    return APSIMGTAPConfig(**kwargs)
