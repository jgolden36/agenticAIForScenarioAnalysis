"""OpenCGEAdapter — PSL OG-Core / OG-USA computable general equilibrium driver.

OpenCGE in this pipeline is bound to the Policy Simulation Library's
**OG-Core / OG-USA** dynamic overlapping-generations CGE framework
(https://github.com/PSLmodels/OG-Core, https://github.com/PSLmodels/OG-USA).
OG-Core/OG-USA exposes a steady-state (`SS`) and transition-path (`TPI`)
solver via the ``ogcore.execute.runner`` entry point and consumes a
``Specifications`` parameter object that can be patched with reform
dictionaries.

OG-Core has no commodity sectors out of the box: it operates on aggregate
production with optional multi-industry extensions. Pipeline commodity
shocks are therefore mapped to **exogenous productivity (``Z``) and
capital-quality (economic depreciation ``delta_annual``) adjustments** via a config-driven
``shock_to_productivity`` table. The mapping table is loaded from
``configs/model_configs/opencge.yaml`` so analysts can tune the elasticity
of macro outcomes to commodity-tier shocks without code changes.

Real implementation requirements:
- ``ogcore`` and ``ogusa`` Python packages (``pip install ogcore ogusa``)
- A baseline OG-USA calibration directory (``ogusa_data_dir``)
- A ``dask.distributed`` client for parallel TPI iterations
- Writable baseline / reform output directories
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import (
    ModelAdapter,
    ModelOutput,
    ResourceRequirements,
    ValidationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class OpenCGEConfig(BaseModel):
    """Configuration for the OpenCGE / OG-Core driver."""

    ogusa_data_dir: Path | None = Field(
        default=None,
        description=(
            "Directory containing OG-USA baseline calibration data "
            "(microsimulation puf-derived parameters, demographic data, etc.)."
        ),
    )
    baseline_dir: Path = Field(
        default=Path("data/opencge/baseline"),
        description="Directory for OG-Core baseline (no-reform) outputs",
    )
    reform_dir: Path = Field(
        default=Path("data/opencge/reform"),
        description="Directory for OG-Core reform (scenario) outputs",
    )
    num_workers: int = Field(
        default=4,
        description="Dask workers for parallel TPI iteration",
    )
    time_path_iter: int = Field(
        default=200,
        description="Maximum TPI iterations (OG-Core default ~200)",
    )
    solution_method: Literal["TPI", "SS"] = Field(
        default="TPI",
        description="'TPI' for full transition path, 'SS' for steady-state only",
    )
    closure_rule: Literal["full_employment", "fixed_capital"] = Field(
        default="full_employment",
        description="Macro closure assumption",
    )
    baseline_year: int = Field(
        default=2026,
        description="First year of the simulation (start_year in OG-Core)",
    )
    budget_balance: bool = Field(
        default=False,
        description=(
            "Force government budget balance (closes via lump-sum transfers). "
            "Default False = use OG-USA baseline fiscal closure."
        ),
    )
    # Mapping table: commodity name -> (Z multiplier per 1% price shock,
    # delta_tau multiplier per 1% price shock). Loaded from YAML so analysts
    # can recalibrate without editing code.
    shock_to_productivity: dict[str, dict[str, float]] = Field(
        default_factory=lambda: {
            "oil": {"Z_mult_per_pct": -0.0008, "delta_tau_per_pct": 0.00005},
            "lng": {"Z_mult_per_pct": -0.0004, "delta_tau_per_pct": 0.00002},
            "fertilizer": {"Z_mult_per_pct": -0.0002, "delta_tau_per_pct": 0.00001},
            "helium": {"Z_mult_per_pct": -0.0001, "delta_tau_per_pct": 0.000005},
            # Water enters the macro layer ONLY under the prescribed
            # infrastructure_collapse scenario (per the rule in
            # configs/upstream_to_macro_mapping.yaml). Calibration is
            # deliberately larger in magnitude than oil because, in the
            # short run, water has near-zero substitutability for the
            # affected sectors (households, agriculture, refining,
            # power-plant cooling). The "shock" channel here is the
            # CWatM unmet-demand percentage rather than a price; we
            # treat it as a quantity-equivalent productivity hit on
            # aggregate Z and a small additional capital-quality drag
            # standing in for damage to water-distribution
            # infrastructure that depreciates the productive capital
            # stock.
            "water": {"Z_mult_per_pct": -0.0012, "delta_tau_per_pct": 0.00008},
        },
        description=(
            "Per-commodity sensitivity coefficients translating a 1% commodity "
            "price (or, for 'water', unmet-demand) shock into multiplicative "
            "adjustments on aggregate productivity (Z) and capital-quality "
            "(economic depreciation delta_annual; the key name "
            "delta_tau_per_pct is historical)."
        ),
    )
    capital_drag_scenarios: list[str] | None = Field(
        default=None,
        description=(
            "Scenario ids under which the capital-quality drag (delta_annual) "
            "is applied. OG-Core's delta_annual is one scalar for every year, "
            "so the drag is permanent and lowers the long-run steady state; "
            "it suits lasting infrastructure damage, not a temporary closure. "
            "None applies it in every scenario; a list restricts it (the "
            "shipped opencge.yaml uses [infrastructure_collapse])."
        ),
    )
    skip_baseline_if_present: bool = Field(
        default=True,
        description=(
            "If True, skip the baseline run when a SS_vars.pkl is already "
            "present in baseline_dir. Saves ~hours per scenario."
        ),
    )
    timeout_seconds: int = Field(
        default=14400,
        description="Per-run timeout (default 4 hours)",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Parameters that must be present for OpenCGE to run
REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "commodity_price_shocks",
        "disruption_duration_months",
    }
)


def _coerce_commodity_shocks(value: Any) -> dict[str, float] | None:
    """Best-effort flattening of common LLM-emitted shapes for ``commodity_price_shocks``.

    The model spec asks the LLM for ``dict[str, number]`` (e.g.
    ``{"lng": 40.0}``), but smaller LLMs sometimes emit
    ``{"lng": {"shock": 40, "unit": "percent"}}``. This helper accepts
    either shape and normalises to ``{commodity: float}``. Returns
    ``None`` if the input isn't a dict at all (caller surfaces a clearer
    error in that case).
    """
    if not isinstance(value, dict):
        return None
    flat: dict[str, float] = {}
    for k, v in value.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            flat[str(k)] = float(v)
            continue
        if isinstance(v, dict):
            inner = v.get("shock", v.get("value", v.get("pct", v.get("percent"))))
            if isinstance(inner, (int, float)) and not isinstance(inner, bool):
                flat[str(k)] = float(inner)
                continue
        if isinstance(v, str):
            try:
                flat[str(k)] = float(v.strip().rstrip("%"))
            except ValueError:
                continue
    return flat


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OpenCGEAdapter(ModelAdapter):
    """Adapter binding OpenCGE to PSL OG-Core / OG-USA.

    Translates pipeline commodity price shocks into OG-Core
    ``Specifications`` overrides (productivity ``Z`` and capital quality
    ``delta_tau_annual``), runs the steady-state and transition-path
    solvers via ``ogcore.execute.runner``, and standardizes welfare and
    macro-aggregate outputs for the synthesis layer.
    """

    def __init__(self, config: OpenCGEConfig | None = None) -> None:
        self._config = config or OpenCGEConfig()

    @property
    def model_id(self) -> str:
        return "opencge"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "OpenCGE (PSL OG-Core / OG-USA): dynamic overlapping-generations "
            "computable general equilibrium model. Pipeline commodity price "
            "shocks are translated into exogenous productivity and capital-"
            "quality adjustments; the OG-Core SS+TPI solver returns welfare "
            "(EV by lifetime-income group), GDP path, factor prices, and "
            "consumption path for cross-validation against PyCGE and MIRAGRODEP."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=self._config.num_workers,
            memory_gb=16.0,
            supports_multi_threading=True,
            max_threads=self._config.num_workers,
            prefers_process_isolation=True,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate OpenCGE input parameters.

        Checks required parameters are present and numeric, and that the
        commodity_price_shocks dict only references commodities that are
        present in the shock_to_productivity mapping table.
        """
        errors: list[str] = []
        warnings: list[str] = []

        missing = REQUIRED_PARAMS - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Defensive coercion: smaller LLMs sometimes wrap each shock in
        # {shock, unit} instead of emitting a bare number. Normalise to
        # dict[str, float] in place so the rest of validation and
        # translate_inputs see the canonical shape.
        coerced = _coerce_commodity_shocks(params.get("commodity_price_shocks"))
        if coerced is not None and coerced != params.get("commodity_price_shocks"):
            params["commodity_price_shocks"] = coerced
            warnings.append(
                "'commodity_price_shocks' was normalised from an LLM-emitted "
                "nested shape to a flat dict[str, number]."
            )

        oil_shock = params["oil_price_shock_pct"]
        if not isinstance(oil_shock, (int, float)):
            errors.append(
                f"'oil_price_shock_pct' must be numeric; got {type(oil_shock).__name__}"
            )
        elif oil_shock < -100.0:
            errors.append(
                f"'oil_price_shock_pct' cannot be less than -100%; got {oil_shock}"
            )
        elif oil_shock > 500.0:
            warnings.append(
                f"'oil_price_shock_pct' is {oil_shock}%, implying more than a 5x price "
                "increase. Verify consistency with commodity-level oil model outputs."
            )

        price_shocks = params["commodity_price_shocks"]
        if not isinstance(price_shocks, dict) or len(price_shocks) == 0:
            errors.append(
                "'commodity_price_shocks' must be a non-empty dict mapping commodity "
                "names to percentage price shocks (e.g., {'lng': 40.0, 'fertilizer': 25.0})"
            )
        else:
            mapping = self._config.shock_to_productivity
            for commodity, shock in price_shocks.items():
                if not isinstance(shock, (int, float)):
                    errors.append(
                        f"'commodity_price_shocks[{commodity!r}]' must be numeric; "
                        f"got {type(shock).__name__}"
                    )
                    continue
                if shock < -100.0:
                    errors.append(
                        f"'commodity_price_shocks[{commodity!r}]' cannot be less than "
                        f"-100%; got {shock}"
                    )
                if commodity not in mapping:
                    warnings.append(
                        f"'commodity_price_shocks' includes '{commodity}' which is "
                        f"not in shock_to_productivity mapping (known: "
                        f"{sorted(mapping)}); shock will be ignored."
                    )

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

        # Surface integration prerequisites as warnings
        if self._config.ogusa_data_dir is None:
            warnings.append(
                "OpenCGEConfig.ogusa_data_dir is not set; execute() will rely on "
                "OG-USA's bundled defaults (may be slow on first run)."
            )
        elif not Path(self._config.ogusa_data_dir).exists():
            warnings.append(
                f"OpenCGEConfig.ogusa_data_dir does not exist: "
                f"{self._config.ogusa_data_dir}"
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate pipeline shocks into an OG-Core ``Specifications`` reform dict.

        Aggregates the commodity-level price shocks (including
        ``oil_price_shock_pct``) into a single (Z multiplier, delta_tau
        adjustment) pair using ``shock_to_productivity``.

        Returns a dict with:
            scenario_id: str
            reform_dict: kwargs for OG-Core Specifications.update_specifications
            duration_years: float (disruption_duration_months / 12)
            baseline_dir / reform_dir: resolved Path strings
        """
        scenario_id = params.get("scenario_id", "default")
        mapping = self._config.shock_to_productivity

        # Build a unified shock dict (commodity_price_shocks + oil_price_shock_pct).
        all_shocks: dict[str, float] = {
            **{k: float(v) for k, v in params["commodity_price_shocks"].items()
               if isinstance(v, (int, float))},
        }
        # oil_price_shock_pct overrides any "oil" entry in commodity_price_shocks
        all_shocks["oil"] = float(params["oil_price_shock_pct"])

        # Aggregate productivity / capital-quality adjustments.
        # ``delta_tau_per_pct`` is the historical config key name; the
        # adjustment is applied to OG-Core's *economic* depreciation rate
        # ``delta_annual`` (a capital-quality drag), not to the tax
        # depreciation rate ``delta_tau_annual``. ``delta_per_pct`` is
        # accepted as the clearer alias.
        z_mult = 1.0
        delta_adj = 0.0
        applied: dict[str, dict[str, float]] = {}
        for commodity, shock_pct in all_shocks.items():
            coeffs = mapping.get(commodity)
            if coeffs is None:
                continue
            z_delta = coeffs.get("Z_mult_per_pct", 0.0) * shock_pct
            d_coef = coeffs.get("delta_per_pct", coeffs.get("delta_tau_per_pct", 0.0))
            d_delta = d_coef * shock_pct
            z_mult *= (1.0 + z_delta)
            delta_adj += d_delta
            applied[commodity] = {
                "shock_pct": shock_pct,
                "Z_delta": z_delta,
                "delta_annual_delta": d_delta,
            }

        # delta_annual is a scalar in OG-Core, so any drag is permanent:
        # apply it only in scenarios configured as lasting capital damage.
        drag_scenarios = self._config.capital_drag_scenarios
        capital_drag_applied = drag_scenarios is None or scenario_id in drag_scenarios
        if not capital_drag_applied:
            delta_adj = 0.0
            for rec in applied.values():
                rec["delta_annual_delta"] = 0.0

        duration_years = float(params["disruption_duration_months"]) / 12.0

        # Construct an OG-Core reform dict. Keys match OG-Core's
        # Specifications parameter names (ogcore default_parameters.json):
        #   Z         float, number_dims 2 -> [[year0_ind0, ...], [year1...], ...]
        #             (years x M industries, M=1 by default; OG-Core extends a
        #             short list with its last row).
        #   maxiter   int, max TPI iterations.
        # ``delta_annual`` (a scalar) is filled in at execute() time as
        # baseline value + delta_adj, because the baseline value comes from
        # the Specifications object.
        if duration_years < 25:
            z_path = [[z] for z in self._duration_weighted_z(z_mult, duration_years)]
            z_path += [[1.0]] * (25 - len(z_path))
        else:
            z_path = [[z_mult]]
        reform_dict: dict[str, Any] = {
            "Z": z_path,
            "start_year": self._config.baseline_year,
            "budget_balance": self._config.budget_balance,
            "maxiter": int(self._config.time_path_iter),
        }

        # Reform solves are keyed by run id when one is set, so two runs
        # (e.g. the two supplementary runs) do not overwrite each other's
        # OG-Core pickles. The baseline is shared: it carries no shock.
        import os

        run_id = os.environ.get("HORMUZ_RUN_ID")
        reform_base = self._config.reform_dir / run_id if run_id else self._config.reform_dir
        return {
            "scenario_id": scenario_id,
            "reform_dict": reform_dict,
            "delta_annual_adj": delta_adj,
            "capital_drag_applied": capital_drag_applied,
            "duration_years": duration_years,
            "applied_shocks": applied,
            "baseline_dir": str(self._config.baseline_dir),
            "reform_dir": str(reform_base / scenario_id),
        }

    @staticmethod
    def _duration_weighted_z(z_mult: float, duration_years: float) -> list[float]:
        """Annual Z values for a disruption lasting ``duration_years``.

        OG-Core is annual, so each model year gets the shock weighted by the
        fraction of that year the disruption lasts: full years carry
        ``z_mult``, the final partial year ``1 + (z_mult - 1) * fraction``.
        A 5-month disruption is therefore a 5/12-weighted year-1 shock, not
        a full year at full strength (runs before 2026-11-13 rounded the
        window up to one full year). Returns at least one value.
        """
        d = max(0.0, float(duration_years))
        full = int(d)
        frac = d - full
        path = [float(z_mult)] * full
        if frac > 1e-9 or not path:
            path.append(1.0 + (float(z_mult) - 1.0) * frac)
        return path

    @staticmethod
    def _delta_annual_update(base: float, adj: float) -> float:
        """Baseline economic depreciation plus the shock drag, kept in [0, 1]."""
        return float(min(1.0, max(0.0, float(base) + float(adj))))

    _SHARED_SETTINGS: tuple[str, ...] = ("start_year", "budget_balance", "maxiter")
    _BASELINE_STAMP = "pipeline_baseline_settings.json"
    _BASELINE_MARKER = "BASELINE_SOLVE_IN_PROGRESS.json"

    @classmethod
    def _write_baseline_marker(cls, baseline_dir: Path) -> None:
        import json
        import socket

        (baseline_dir / cls._BASELINE_MARKER).write_text(json.dumps({
            "job_id": os.environ.get("SLURM_JOB_ID"),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "started": time.time(),
        }), encoding="utf-8")

    @classmethod
    def _live_baseline_marker(cls, baseline_dir: Path, max_age_s: float = 48 * 3600) -> str | None:
        """Describe the job solving ``baseline_dir`` if it is still alive, else None.

        A marker naming a Slurm job is live while ``squeue`` lists that job;
        otherwise a marker from this host is live while its pid exists. A
        marker older than ``max_age_s`` is treated as stale.
        """
        import json
        import socket
        import subprocess

        path = baseline_dir / cls._BASELINE_MARKER
        if not path.exists():
            return None
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() - float(m.get("started") or path.stat().st_mtime) > max_age_s:
            return None
        job = m.get("job_id")
        if job and str(job) != os.environ.get("SLURM_JOB_ID"):
            try:
                out = subprocess.run(["squeue", "-h", "-j", str(job), "-o", "%T"],
                                     capture_output=True, text=True, timeout=30).stdout.strip()
            except (OSError, subprocess.SubprocessError):
                return f"slurm job {job} (squeue unavailable; assuming live)"
            return f"slurm job {job} {out}" if out else None
        pid = m.get("pid")
        if pid and m.get("host") == socket.gethostname() and int(pid) != os.getpid():
            if os.name == "nt":  # os.kill(pid, 0) terminates the process on Windows
                return f"pid {pid} on {m.get('host')}"
            try:
                os.kill(int(pid), 0)
            except OSError:
                return None
            return f"pid {pid} on {m.get('host')}"
        return None

    @classmethod
    def _write_baseline_stamp(cls, baseline_dir: Path, shared: dict[str, Any]) -> None:
        import json

        (baseline_dir / cls._BASELINE_STAMP).write_text(
            json.dumps(shared, sort_keys=True), encoding="utf-8"
        )

    @classmethod
    def _baseline_complete(
        cls,
        baseline_dir: Path,
        solution_method: str,
        shared: dict[str, Any] | None = None,
    ) -> bool:
        """True when the cached baseline has every file the reform needs.

        A TPI reform needs the baseline transition path as well as the
        steady state; the earlier check looked only for ``SS_vars.pkl``,
        so a baseline cached from an SS-only run silently produced no
        GDP / wage / consumption paths. When ``shared`` settings are
        given, the baseline must also carry a stamp written with the same
        settings (a cache solved with different settings is re-solved).
        """
        import json

        if not (baseline_dir / "SS" / "SS_vars.pkl").exists():
            return False
        if solution_method == "TPI" and not (baseline_dir / "TPI" / "TPI_vars.pkl").exists():
            return False
        if shared is not None:
            stamp = baseline_dir / cls._BASELINE_STAMP
            if not stamp.exists():
                return False
            try:
                return json.loads(stamp.read_text(encoding="utf-8")) == json.loads(
                    json.dumps(shared, sort_keys=True)
                )
            except (OSError, ValueError):
                return False
        return True

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Run OG-Core baseline (if needed) and reform via ``ogcore.execute.runner``.

        Heavy lifting:
        1. Build a ``Specifications`` object via OG-USA's calibration loader.
        2. Run baseline if no SS_vars.pkl exists in baseline_dir.
        3. Patch baseline Specifications with reform_dict and run reform.
        4. Read ``SS_vars.pkl`` and ``TPI_vars.pkl`` from reform_dir.
        5. Compute pct-change-from-baseline for headline aggregates.
        """
        try:
            from ogcore.execute import runner
            from ogcore.parameters import Specifications
        except ImportError as exc:
            raise ImportError(
                "OpenCGEAdapter.execute() requires the 'ogcore' package. "
                "Install with: pip install ogcore ogusa dask[distributed]\n"
                "See https://github.com/PSLmodels/OG-Core for details."
            ) from exc

        try:
            from dask.distributed import Client, LocalCluster
        except ImportError as exc:
            raise ImportError(
                "OpenCGEAdapter.execute() requires dask[distributed]. "
                "Install with: pip install 'dask[distributed]'"
            ) from exc

        scenario_id = inputs["scenario_id"]
        reform_dict = inputs["reform_dict"]
        baseline_dir = Path(inputs["baseline_dir"])
        reform_dir = Path(inputs["reform_dir"])
        baseline_dir.mkdir(parents=True, exist_ok=True)
        reform_dir.mkdir(parents=True, exist_ok=True)

        cluster: LocalCluster | None = None
        client: Client | None = None
        start = time.time()

        try:
            cluster = LocalCluster(
                n_workers=self._config.num_workers,
                threads_per_worker=1,
                processes=True,
            )
            client = Client(cluster)

            # 1. Build baseline Specifications.
            p_baseline = Specifications(
                baseline=True,
                baseline_dir=str(baseline_dir),
                output_base=str(baseline_dir),
                num_workers=self._config.num_workers,
            )
            self._apply_calibration(p_baseline)

            # Settings shared by baseline and reform, so the two solves
            # differ only in the shock.
            shared = {
                k: reform_dict[k]
                for k in self._SHARED_SETTINGS
                if k in reform_dict
            }
            if shared:
                p_baseline.update_specifications(shared)
            baseline_done = self._baseline_complete(
                baseline_dir, self._config.solution_method, shared
            )
            require_cached = os.environ.get("HORMUZ_OPENCGE_REQUIRE_BASELINE") == "1"
            if require_cached and not baseline_done:
                # Parallel reform cells share one baseline directory; a cell
                # must never start solving (and overwriting) it on its own.
                raise RuntimeError(
                    f"OpenCGE baseline cache at {baseline_dir} is incomplete or was solved with "
                    f"different settings ({shared}); HORMUZ_OPENCGE_REQUIRE_BASELINE=1 forbids "
                    "re-solving it here. Solve the baseline in a single job first."
                )
            if not require_cached and (not baseline_done or not self._config.skip_baseline_if_present):
                # The baseline directory is shared by every job on the
                # cluster; refuse to start while another live job is solving
                # it (run 89206 vs revision job 89217, 2026-11-08).
                busy = self._live_baseline_marker(baseline_dir)
                if busy:
                    raise RuntimeError(
                        f"OpenCGE baseline at {baseline_dir} is being solved by another job ({busy}); "
                        "not starting a second solve into the same directory."
                    )
                self._write_baseline_marker(baseline_dir)
                (baseline_dir / self._BASELINE_STAMP).unlink(missing_ok=True)
                logger.info(
                    "OpenCGE: running baseline (this may take 30+ minutes)..."
                )
                try:
                    # runner(time_path=True) solves the steady state first and
                    # then the transition path, so one call covers both.
                    runner(
                        p_baseline,
                        time_path=(self._config.solution_method == "TPI"),
                        client=client,
                    )
                    self._write_baseline_stamp(baseline_dir, shared)
                finally:
                    (baseline_dir / self._BASELINE_MARKER).unlink(missing_ok=True)

            # 2. Build reform Specifications and apply the reform_dict.
            p_reform = Specifications(
                baseline=False,
                baseline_dir=str(baseline_dir),
                output_base=str(reform_dir),
                num_workers=self._config.num_workers,
            )
            self._apply_calibration(p_reform)
            reform_update = dict(reform_dict)
            base_delta = getattr(p_reform, "delta_annual", 0.05)
            delta_adj = float(inputs.get("delta_annual_adj", 0.0) or 0.0)
            reform_update["delta_annual"] = self._delta_annual_update(
                base_delta, delta_adj
            )
            p_reform.update_specifications(reform_update)

            # 3. Run reform.
            logger.info(
                "OpenCGE: running reform for scenario %s (TPI iter=%d)...",
                scenario_id,
                self._config.time_path_iter,
            )
            runner(
                p_reform,
                time_path=(self._config.solution_method == "TPI"),
                client=client,
            )

            elapsed = time.time() - start

            # 4. Read outputs.
            outputs = self._read_outputs(baseline_dir, reform_dir)
            outputs["_applied_shocks"] = inputs.get("applied_shocks", {})
            outputs["_duration_years"] = inputs.get("duration_years")
            outputs["_capital_drag_applied"] = bool(inputs.get("capital_drag_applied", True))
            outputs["_z_path_shock_years"] = [
                row[0] for row in reform_dict.get("Z", []) if row and row[0] != 1.0
            ]

            # OG-Core is single-country (US) by construction. Surface
            # the headline US response as a one-row ``regional_vars``
            # table so the synthesizer's regional layer can consume it
            # alongside MIRAGRODEP / PyCGE / energy-tier outputs. Also
            # attach a kernel-derived multi-region context row set
            # tagged ``regional_context_vars`` so analysts comparing the
            # US OG-Core answer to PyCGE / MIRAGRODEP have a calibrated
            # cross-region benchmark from the shared elasticity table.
            applied = inputs.get("applied_shocks", {}) or {}
            duration_years = float(inputs.get("duration_years") or 0.5)
            duration_months = duration_years * 12.0
            outputs["regional_vars"] = self._build_us_regional_row(outputs)
            from src.models.macro.macro_kernel import (
                compute_regional_macro_outcomes,
            )
            outputs["regional_context_vars"] = compute_regional_macro_outcomes(
                self._kernel_shocks(applied), duration_months, regime="long_run"
            )
            outputs["_regional_source"] = "ogcore_us_native_plus_kernel_context"

            return ModelOutput(
                model_id=self.model_id,
                outputs=outputs,
                convergence_status="completed",
                metadata={
                    "scenario_id": scenario_id,
                    "baseline_dir": str(baseline_dir),
                    "reform_dir": str(reform_dir),
                    "elapsed_seconds": elapsed,
                    "solution_method": self._config.solution_method,
                    "num_workers": self._config.num_workers,
                },
            )

        finally:
            if client is not None:
                client.close()
            if cluster is not None:
                cluster.close()

    def _apply_calibration(self, p: Any) -> None:
        """Apply OG-USA calibration data to a Specifications object.

        Uses ogusa.calibrate.Calibration if ogusa is installed and an
        ogusa_data_dir is configured. Otherwise relies on OG-Core's
        bundled defaults (typically slower and less realistic).
        """
        if self._config.ogusa_data_dir is None:
            return
        try:
            from ogusa.calibrate import Calibration
        except ImportError:
            logger.warning(
                "ogusa not installed; OpenCGE will use OG-Core defaults. "
                "Install with: pip install ogusa"
            )
            return

        try:
            cal = Calibration(p, data_dir=str(self._config.ogusa_data_dir))
            d = cal.get_dict()
            p.update_specifications(d)
        except Exception as exc:
            logger.warning(
                "OG-USA calibration failed (%s); falling back to defaults",
                exc,
            )

    def _read_outputs(
        self, baseline_dir: Path, reform_dir: Path,
    ) -> dict[str, Any]:
        """Read OG-Core SS / TPI output pickles and standardize key aggregates.

        Returns a dict with both raw arrays and percent-change-from-baseline
        scalars for headline variables (welfare, GDP path, wage path,
        interest-rate path, consumption).
        """
        out: dict[str, Any] = {
            "_baseline_dir": str(baseline_dir),
            "_reform_dir": str(reform_dir),
        }

        # SS_vars.pkl
        ss_reform = self._safe_pickle(reform_dir / "SS" / "SS_vars.pkl")
        ss_baseline = self._safe_pickle(baseline_dir / "SS" / "SS_vars.pkl")
        if ss_reform:
            out["ss_reform"] = self._summarize_ss(ss_reform)
        if ss_baseline:
            out["ss_baseline"] = self._summarize_ss(ss_baseline)

        # TPI_vars.pkl
        tpi_reform = self._safe_pickle(reform_dir / "TPI" / "TPI_vars.pkl")
        tpi_baseline = self._safe_pickle(baseline_dir / "TPI" / "TPI_vars.pkl")

        # Standardized headline outputs
        if tpi_reform and tpi_baseline:
            out["gdp_pct_change_path"] = self._pct_change_path(
                tpi_baseline, tpi_reform, "Y"
            )
            out["wage_pct_change_path"] = self._pct_change_path(
                tpi_baseline, tpi_reform, "w"
            )
            out["interest_rate_path"] = self._scalar_path(tpi_reform, "r")
            out["consumption_pct_change"] = self._pct_change_path(
                tpi_baseline, tpi_reform, "C"
            )

        # Welfare: lifetime utility difference at SS (if available).
        if ss_reform and ss_baseline:
            out["welfare_pct_change"] = self._compute_welfare_change(
                ss_baseline, ss_reform
            )

        # Headline scalars convenient for cross-model consistency checks.
        if "gdp_pct_change_path" in out and out["gdp_pct_change_path"]:
            out["gdp_impact_pct"] = float(out["gdp_pct_change_path"][0])
        if "wage_pct_change_path" in out and out["wage_pct_change_path"]:
            out["wage_impact_pct"] = float(out["wage_pct_change_path"][0])

        return out

    @staticmethod
    def _kernel_shocks(applied: dict[str, Any]) -> dict[str, float]:
        """Reduce ``applied_shocks`` to the ``commodity -> percent`` map the kernel takes.

        ``translate_inputs`` records each commodity as a dict
        (``shock_pct``, ``Z_delta``, ``delta_annual_delta``). The kernel
        silently drops non-numeric values, so passing the dicts through
        produced an all-zero ``regional_context_vars`` table in both
        supplementary runs (supp_full_20260504_222710 and
        supp_full_mkt_20260504_222710).
        """
        shocks: dict[str, float] = {}
        for commodity, rec in (applied or {}).items():
            value = rec.get("shock_pct") if isinstance(rec, dict) else rec
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                shocks[commodity] = float(value)
        return shocks

    @staticmethod
    def _build_us_regional_row(outputs: dict[str, Any]) -> list[dict[str, Any]]:
        """Build a single-row ``regional_vars`` table for OG-Core's US response.

        OG-Core is a single-country US OLG model, so its native regional
        granularity is exactly one region. Surfacing a one-row table
        keeps the synthesizer's regional layer happy (it can read the
        ``regional`` spec uniformly across PyCGE, MIRAGRODEP, OpenCGE,
        and the energy adapters) without pretending the model produced
        ROW or MENA outcomes it did not solve for.
        """
        row: dict[str, Any] = {"region": "US"}
        if "gdp_impact_pct" in outputs:
            row["gdp_impact_pct"] = float(outputs["gdp_impact_pct"])
        if "wage_impact_pct" in outputs:
            row["wage_impact_pct"] = float(outputs["wage_impact_pct"])
        if "welfare_pct_change" in outputs and outputs["welfare_pct_change"] is not None:
            row["welfare_pct_change"] = float(outputs["welfare_pct_change"])
        cons = outputs.get("consumption_pct_change")
        if isinstance(cons, list) and cons:
            row["consumption_impact_pct"] = float(cons[0])
        return [row]

    @staticmethod
    def _safe_pickle(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)  # noqa: S301 — controlled OG-Core output
        except (OSError, pickle.UnpicklingError) as exc:
            logger.warning("Failed to load %s: %s", path, exc)
            return None

    # OG-Core >= 0.10 saves steady-state aggregates under short keys
    # ("Y", "C", ...; see ogcore/SS.py SS_solver ``output``). Older
    # releases used "Yss"/"Css"; the "_ss" spellings are kept as a last
    # fallback because the adapter originally read them.
    _SS_KEYS: tuple[str, ...] = ("Y", "C", "K", "L", "w", "r", "BQ", "I", "G", "D")

    @staticmethod
    def _ss_value(ss: dict[str, Any], key: str) -> Any:
        for candidate in (key, f"{key}ss", f"{key}_ss"):
            if candidate in ss and ss[candidate] is not None:
                return ss[candidate]
        return None

    @classmethod
    def _summarize_ss(cls, ss: dict[str, Any]) -> dict[str, Any]:
        """Reduce a SS_vars dict to scalar summaries for serialization."""
        summary: dict[str, Any] = {}
        for key in cls._SS_KEYS:
            v = cls._ss_value(ss, key)
            if v is None:
                continue
            try:
                summary[key] = float(v)
            except (TypeError, ValueError):
                pass
        return summary

    @staticmethod
    def _scalar_path(tpi: dict[str, Any], var: str, max_periods: int = 50) -> list[float]:
        v = tpi.get(var)
        if v is None:
            return []
        try:
            arr = list(v.flatten()) if hasattr(v, "flatten") else list(v)
        except Exception:
            return []
        return [float(x) for x in arr[:max_periods]]

    @classmethod
    def _pct_change_path(
        cls,
        baseline: dict[str, Any],
        reform: dict[str, Any],
        var: str,
        max_periods: int = 50,
    ) -> list[float]:
        b = cls._scalar_path(baseline, var, max_periods)
        r = cls._scalar_path(reform, var, max_periods)
        n = min(len(b), len(r))
        out: list[float] = []
        for i in range(n):
            if b[i] == 0:
                out.append(0.0)
            else:
                out.append(round((r[i] - b[i]) / b[i] * 100.0, 4))
        return out

    @classmethod
    def _compute_welfare_change(
        cls,
        ss_baseline: dict[str, Any],
        ss_reform: dict[str, Any],
    ) -> float | None:
        """Steady-state aggregate-consumption change, a first-order welfare proxy.

        This is not a Hicksian equivalent variation (that needs the full
        utility function and lifetime paths); it is reported as
        ``welfare_pct_change`` for comparability with the other CGEs.
        """
        cb = cls._ss_value(ss_baseline, "C")
        cr = cls._ss_value(ss_reform, "C")
        if cb is None or cr is None:
            return None
        try:
            cb, cr = float(cb), float(cr)
        except (TypeError, ValueError):
            return None
        if cb == 0:
            return None
        return round((cr - cb) / cb * 100.0, 4)

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Wrap raw output dict in a ModelOutput, or pass through a ModelOutput."""
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
