"""Adapter for SimRLFab — RL/SimPy simulation of semiconductor fab disruption.

SimRLFab (https://github.com/AndreasKuhnle/SimRLFab) is a SimPy-based discrete
event simulation of a complex job-shop fab, paired with a Tensorforce
reinforcement-learning agent (PPO/TRPO) that controls order dispatching.
Heuristic baselines (FIFO, NJF, EMPTY) are also provided for benchmarking.

The model is **not** intrinsically a helium consumption model. It is a fab
operations simulator. To use it for Strait of Hormuz disruption analysis we
translate the pipeline's high-level supply-disruption parameters into
fab-operations parameters that drive the simulation:

* ``helium_supply_reduction_pct`` and ``neon_supply_status`` →
  reduced ``MTBF`` and inflated ``MTOL`` on the subset of machines that
  depend on each gas. Gas exhaustion is modelled as a forced "process gas"
  breakdown event whose frequency (1/MTBF) and duration (MTOL) scale with
  the supply shortfall. Helium is used in ion implantation, deposition and
  wafer cleaning; neon is used in excimer-laser lithography. The default
  ``helium_affected_machines`` and ``neon_affected_machines`` indices reflect
  this rough mapping for the SimRLFab default 8-machine layout.
* ``fab_utilization_baseline`` → ``MTOG`` (mean time order generation) for
  each source. Lower baseline utilization means orders arrive less often and
  there is a larger inventory buffer to absorb gas-shortage breakdowns.
* ``disruption_duration_months`` → number of training/simulation episodes,
  via ``episodes_per_disruption_month``. SimRLFab uses minutes as its time
  unit and the absolute simulation horizon is determined dynamically by the
  episode loop, so this is a proxy for "how long do we simulate the
  disrupted regime".

This is an approximation: SimRLFab does not natively model gas inventories.
The fab operator effectively sees gas-supply shortfalls as a rise in the
breakdown rate of the gas-dependent machines, which is what the simulator
exposes through MTBF/MTOL.

Execution is delegated to the ``SubprocessAdapter`` base class. SimRLFab
pins ``simpy==4.0`` / ``tensorforce==0.5.4`` / ``numpy==1.17`` / Python 3.6
(see ``Models/Helium Market_ Semiconductors/SimRLFab-master/SimRLFab-master/
requirements.txt``), which is incompatible with the orchestration pipeline's
modern environment. Running it in an isolated venv via subprocess is
therefore the only practical option. The ``simrlfab_driver.py`` script that
ships alongside this adapter performs the in-process integration: it sets up
``sys.path`` for the SimRLFab repo, monkey-patches
``production.envs.initialize_env.extend_production_parameters`` /
``extend_agent_parameters`` to apply the per-scenario overrides, runs the
simulation, and writes the KPIs back as JSON.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.adapters.subprocess_adapter import SubprocessAdapter, SubprocessConfig
from src.models.base import ModelOutput, ResourceRequirements, ValidationResult

_NEON_STATUS_VALID_VALUES = {"normal", "constrained", "severely_disrupted"}

_NEON_STATUS_TO_FACTORS: dict[str, dict[str, float]] = {
    "normal": {"mtbf_factor": 1.0, "mtol_factor": 1.0},
    "constrained": {"mtbf_factor": 0.7, "mtol_factor": 1.3},
    "severely_disrupted": {"mtbf_factor": 0.3, "mtol_factor": 2.5},
}

_DEFAULT_DRIVER_SCRIPT = (
    Path(__file__).resolve().parent / "simrlfab_driver.py"
)


class SimRLFabConfig(BaseModel):
    """Configuration for executing SimRLFab via subprocess.

    Attributes:
        simrlfab_repo_path: Filesystem path to the SimRLFab repository root
            (the directory that contains ``run.py`` and ``production/``).
        python_executable: Python interpreter that has SimRLFab's pinned
            dependencies installed (simpy==4.0, tensorforce==0.5.4,
            numpy==1.17, pandas==1.0.3, progressbar2==3.51.3). Typically
            this is the python from a dedicated venv created for SimRLFab.
        driver_script: Path to ``simrlfab_driver.py``. Defaults to the
            driver script that ships alongside this adapter.
        episodes: Number of episodes the SimRLFab Runner trains/runs for at
            the *baseline* duration (one disruption month). The actual run
            scales with ``disruption_duration_months``.
        timesteps_per_episode: Maximum number of agent actions per episode
            (mapped to ``max_episode_timesteps`` in SimRLFab).
        agent_type: Dispatch agent. One of ``"FIFO"``, ``"NJF"``,
            ``"EMPTY"``, ``"TRPO"``, ``"PPO"``. Heuristics still go through
            the Tensorforce Runner (SimRLFab's design) but skip RL training.
        agent_config_path: Path to a Tensorforce agent config JSON. Required
            when ``agent_type`` is ``"TRPO"`` or ``"PPO"``. Defaults to
            ``<repo>/config/ppo1.json`` when None.
        helium_affected_machines: Machine indices (0-based) whose MTBF/MTOL
            are scaled by the helium supply shortfall.
        neon_affected_machines: Machine indices whose MTBF/MTOL are scaled
            by the neon supply status.
        episodes_per_disruption_month: Conversion factor used to scale
            ``disruption_duration_months`` into a number of episodes.
        timeout_seconds: Subprocess timeout. Tensorforce RL runs are slow;
            give them ample time.
        run_dir_base: Base directory for per-run scratch (inputs.json,
            outputs.json, KPI logs).
    """

    simrlfab_repo_path: Path
    python_executable: str = "python"
    driver_script: Path = Field(default=_DEFAULT_DRIVER_SCRIPT)
    episodes: int = Field(default=50, ge=1)
    timesteps_per_episode: int = Field(default=100, ge=1)
    agent_type: str = Field(default="FIFO")
    agent_config_path: Path | None = None
    helium_affected_machines: list[int] = Field(default_factory=lambda: [0, 1, 2])
    neon_affected_machines: list[int] = Field(default_factory=lambda: [3, 4])
    episodes_per_disruption_month: float = Field(default=10.0, gt=0.0)
    timeout_seconds: int = Field(default=7200, ge=60)
    run_dir_base: Path | None = None

    def to_subprocess_config(self) -> SubprocessConfig:
        """Build the underlying SubprocessConfig used by SubprocessAdapter.

        All embedded paths are pre-converted to forward-slash (POSIX) form
        so the shlex tokenizer in SubprocessAdapter._build_command does not
        consume Windows backslashes as escape characters. Quoted strings
        protect paths that contain spaces (e.g., 'Helium Market_
        Semiconductors').
        """
        python_exe = (
            Path(self.python_executable).as_posix()
            if Path(self.python_executable).is_absolute()
            or os.sep in self.python_executable
            or "/" in self.python_executable
            else self.python_executable
        )
        driver = Path(self.driver_script).as_posix()
        repo = Path(self.simrlfab_repo_path).as_posix()

        cmd_template = (
            f'"{python_exe}" '
            f'"{driver}" '
            f'--input "{{input_path}}" '
            f'--output "{{output_path}}" '
            f'--simrlfab-path "{repo}" '
            f'--run-dir "{{run_dir}}"'
        )
        kwargs: dict[str, Any] = {
            "command_template": cmd_template,
            "working_directory": self.simrlfab_repo_path,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.run_dir_base is not None:
            kwargs["run_dir_base"] = self.run_dir_base
        return SubprocessConfig(**kwargs)


class SimRLFabAdapter(SubprocessAdapter):
    """Adapter for the SimRLFab semiconductor fab simulation.

    Real implementation requirements:

    * A clone or copy of the SimRLFab repository (this workspace ships one
      under ``Models/Helium Market_ Semiconductors/SimRLFab-master/``).
    * A dedicated Python environment with SimRLFab's pinned dependencies
      installed. The pin set targets Python 3.6 — using a conda env or
      virtualenv with that interpreter is the most reliable path:

      .. code-block:: bash

          conda create -n simrlfab python=3.6
          conda activate simrlfab
          pip install -r "Models/Helium Market_ Semiconductors/\
SimRLFab-master/SimRLFab-master/requirements.txt"

    * A :class:`SimRLFabConfig` that points at the repo root and that
      Python interpreter.
    * Optionally, a Tensorforce agent config JSON when running with
      ``agent_type="PPO"`` or ``"TRPO"``. Heuristic agent types
      (``FIFO``, ``NJF``, ``EMPTY``) skip RL training and run much faster.

    The adapter monkey-patches SimRLFab's parameter initialization rather
    than editing the upstream sources. This keeps the SimRLFab repo
    pristine and lets multiple scenarios share a single SimRLFab install.
    """

    def __init__(self, config: SimRLFabConfig | None = None) -> None:
        self._sim_config = config
        sub_config = config.to_subprocess_config() if config is not None else None
        super().__init__(sub_config)

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
            "SimRLFab: SimPy + Tensorforce simulation of complex job-shop "
            "semiconductor fab operations. Helium and neon supply shortfalls are "
            "translated into elevated breakdown rates (MTBF/MTOL) on the gas-"
            "dependent machine subsets to estimate fab utilization, finished-order "
            "throughput, order cycle time, and the alpha congestion factor under "
            "Strait of Hormuz closure scenarios."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=2,
            memory_gb=4.0,
            supports_multi_threading=False,
            prefers_process_isolation=True,
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
            "Duration of the helium supply disruption in months. Mapped to a "
            "number of SimRLFab episodes via "
            "SimRLFabConfig.episodes_per_disruption_month."
        ),
        "fab_utilization_baseline": (
            "Baseline fab utilization rate at disruption onset (0.0–1.0, "
            "where 1.0 = 100% utilization). Drives the source MTOG (mean "
            "time order generation) and therefore the inventory-buffer "
            "headroom available to absorb gas-shortage breakdowns."
        ),
    }

    PARAM_BOUNDS: dict[str, tuple[float, float]] = {
        "helium_supply_reduction_pct": (0.0, 100.0),
        "disruption_duration_months": (0.0, 36.0),
        "fab_utilization_baseline": (0.0, 1.0),
    }

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate required parameters and check value ranges and categorical values."""
        errors: list[str] = []
        warnings: list[str] = []

        for param_name in self.REQUIRED_PARAMS:
            if param_name not in params:
                errors.append(
                    f"Missing required parameter '{param_name}': "
                    f"{self.REQUIRED_PARAMS[param_name]}"
                )

        for param_name, (low, high) in self.PARAM_BOUNDS.items():
            if param_name not in params:
                continue
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

        if "neon_supply_status" in params:
            neon_val = params["neon_supply_status"]
            if neon_val not in _NEON_STATUS_VALID_VALUES:
                errors.append(
                    f"Parameter 'neon_supply_status' = {neon_val!r} is not a recognized "
                    f"value. Must be one of: {sorted(_NEON_STATUS_VALID_VALUES)}."
                )

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
                        "horizon over which the SimRLFab RL policy is typically trained. "
                        "Outputs beyond this horizon are extrapolations and should be "
                        "interpreted with caution."
                    )
            except (TypeError, ValueError):
                pass

        if "neon_supply_status" in params and "helium_supply_reduction_pct" in params:
            neon_val = params["neon_supply_status"]
            try:
                he_pct = float(params["helium_supply_reduction_pct"])
                if neon_val == "severely_disrupted" and he_pct > 20.0:
                    warnings.append(
                        f"Both helium (>{he_pct:.0f}% reduction) and neon "
                        "('severely_disrupted') are simultaneously constrained. This "
                        "compound-shortage scenario may push fab operations outside the "
                        "range of the RL agent's training distribution. Flag outputs "
                        "for analyst review."
                    )
            except (TypeError, ValueError):
                pass

        if "fab_utilization_baseline" in params:
            try:
                util = float(params["fab_utilization_baseline"])
                if util < 0.7:
                    warnings.append(
                        f"fab_utilization_baseline = {util:.2f} indicates fabs operating "
                        "below 70% capacity at disruption onset. Lower baseline "
                        "utilization increases the gas inventory buffer and may cause "
                        "SimRLFab to underestimate disruption severity relative to a "
                        "high-utilization baseline."
                    )
            except (TypeError, ValueError):
                pass

        if self._sim_config is not None:
            cfg = self._sim_config
            agent_t = cfg.agent_type.upper()
            if agent_t in {"PPO", "TRPO"} and cfg.agent_config_path is None:
                warnings.append(
                    f"agent_type={cfg.agent_type!r} but no agent_config_path is set; "
                    f"the driver will fall back to <repo>/config/ppo1.json or trpo1.json."
                )
            valid_agents = {"FIFO", "NJF", "EMPTY", "PPO", "TRPO"}
            if agent_t not in valid_agents:
                errors.append(
                    f"SimRLFabConfig.agent_type = {cfg.agent_type!r} is not recognized. "
                    f"Must be one of: {sorted(valid_agents)}."
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Translation: high-level params → SimRLFab parameter overrides
    # ------------------------------------------------------------------

    # Baseline values that match SimRLFab's defaults in
    # production/envs/initialize_env.py::extend_production_parameters.
    _BASELINE_MTBF_MIN = 1000.0
    _BASELINE_MTOL_MIN = 200.0
    _BASELINE_MTOG_MIN = 10.0
    _BASELINE_UTILIZATION = 0.85

    def _compute_machine_overrides(
        self, params: dict[str, Any]
    ) -> tuple[dict[int, float], dict[int, float]]:
        """Map gas shortfalls to per-machine MTBF/MTOL overrides.

        Helium reduction (in pct) compresses MTBF and inflates MTOL on the
        helium-affected machines linearly. Neon status applies a categorical
        multiplier on the neon-affected machines. Where a machine appears on
        both lists, the multipliers compose (worst case wins).
        """
        cfg = self._sim_config
        if cfg is None:
            return {}, {}

        he_pct = float(params.get("helium_supply_reduction_pct", 0.0))
        he_mtbf_factor = max(0.05, 1.0 - he_pct / 100.0)
        he_mtol_factor = 1.0 + he_pct / 100.0

        neon_status = params.get("neon_supply_status", "normal")
        neon_factors = _NEON_STATUS_TO_FACTORS.get(neon_status, _NEON_STATUS_TO_FACTORS["normal"])

        mtbf_overrides: dict[int, float] = {}
        mtol_overrides: dict[int, float] = {}

        for idx in cfg.helium_affected_machines:
            mtbf_overrides[idx] = self._BASELINE_MTBF_MIN * he_mtbf_factor
            mtol_overrides[idx] = self._BASELINE_MTOL_MIN * he_mtol_factor

        for idx in cfg.neon_affected_machines:
            base_mtbf = mtbf_overrides.get(idx, self._BASELINE_MTBF_MIN)
            base_mtol = mtol_overrides.get(idx, self._BASELINE_MTOL_MIN)
            mtbf_overrides[idx] = base_mtbf * neon_factors["mtbf_factor"]
            mtol_overrides[idx] = base_mtol * neon_factors["mtol_factor"]

        return mtbf_overrides, mtol_overrides

    def _compute_mtog(self, params: dict[str, Any]) -> float:
        """Map fab_utilization_baseline → MTOG (mean time order generation).

        Uses a simple inverse scaling around SimRLFab's default
        (utilization 0.85 ↔ MTOG 10 minutes). Lower utilization → higher
        MTOG (fewer orders arriving), higher utilization → lower MTOG.
        Bounded to keep the simulation numerically well behaved.
        """
        util = float(params.get("fab_utilization_baseline", self._BASELINE_UTILIZATION))
        util = max(0.1, min(util, 0.99))
        mtog = self._BASELINE_MTOG_MIN * (self._BASELINE_UTILIZATION / util)
        return max(2.0, min(mtog, 60.0))

    def _compute_episodes(self, params: dict[str, Any]) -> int:
        """Scale the configured baseline episode count by disruption duration.

        ``cfg.episodes`` defines the number of episodes that represents the
        baseline 1-month disruption. We then linearly scale by
        ``disruption_duration_months``, with a separate multiplier
        (``episodes_per_disruption_month``) available when an analyst wants
        to explicitly set the per-month episode budget.
        """
        cfg = self._sim_config
        if cfg is None:
            return 0
        duration = float(params.get("disruption_duration_months", 1.0))
        scaled = int(round(cfg.episodes_per_disruption_month * max(0.0, duration)))
        return max(1, scaled)

    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert validated parameters into the JSON config consumed by the driver.

        Returns:
            Dict that the SimRLFab driver script reads from ``inputs.json``.
        """
        if self._sim_config is None:
            raise ValueError(
                "SimRLFabAdapter.translate_inputs_to_dict requires a "
                "SimRLFabConfig. Initialize the adapter with one before "
                "calling translate_inputs / execute."
            )

        cfg = self._sim_config
        mtbf_overrides, mtol_overrides = self._compute_machine_overrides(params)
        mtog = self._compute_mtog(params)
        episodes = self._compute_episodes(params)

        agent_config_path = (
            str(cfg.agent_config_path) if cfg.agent_config_path is not None else None
        )

        scenario_id = params.get("scenario_id", "default")

        return {
            "scenario_id": scenario_id,
            "episodes": episodes,
            "timesteps_per_episode": cfg.timesteps_per_episode,
            "agent_type": cfg.agent_type.upper(),
            "agent_config_path": agent_config_path,
            "simrlfab_overrides": {
                "machine_mtbf_overrides": {str(k): v for k, v in mtbf_overrides.items()},
                "machine_mtol_overrides": {str(k): v for k, v in mtol_overrides.items()},
                "mtog_per_source": mtog,
            },
            "input_params": dict(params),
            "mapping_metadata": {
                "helium_affected_machines": list(cfg.helium_affected_machines),
                "neon_affected_machines": list(cfg.neon_affected_machines),
                "baseline_mtbf_min": self._BASELINE_MTBF_MIN,
                "baseline_mtol_min": self._BASELINE_MTOL_MIN,
                "baseline_mtog_min": self._BASELINE_MTOG_MIN,
                "baseline_utilization": self._BASELINE_UTILIZATION,
            },
        }

    def execute(self, inputs: Any) -> ModelOutput:
        """Run SimRLFab via subprocess.

        When no SimRLFabConfig was provided, raises NotImplementedError with
        a description of what is required. Otherwise delegates to
        SubprocessAdapter.execute, which handles JSON I/O, env vars, GPU
        affinity, and srun wrapping if configured.
        """
        if self._sim_config is None:
            raise NotImplementedError(
                "SimRLFabAdapter.execute requires a SimRLFabConfig. "
                "Construct one pointing at: (1) the SimRLFab repository "
                "(this workspace ships a copy under "
                "'Models/Helium Market_ Semiconductors/SimRLFab-master/"
                "SimRLFab-master'); (2) a Python interpreter with SimRLFab's "
                "pinned dependencies installed (simpy==4.0, tensorforce==0.5.4, "
                "numpy==1.17, pandas==1.0.3, progressbar2==3.51.3, typically "
                "Python 3.6 in a dedicated venv); (3) optionally a Tensorforce "
                "agent config JSON when agent_type is 'PPO' or 'TRPO'. "
                "Heuristic agent types ('FIFO', 'NJF', 'EMPTY') run without "
                "RL training and are recommended for fast scenario sweeps."
            )
        return super().execute(inputs)

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Wrap the JSON returned by the driver into a ModelOutput."""
        if isinstance(raw, ModelOutput):
            return raw

        if not isinstance(raw, dict):
            return ModelOutput(
                model_id=self.model_id,
                outputs={"raw": raw},
                convergence_status="unknown",
            )

        kpis = raw.get("kpis", {})
        episode_log = raw.get("episode_log", [])
        applied_overrides = raw.get("applied_overrides", {})
        run_status = raw.get("status", "ok")
        error_message = raw.get("error")

        outputs: dict[str, Any] = {
            "kpis": kpis,
            "episode_log": episode_log,
            "applied_overrides": applied_overrides,
        }
        # Promote a handful of headline KPIs to the top level for easy
        # cross-model comparison in the synthesis layer.
        for key in (
            "machines_working",
            "machines_idle",
            "machines_broken",
            "transp_idle",
            "finished_orders",
            "processed_orders",
            "order_waiting_time",
            "alpha",
            "inventory",
        ):
            if isinstance(kpis, dict) and key in kpis:
                outputs[key] = kpis[key]

        diagnostics: dict[str, Any] = {}
        if error_message:
            diagnostics["error"] = error_message
        if "log_files" in raw:
            diagnostics["log_files"] = raw["log_files"]

        return ModelOutput(
            model_id=self.model_id,
            outputs=outputs,
            convergence_status=run_status,
            metadata=raw.get("metadata", {}),
            diagnostics=diagnostics,
        )
