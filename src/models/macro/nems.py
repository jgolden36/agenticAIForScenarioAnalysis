"""NEMSAdapter — EIA National Energy Modeling System adapter.

Integrates with the NEMS codebase at Models/LNG/NEMS-main/NEMS-main.

NEMS is a Fortran+Python energy-economy equilibrium model that projects
U.S. energy supply, demand, and prices through 2050.  A single "cycle"
takes ~4 hours on EIA servers; a typical 4-cycle run takes 20+ hours.
The model requires Windows, Intel Fortran, AIMMS 4, GAMS, and optionally
EViews for macro feedback.

This adapter supports three execution modes:

    1. **output_ingestion** (default): reads pre-computed NEMS outputs
       (restart.npz, reporter XLSX/CSV, nohup.out) from a completed run
       directory.  Fastest path — no NEMS installation required.

    2. **subprocess**: sets up a run directory from a scedes scenario
       file, then launches ``cycle.py`` (the real NEMS multi-cycle
       orchestrator) as a subprocess.  Requires a full NEMS installation
       with all solver dependencies.

    3. **remote**: submits the run to a SLURM cluster via ``sbatch``.
       Used on GPU clusters where NEMS runs alongside other models —
       NEMS itself is CPU-only but benefits from reserving cores on the
       cluster scheduler.

The adapter does NOT need a GPU.  NEMS is CPU-bound (Fortran + AIMMS
CPLEX solver + GAMS Xpress).  The ``resource_requirements`` declaration
requests 4 CPU cores (parallel partition mode) and ~32 GB RAM, with
``prefers_process_isolation=True`` to avoid GIL contention in the
orchestrator.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import (
    ModelAdapter,
    ModelOutput,
    ResourceRequirements,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class NEMSConfig(BaseModel):
    """Configuration for the NEMS adapter."""

    mode: Literal["output_ingestion", "subprocess", "remote"] = Field(
        default="output_ingestion",
        description="Execution mode",
    )

    # --- Paths ---
    nems_install_dir: Path | None = Field(
        default=None,
        description=(
            "Root of the NEMS repository (the inner NEMS-main/ that contains "
            "source/, models/, scripts/, scedes/).  Required for subprocess "
            "and remote modes."
        ),
    )
    output_base_dir: Path = Field(
        default=Path("data/nems_outputs"),
        description="Base directory for pre-computed NEMS run outputs",
    )
    scenario_dir_mapping: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Maps pipeline scenario IDs to NEMS output subdirectory names. "
            "E.g. {'baseline': 'ref2025/d031725c', "
            "'scenario_a': 'highprice/d041025a'}"
        ),
    )

    # --- Python environment for NEMS ---
    python_env_path: str | None = Field(
        default=None,
        description=(
            "Path to the Python 3.11 environment used by NEMS (the value "
            "that goes into NEMSPYENN in scedes).  Required for "
            "subprocess mode."
        ),
    )

    # --- Run parameters ---
    run_mode: Literal["jog", "par"] = Field(
        default="par",
        description="NEMS run mode: 'jog' (sequential) or 'par' (parallel partitions p1/p2/p3)",
    )
    num_cycles: int = Field(
        default=4,
        description="Number of NEMS cycles (NRUNS in scedes)",
    )
    max_iterations: int = Field(
        default=4,
        description="Max convergence iterations per year (MAXITR in scedes)",
    )
    last_projection_year: int = Field(
        default=2050,
        description="Last projection year (LASTYR in scedes)",
    )
    timeout_seconds: int = Field(
        default=86400,
        description="Timeout for the full NEMS run (default 24 hours)",
    )

    # --- Cluster / SLURM ---
    sbatch_script: Path | None = Field(
        default=None,
        description="Path to a custom sbatch wrapper script for remote mode",
    )
    slurm_partition: str | None = Field(
        default=None,
        description="SLURM partition to target (e.g. 'cpu', 'compute')",
    )
    slurm_account: str | None = Field(
        default=None,
        description="SLURM account for job billing",
    )
    slurm_extra_args: list[str] = Field(
        default_factory=list,
        description="Extra sbatch/srun arguments (e.g. ['--exclusive', '--mem=64G'])",
    )

    # --- Setup mode ---
    use_nems_setup: bool = Field(
        default=True,
        description=(
            "When True, use NEMS's own nems_setup.py to prepare the run "
            "directory (recommended). When False, use the adapter's "
            "lightweight directory preparation."
        ),
    )

    # --- Pipeline shock translation ---
    mam_link_table: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Override the default pipeline-shock → scedes-key map used by "
            "translate_pipeline_shocks_to_scedes. Empty dict means use the "
            "MAM-derived defaults (DEFAULT_MAM_LINK_TABLE in nems_shocks.py)."
        ),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODULE_FLAGS = {
    "IEM": "EXW", "MAM": "EXM", "RDM": "EXR", "CDM": "EXK",
    "IDM": "EXI", "TDM": "EXT", "CMM": "EXC", "EMM": "EXE",
    "NGMM": "EXG", "HSM": "EXL", "LFMM": "EXO", "RFM": "EXN",
    "HMM": "EXH", "CCATS": "EXQ",
}

NEMS_OUTPUT_VARIABLES = {
    "oil_price_wti": "West Texas Intermediate oil price ($/bbl)",
    "natural_gas_price_hh": "Henry Hub natural gas price ($/MMBtu)",
    "gdp_growth_pct": "Real GDP growth rate (%)",
    "cpi_inflation_pct": "Consumer price inflation (%)",
    "unemployment_rate_pct": "Unemployment rate (%)",
    "total_energy_consumption_quads": "Total energy consumption (quadrillion BTU)",
    "petroleum_consumption_mbpd": "Petroleum consumption (million bbl/day)",
    "natural_gas_consumption_tcf": "Natural gas consumption (trillion cubic feet)",
    "electricity_price_cents_kwh": "Average electricity price (cents/kWh)",
    "coal_consumption_quads": "Coal consumption (quadrillion BTU)",
    "renewable_generation_bkwh": "Renewable electricity generation (billion kWh)",
    "co2_emissions_mmt": "Energy-related CO2 emissions (million metric tons)",
    "refinery_utilization_pct": "Petroleum refinery utilization rate (%)",
    "lng_exports_bcf": "LNG exports (billion cubic feet)",
    "petroleum_imports_mbpd": "Net petroleum imports (million bbl/day)",
}

# Scedes keys that cycle.py's run() function reads from scedes.all.
# These must always be present for a run to succeed.
REQUIRED_SCEDES_KEYS = [
    "NEMSPYENN", "NRUNS", "DOAMINOF", "DOEMALL", "MINSCORE",
    "NEMRWR", "SCEN", "DATE",
]

# The run_string that cycle.py expects, mapping from (locality, run_mode).
_RUN_STRING_MAP = {
    ("local", "par"): "local_parallel",
    ("local", "jog"): "local_sequential",
    ("queue", "par"): "queue_parallel",
    ("queue", "jog"): "queue_sequential",
}


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class NEMSAdapter(ModelAdapter):
    """Adapter for the EIA National Energy Modeling System.

    Wraps the full NEMS codebase (Fortran+Python orchestration layer with
    AIMMS/GAMS sub-models) and exposes it through the pipeline's
    ModelAdapter interface.

    The primary execution path either:
      a) delegates to NEMS's own nems_setup.py for directory preparation
         (use_nems_setup=True), or
      b) performs lightweight directory setup and invokes cycle.py directly.

    cycle.py manages multi-cycle convergence, partition merging (tfiler),
    the reporter, and the validator.
    """

    def __init__(self, config: NEMSConfig | None = None) -> None:
        self._config = config or NEMSConfig()

    # -- Identity --------------------------------------------------------

    @property
    def model_id(self) -> str:
        return "nems"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.SHORT_RUN_MACRO

    @property
    def description(self) -> str:
        return (
            "NEMS (EIA): National Energy Modeling System — integrated "
            "U.S. energy-economy equilibrium model producing annual "
            "projections of energy supply, demand, prices, and macro "
            "feedbacks.  Fortran core with Python orchestration, AIMMS "
            "(CPLEX) and GAMS (Xpress) sub-models."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=4,
            memory_gb=32.0,
            supports_multi_threading=True,
            max_threads=4,
            prefers_process_isolation=True,
        )

    # -- Validation ------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        mode = self._config.mode

        if mode == "output_ingestion":
            self._validate_ingestion_inputs(params, errors, warnings)
        elif mode in ("subprocess", "remote"):
            self._validate_execution_inputs(params, errors, warnings)

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings,
        )

    def _validate_ingestion_inputs(
        self, params: dict[str, Any], errors: list[str], warnings: list[str],
    ) -> None:
        if "scenario_id" not in params:
            errors.append("Missing required parameter: 'scenario_id'")
            return
        sid = params["scenario_id"]
        mapping = self._config.scenario_dir_mapping
        if mapping and sid not in mapping:
            available = ", ".join(sorted(mapping.keys()))
            errors.append(
                f"scenario_id '{sid}' not in NEMS output mapping. "
                f"Available: {available}"
            )

    def _validate_execution_inputs(
        self, params: dict[str, Any], errors: list[str], warnings: list[str],
    ) -> None:
        mode = self._config.mode
        nems_dir = self._config.nems_install_dir

        if nems_dir is None:
            errors.append(
                f"NEMSConfig.nems_install_dir is required for '{mode}' mode"
            )
        else:
            if not nems_dir.exists():
                errors.append(
                    f"NEMS install directory does not exist: {nems_dir}"
                )
            else:
                # cycle.py is the actual entry point; it lives in scripts/
                cycle_path = nems_dir / "scripts" / "cycle.py"
                if not cycle_path.exists():
                    errors.append(
                        f"scripts/cycle.py not found under {nems_dir}. "
                        "Verify nems_install_dir points to the inner NEMS-main."
                    )
                flow_path = nems_dir / "source" / "nems_flow.py"
                if not flow_path.exists():
                    warnings.append(
                        f"source/nems_flow.py not found under {nems_dir}. "
                        "The NEMS numerical flow driver may be missing."
                    )

        if "base_scedes" not in params:
            errors.append(
                "Missing required parameter: 'base_scedes' — the name of "
                "the base scedes scenario (e.g. 'ref2025', 'highprice')"
            )
        elif nems_dir and nems_dir.exists():
            scedes_dir = nems_dir / "scedes"
            if scedes_dir.exists():
                scedes_file = scedes_dir / f"scedes.{params['base_scedes']}"
                if not scedes_file.exists():
                    available = [
                        f.name.split(".", 1)[1]
                        for f in scedes_dir.glob("scedes.*")
                        if not f.name.startswith("scedes.all")
                    ]
                    errors.append(
                        f"Scedes file not found: {scedes_file}. "
                        f"Available: {', '.join(sorted(available))}"
                    )

        if mode == "subprocess" and self._config.python_env_path is None:
            errors.append(
                "NEMSConfig.python_env_path is required for subprocess mode"
            )

        if mode == "remote":
            if self._config.sbatch_script is None:
                errors.append(
                    "NEMSConfig.sbatch_script is required for remote mode"
                )
            elif not Path(self._config.sbatch_script).exists():
                warnings.append(
                    f"sbatch_script not found: {self._config.sbatch_script}"
                )

        overrides = params.get("scedes_overrides", {})
        if not isinstance(overrides, dict):
            errors.append("'scedes_overrides' must be a dict of KEY=VALUE pairs")
        else:
            for key, val in overrides.items():
                if "=" in str(key):
                    errors.append(
                        f"scedes_overrides key '{key}' should not contain '='"
                    )
                if key in ("NRUNS", "MAXITR", "LASTYR"):
                    try:
                        int(val)
                    except (ValueError, TypeError):
                        errors.append(f"scedes_overrides['{key}'] must be an integer")

        output_dir = params.get("output_dir")
        if output_dir and not Path(output_dir).parent.exists():
            warnings.append(
                f"Parent of output_dir '{output_dir}' does not exist; "
                "it will be created at run time."
            )

        restart_path = params.get("restart_path")
        if restart_path and not Path(restart_path).exists():
            warnings.append(
                f"Custom restart_path '{restart_path}' does not exist yet"
            )

    # -- Input translation -----------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        mode = self._config.mode

        if mode == "output_ingestion":
            return self._translate_for_ingestion(params)
        return self._translate_for_execution(params)

    def _translate_for_ingestion(self, params: dict[str, Any]) -> dict[str, Any]:
        scenario_id = params["scenario_id"]
        mapping = self._config.scenario_dir_mapping
        dir_name = mapping.get(scenario_id, scenario_id)
        output_dir = self._config.output_base_dir / dir_name

        return {
            "mode": "output_ingestion",
            "scenario_id": scenario_id,
            "output_dir": str(output_dir),
        }

    def _translate_for_execution(self, params: dict[str, Any]) -> dict[str, Any]:
        """Build the full execution specification for a NEMS run.

        Auto-derives scedes overrides from any pipeline commodity-shock
        keys present in ``params`` (oil_price_shock_pct, lng_price_shock_pct,
        natural_gas_price_shock_pct, disruption_duration_months, ...) using
        ``translate_pipeline_shocks_to_scedes``. Explicit ``scedes_overrides``
        passed in ``params`` take precedence.
        """
        from src.models.macro.nems_shocks import translate_pipeline_shocks_to_scedes

        nems_dir = self._config.nems_install_dir
        assert nems_dir is not None

        base_scedes = params["base_scedes"]
        explicit_overrides = params.get("scedes_overrides", {})

        effective_overrides = {
            "NRUNS": str(self._config.num_cycles),
            "MAXITR": str(self._config.max_iterations),
            "LASTYR": str(self._config.last_projection_year),
        }

        if self._config.python_env_path:
            effective_overrides["NEMSPYENN"] = self._config.python_env_path

        # Auto-derive scedes overrides from pipeline shock parameters
        # (oil_price_shock_pct, lng_price_shock_pct, ...).
        derived = translate_pipeline_shocks_to_scedes(
            params,
            mam_link_table=self._config.mam_link_table or None,
            lastyr=self._config.last_projection_year,
        )
        effective_overrides.update(derived)

        # Explicit analyst-supplied overrides win over derived ones.
        effective_overrides.update(explicit_overrides)

        # Apply module on/off overrides
        modules_on = params.get("modules_on")
        modules_off = params.get("modules_off")
        if modules_on:
            for mod in modules_on:
                flag = MODULE_FLAGS.get(mod.upper())
                if flag:
                    effective_overrides[flag] = "1"
        if modules_off:
            for mod in modules_off:
                flag = MODULE_FLAGS.get(mod.upper())
                if flag:
                    effective_overrides[flag] = "0"

        output_dir = params.get("output_dir")
        if not output_dir:
            output_dir = str(
                self._config.output_base_dir / base_scedes / f"run_{int(time.time())}"
            )

        # cycle.py expects run_string like "local_parallel", not "par"
        locality = "local"
        if self._config.mode == "remote":
            locality = "queue"
        run_string = _RUN_STRING_MAP.get(
            (locality, self._config.run_mode),
            f"{locality}_{'parallel' if self._config.run_mode == 'par' else 'sequential'}",
        )

        return {
            "mode": self._config.mode,
            "nems_dir": str(nems_dir),
            "base_scedes": base_scedes,
            "scedes_overrides": effective_overrides,
            "output_dir": output_dir,
            "run_mode": self._config.run_mode,
            "run_string": run_string,
            "python_env_path": self._config.python_env_path,
            "restart_path": params.get("restart_path"),
            "timeout_seconds": self._config.timeout_seconds,
            "use_nems_setup": self._config.use_nems_setup,
            "sbatch_script": str(self._config.sbatch_script) if self._config.sbatch_script else None,
            "slurm_partition": self._config.slurm_partition,
            "slurm_account": self._config.slurm_account,
            "slurm_extra_args": self._config.slurm_extra_args,
        }

    # -- Execution -------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        mode = inputs["mode"]

        if mode == "output_ingestion":
            return self._execute_ingestion(inputs)
        elif mode == "subprocess":
            return self._execute_subprocess(inputs)
        elif mode == "remote":
            return self._execute_remote(inputs)
        else:
            raise ValueError(f"Unknown NEMS execution mode: {mode}")

    # --- Ingestion mode -------------------------------------------------

    def _execute_ingestion(self, inputs: dict[str, Any]) -> ModelOutput:
        output_dir = Path(inputs["output_dir"])

        if not output_dir.exists():
            raise FileNotFoundError(
                f"NEMS output directory not found: {output_dir}\n"
                "Run NEMS externally and place outputs at this path, or "
                "update NEMSConfig.scenario_dir_mapping."
            )

        results = self._read_nems_outputs(output_dir)
        results["_source"] = str(output_dir)

        return ModelOutput(
            model_id=self.model_id,
            outputs=results,
            convergence_status="pre_computed",
            metadata={
                "mode": "output_ingestion",
                "output_dir": str(output_dir),
                "scenario_id": inputs.get("scenario_id", "unknown"),
            },
        )

    # --- Subprocess mode ------------------------------------------------

    def _execute_subprocess(self, inputs: dict[str, Any]) -> ModelOutput:
        nems_dir = Path(inputs["nems_dir"])
        output_dir = Path(inputs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        base_scedes = inputs["base_scedes"]
        overrides = inputs.get("scedes_overrides", {})
        run_string = inputs["run_string"]
        python_env = inputs["python_env_path"]
        timeout = inputs.get("timeout_seconds", 86400)
        use_nems_setup = inputs.get("use_nems_setup", True)

        if use_nems_setup and self._can_use_nems_setup(nems_dir):
            self._prepare_via_nems_setup(nems_dir, output_dir, inputs)
        else:
            self._build_scedes_all(
                nems_dir / "scedes", base_scedes, overrides, output_dir,
            )
            self._prepare_run_directory(nems_dir, output_dir, inputs)

        # Handle custom restart file if provided
        restart_path = inputs.get("restart_path")
        if restart_path:
            dest = output_dir / "input" / Path(restart_path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(restart_path, dest)

        # Build the launch command.
        # cycle.py expects: python cycle.py <dest_path> <run_string>
        python_exe = str(Path(python_env) / "Scripts" / "python.exe")
        cycle_script = str(output_dir / "cycle.py")

        cmd: list[str] = [python_exe, cycle_script, str(output_dir), run_string]

        env = {**os.environ}
        env["NEMS"] = str(nems_dir)
        if python_env:
            env["VIRTUAL_ENV"] = python_env

        start_time = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(output_dir),
            env=env,
        )
        elapsed = time.time() - start_time

        if proc.returncode != 0:
            tail_stderr = proc.stderr[-3000:] if proc.stderr else "no stderr"
            tail_stdout = proc.stdout[-3000:] if proc.stdout else "no stdout"
            raise RuntimeError(
                f"NEMS run failed (rc={proc.returncode}) after "
                f"{elapsed:.0f}s.\nstderr:\n{tail_stderr}\nstdout:\n{tail_stdout}"
            )

        results = self._read_nems_outputs(output_dir)
        results["_source"] = str(output_dir)

        return ModelOutput(
            model_id=self.model_id,
            outputs=results,
            convergence_status="completed",
            metadata={
                "mode": "subprocess",
                "nems_dir": str(nems_dir),
                "output_dir": str(output_dir),
                "base_scedes": base_scedes,
                "run_string": run_string,
                "returncode": proc.returncode,
                "elapsed_seconds": elapsed,
            },
        )

    # --- Remote / cluster mode ------------------------------------------

    def _execute_remote(self, inputs: dict[str, Any]) -> ModelOutput:
        """Submit a NEMS run via sbatch and poll for completion.

        Generates a SLURM batch script that wraps cycle.py invocation
        with proper CPU-only resource requests for a mixed GPU/CPU cluster.
        NEMS is CPU-bound so we request --gres=gpu:0 (or omit GPU requests)
        and allocate CPU cores and memory only.
        """
        nems_dir = Path(inputs["nems_dir"])
        output_dir = Path(inputs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        base_scedes = inputs["base_scedes"]
        overrides = inputs.get("scedes_overrides", {})
        run_string = inputs["run_string"]
        python_env = inputs.get("python_env_path")
        timeout = inputs.get("timeout_seconds", 86400)
        use_nems_setup = inputs.get("use_nems_setup", True)

        # Prepare run directory
        if use_nems_setup and self._can_use_nems_setup(nems_dir):
            self._prepare_via_nems_setup(nems_dir, output_dir, inputs)
        else:
            self._build_scedes_all(
                nems_dir / "scedes", base_scedes, overrides, output_dir,
            )
            self._prepare_run_directory(nems_dir, output_dir, inputs)

        # Build SLURM batch script or use a custom one
        custom_sbatch = inputs.get("sbatch_script")
        if custom_sbatch and Path(custom_sbatch).exists():
            sbatch_path = Path(custom_sbatch)
        else:
            sbatch_path = self._generate_sbatch_script(output_dir, inputs)

        # Submit via sbatch
        cmd = ["sbatch", "--parsable", str(sbatch_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"sbatch submission failed (rc={result.returncode}): "
                f"{result.stderr.strip()}"
            )
        job_id = result.stdout.strip().split(";")[0]

        # Poll for completion via done.txt marker
        poll_interval = 60.0
        elapsed = 0.0
        done_file = output_dir / "done.txt"
        stop_file = output_dir / "stop.txt"

        while elapsed < timeout:
            if done_file.exists():
                break
            if stop_file.exists():
                raise RuntimeError("NEMS run was stopped by user (stop.txt)")

            # Also check SLURM job state to detect early failures
            if elapsed > 0 and elapsed % 300 < poll_interval:
                job_state = self._check_slurm_job_state(job_id)
                if job_state in ("FAILED", "CANCELLED", "TIMEOUT", "NODE_FAIL"):
                    raise RuntimeError(
                        f"SLURM job {job_id} entered state {job_state}"
                    )

            time.sleep(poll_interval)
            elapsed += poll_interval
            poll_interval = min(poll_interval * 1.2, 300)
        else:
            raise TimeoutError(
                f"NEMS remote job {job_id} did not complete within {timeout}s"
            )

        results = self._read_nems_outputs(output_dir)
        results["_source"] = str(output_dir)

        return ModelOutput(
            model_id=self.model_id,
            outputs=results,
            convergence_status="completed",
            metadata={
                "mode": "remote",
                "job_id": job_id,
                "output_dir": str(output_dir),
                "base_scedes": base_scedes,
                "run_string": run_string,
            },
        )

    def _generate_sbatch_script(
        self, output_dir: Path, inputs: dict[str, Any],
    ) -> Path:
        """Generate a SLURM batch script tailored for a CPU-only NEMS run
        on a mixed GPU/CPU cluster.

        Requests only CPU and memory — no GPU resources — so the cluster
        scheduler can pack GPU jobs on other nodes while NEMS occupies
        CPU-only slots.
        """
        python_env = inputs.get("python_env_path", "")
        run_string = inputs["run_string"]
        nems_dir = inputs["nems_dir"]
        partition = inputs.get("slurm_partition", "cpu")
        account = inputs.get("slurm_account")
        extra_args = inputs.get("slurm_extra_args", [])

        python_exe = str(Path(python_env) / "Scripts" / "python.exe") if python_env else "python"
        req = self.resource_requirements

        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=nems-{output_dir.name}",
            f"#SBATCH --output={output_dir / 'slurm-%j.out'}",
            f"#SBATCH --error={output_dir / 'slurm-%j.err'}",
            f"#SBATCH --cpus-per-task={req.cpu_cores}",
            f"#SBATCH --mem={int(req.memory_gb)}G",
            f"#SBATCH --time={inputs.get('timeout_seconds', 86400) // 60}",
        ]
        if partition:
            lines.append(f"#SBATCH --partition={partition}")
        if account:
            lines.append(f"#SBATCH --account={account}")
        # Explicitly avoid requesting GPUs
        lines.append("#SBATCH --gres=gpu:0")
        for arg in extra_args:
            lines.append(f"#SBATCH {arg}")

        lines.extend([
            "",
            f"export NEMS='{nems_dir}'",
            f"cd '{output_dir}'",
            "",
            f"'{python_exe}' cycle.py '{output_dir}' '{run_string}'",
            "exit_code=$?",
            "",
            "if [ $exit_code -eq 0 ]; then",
            "    touch done.txt",
            "fi",
            "",
            "exit $exit_code",
        ])

        script_path = output_dir / "nems_sbatch.sh"
        script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        script_path.chmod(0o755)
        return script_path

    @staticmethod
    def _check_slurm_job_state(job_id: str) -> str:
        """Query SLURM for the current state of a job."""
        try:
            result = subprocess.run(
                ["sacct", "-j", job_id, "--format=State", "--noheader", "--parsable2"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().splitlines()[0].strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return "UNKNOWN"

    # -- Run directory preparation: nems_setup.py path --------------------

    @staticmethod
    def _can_use_nems_setup(nems_dir: Path) -> bool:
        """Check whether NEMS's own setup infrastructure is available."""
        setup_script = nems_dir / "scripts" / "setup" / "src" / "nems_setup.py"
        return setup_script.exists()

    def _prepare_via_nems_setup(
        self, nems_dir: Path, output_dir: Path, inputs: dict[str, Any],
    ) -> None:
        """Use NEMS's own nems_setup.py to prepare the run directory.

        This is the preferred path because nems_setup.py handles the full
        complexity of AIMMS project setup, GAMS configuration, partition
        directory layout, FILELIST processing, etc.

        We invoke nems_submit.py-equivalent logic by setting the environment
        variables that nems_setup.py expects, then calling it as a subprocess.
        """
        nems_dir_str = str(nems_dir)
        python_env = inputs.get("python_env_path", "")
        base_scedes = inputs["base_scedes"]
        run_mode = inputs.get("run_mode", "par") or "par"

        # First, build scedes.all in the scedes/ directory so nems_setup
        # can find it via the normal flow
        overrides = inputs.get("scedes_overrides", {})
        scedes_dir = nems_dir / "scedes"
        self._build_scedes_all(scedes_dir, base_scedes, overrides, output_dir)

        python_exe = str(Path(python_env) / "Scripts" / "python.exe") if python_env else "python"
        setup_script = nems_dir / "scripts" / "setup" / "src" / "nems_setup.py"

        env = {**os.environ}
        env["NEMS"] = nems_dir_str
        env["USER"] = os.environ.get("USER", os.environ.get("USERNAME", "pipeline"))
        env["OUTDIR"] = str(output_dir)
        env["PARNEMS"] = "1" if run_mode == "par" else ""
        env["JOBTYPE"] = "local"
        env["CHKRUNDIR"] = "0"

        try:
            proc = subprocess.run(
                [python_exe, str(setup_script)],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(scedes_dir),
                env=env,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"nems_setup.py failed (rc={proc.returncode}):\n"
                    f"{proc.stderr[-2000:]}"
                )
        except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError):
            # Fall back to lightweight preparation
            self._prepare_run_directory(nems_dir, output_dir, inputs)

    # -- Run directory preparation: lightweight fallback -------------------

    @staticmethod
    def _build_scedes_all(
        scedes_dir: Path,
        base_scedes: str,
        overrides: dict[str, str],
        output_dir: Path,
    ) -> Path:
        """Merge the base scedes file with pipeline overrides to create scedes.all."""
        base_file = scedes_dir / f"scedes.{base_scedes}"
        base_lines: list[str] = []

        if base_file.exists():
            base_lines = base_file.read_text(encoding="utf-8").splitlines()

        existing_keys: set[str] = set()
        merged_lines: list[str] = []
        for line in base_lines:
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                if key in overrides:
                    merged_lines.append(f"{key}={overrides[key]}")
                    existing_keys.add(key)
                else:
                    merged_lines.append(line)
                    existing_keys.add(key)
            else:
                merged_lines.append(line)

        for key, val in overrides.items():
            if key not in existing_keys:
                merged_lines.append(f"{key}={val}")

        # Verify required keys are present
        all_keys = set()
        for line in merged_lines:
            if "=" in line:
                all_keys.add(line.split("=", 1)[0].strip())
        missing = [k for k in REQUIRED_SCEDES_KEYS if k not in all_keys]
        if missing:
            for k in missing:
                if k == "NEMRWR":
                    merged_lines.append("NEMRWR=1")
                elif k == "DOAMINOF":
                    merged_lines.append("DOAMINOF=1")
                elif k == "DOEMALL":
                    merged_lines.append("DOEMALL=0")
                elif k == "MINSCORE":
                    merged_lines.append("MINSCORE=1.5")

        scedes_all_path = output_dir / "scedes.all"
        scedes_all_path.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")
        return scedes_all_path

    @staticmethod
    def _prepare_run_directory(
        nems_dir: Path,
        output_dir: Path,
        inputs: dict[str, Any],
    ) -> None:
        """Copy the NEMS infrastructure needed to execute a run.

        This mirrors what nems_setup.py does, covering the files that
        cycle.py, nems_flow.py, and their dependencies require.
        """
        scripts_dir = nems_dir / "scripts"
        source_dir = nems_dir / "source"
        models_dir = nems_dir / "models"
        models_main = models_dir / "main"

        # --- cycle.py and its direct dependencies ---
        for name in ("cycle.py", "cycle_helper.py", "cleanup.py"):
            src = scripts_dir / name
            if src.exists():
                shutil.copy2(src, output_dir / name)

        # run_task.py — cycle.py imports this; it lives in setup/src/cel/
        run_task_src = scripts_dir / "setup" / "src" / "cel" / "run_task.py"
        if run_task_src.exists():
            shutil.copy2(run_task_src, output_dir / "run_task.py")

        # --- nems_flow.py and nems_flow_wrapper.py ---
        for name in ("nems_flow.py", "nems_flow_wrapper.py"):
            src = source_dir / name
            if src.exists():
                shutil.copy2(src, output_dir / name)

        # --- Fortran executables ---
        for name in ("intercv.exe", "tfiler.exe", "oscillate.exe"):
            src = source_dir / name
            if src.exists():
                shutil.copy2(src, output_dir / name)
            else:
                # Some builds rename .exe → .xxx to avoid antivirus issues
                xxx_src = source_dir / name.replace(".exe", ".xxx")
                if xxx_src.exists():
                    shutil.copy2(xxx_src, output_dir / name)

        # --- models/main/ (parse_scedes, prenems, nexec, postnems, etc.) ---
        dest_main = output_dir / "main"
        if models_main.exists() and not dest_main.exists():
            shutil.copytree(models_main, dest_main)

        # --- unf_to_npz converter (used by cycle.py for .npz generation) ---
        unf_to_npz_src = models_main / "unf_to_npz.py"
        if unf_to_npz_src.exists():
            shutil.copy2(unf_to_npz_src, output_dir / "unf_to_npz.py")

        # --- PyFiler (Fortran/Python restart I/O) ---
        pyfiler_src = scripts_dir / "PyFiler"
        pyfiler_dest = output_dir / "PyFiler"
        if pyfiler_src.exists() and not pyfiler_dest.exists():
            shutil.copytree(pyfiler_src, pyfiler_dest)

        # --- input/ directory with dict.txt, varlist.txt ---
        input_dir = output_dir / "input"
        input_dir.mkdir(exist_ok=True)
        nems_input_dir = nems_dir / "input"
        if nems_input_dir.exists():
            for name in ("dict.txt", "varlist.txt", "iccnvrg.txt"):
                src = nems_input_dir / name
                if src.exists():
                    shutil.copy2(src, input_dir / name)

        # --- Reporter ---
        reporter_src = models_dir / "reporter"
        reporter_dest = output_dir / "reporter"
        if reporter_src.exists() and not reporter_dest.exists():
            shutil.copytree(reporter_src, reporter_dest)

        # --- Converge ---
        converge_src = models_dir / "converge"
        converge_dest = output_dir / "converge"
        if converge_src.exists() and not converge_dest.exists():
            shutil.copytree(converge_src, converge_dest)

        # --- Validator ---
        validator_src = scripts_dir / "Validator"
        validator_dest = output_dir / "Validator"
        if validator_src.exists() and not validator_dest.exists():
            shutil.copytree(validator_src, validator_dest)

        # --- intercvfiles.txt (required by intercycle convergence) ---
        intercv_src = nems_dir / "intercvfiles.txt"
        if intercv_src.exists():
            shutil.copy2(intercv_src, output_dir / "intercvfiles.txt")

        # --- EPM (always needed even when RUNEPM=0) ---
        epm_src = models_dir / "epm"
        epm_dest = output_dir / "epm"
        if epm_src.exists() and not epm_dest.exists():
            shutil.copytree(epm_src, epm_dest)

        # --- NGPL price module (always needed) ---
        ngpl_src = models_dir / "ngpl"
        ngpl_dest = output_dir / "ngpl"
        if ngpl_src.exists() and not ngpl_dest.exists():
            shutil.copytree(ngpl_src, ngpl_dest)

        # --- CCATS ---
        ccats_src = models_dir / "ccats"
        ccats_dest = output_dir / "ccats"
        if ccats_src.exists() and not ccats_dest.exists():
            shutil.copytree(ccats_src, ccats_dest)

        # --- HSM ---
        hsm_src = models_dir / "hsm"
        hsm_dest = output_dir / "hsm"
        if hsm_src.exists() and not hsm_dest.exists():
            shutil.copytree(hsm_src, hsm_dest)

        # --- launched.from marker (cycle.py reads this) ---
        launched_from = output_dir / "launched.from"
        if not launched_from.exists():
            launched_from.write_text(
                f"Pipeline adapter launch\n"
                f"Mode: {inputs.get('run_mode', 'par')}\n"
                f"Base scedes: {inputs.get('base_scedes', 'unknown')}\n"
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"User: {os.environ.get('USER', os.environ.get('USERNAME', 'pipeline'))}\n"
                f"OUTDIR={output_dir}\n",
                encoding="utf-8",
            )

        # --- Parallel partition directories ---
        run_mode = inputs.get("run_mode", "par")
        if run_mode == "par":
            for pdir in ("p1", "p2", "p3"):
                p_path = output_dir / pdir
                p_path.mkdir(exist_ok=True)

                # Each partition needs scedes.all
                scedes_all = output_dir / "scedes.all"
                if scedes_all.exists():
                    shutil.copy2(scedes_all, p_path / "scedes.all")

                # Each partition needs nems_flow.py and wrapper
                for name in ("nems_flow.py", "nems_flow_wrapper.py"):
                    src = output_dir / name
                    if src.exists():
                        shutil.copy2(src, p_path / name)

                # Each partition needs input/ with restart, dict, varlist
                p_input = p_path / "input"
                p_input.mkdir(exist_ok=True)
                for name in ("dict.txt", "varlist.txt"):
                    src = input_dir / name
                    if src.exists():
                        shutil.copy2(src, p_input / name)

                # Each partition needs models/main/ contents
                p_main = p_path / "main"
                if models_main.exists() and not p_main.exists():
                    shutil.copytree(models_main, p_main)

                # Each partition needs PyFiler
                p_pyfiler = p_path / "PyFiler"
                if pyfiler_dest.exists() and not p_pyfiler.exists():
                    shutil.copytree(pyfiler_dest, p_pyfiler)

                # Each partition needs converge/
                p_converge = p_path / "converge"
                if converge_src.exists() and not p_converge.exists():
                    shutil.copytree(converge_src, p_converge)

                # EPM in each partition
                p_epm = p_path / "epm"
                if epm_src.exists() and not p_epm.exists():
                    shutil.copytree(epm_src, p_epm)

                # NGPL in each partition
                p_ngpl = p_path / "ngpl"
                if ngpl_src.exists() and not p_ngpl.exists():
                    shutil.copytree(ngpl_src, p_ngpl)

    # -- Output parsing --------------------------------------------------

    def _read_nems_outputs(self, output_dir: Path) -> dict[str, Any]:
        """Parse all available outputs from a completed NEMS run directory.

        Reads in priority order:
        1. restart.npz  — NumPy archive of the full NEMS state
        2. restart.unf  — Fortran unformatted restart (recorded as path)
        3. Reporter XLSX — AEO-style tables
        4. Reporter CSV  — all_tables_stacked / NEMS API CSV
        5. nohup.out     — run log with timing and convergence info
        6. GPA.txt       — intercycle convergence scores
        7. Validator report — pass/fail status
        """
        results: dict[str, Any] = {}

        # 1. restart.npz (primary structured output)
        npz_files = list(output_dir.rglob("restart.npz"))
        if npz_files:
            results["restart_npz"] = self._parse_restart_npz(npz_files[0])

        # 2. restart.unf (Fortran unformatted restart — record path)
        unf_files = list(output_dir.glob("restart.unf"))
        if not unf_files:
            unf_files = list(output_dir.glob("p3/restart.unf"))
        if unf_files:
            results["restart_unf"] = str(unf_files[0])

        # 3. Reporter XLSX files
        xlsx_files = sorted(output_dir.rglob("*.xlsx"))
        reporter_tables: dict[str, Any] = {}
        for xlsx_path in xlsx_files:
            name_lower = xlsx_path.name.lower()
            if "validator" in name_lower:
                if "pass" in name_lower:
                    results["validator_status"] = "PASS"
                elif "fail" in name_lower:
                    results["validator_status"] = "FAIL"
                results["validator_report"] = str(xlsx_path)
            else:
                reporter_tables[xlsx_path.stem] = str(xlsx_path)
        if reporter_tables:
            results["reporter_xlsx"] = reporter_tables

        # 4. Reporter CSV
        for csv_path in sorted(output_dir.rglob("*.csv")):
            name_lower = csv_path.name.lower()
            if "all_tables" in name_lower or "api" in name_lower:
                results.setdefault("reporter_csv", []).append(str(csv_path))

        # 5. nohup.out — extract run metadata
        nohup_paths = list(output_dir.rglob("nohup.out"))
        if nohup_paths:
            results["run_log"] = self._parse_nohup_log(nohup_paths[0])

        # 6. GPA.txt — intercycle convergence scores
        gpa_path = output_dir / "GPA.txt"
        if gpa_path.exists():
            results["convergence_gpa"] = self._parse_gpa(gpa_path)

        # 7. GDX restart files
        gdx_files = list(output_dir.rglob("restart.gdx"))
        if gdx_files:
            results["restart_gdx"] = str(gdx_files[0])

        # 8. done.txt presence indicates clean completion
        results["completed_cleanly"] = (output_dir / "done.txt").exists()

        # 9. SLURM logs if present
        slurm_logs = sorted(output_dir.glob("slurm-*.out"))
        if slurm_logs:
            results["slurm_log"] = str(slurm_logs[-1])

        # 10. Fallback: root-level JSON
        for jf in output_dir.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    results.setdefault("json_outputs", {})[jf.stem] = data
            except (json.JSONDecodeError, OSError):
                continue

        if not results:
            raise FileNotFoundError(
                f"No parseable outputs found in {output_dir}. "
                "Expected restart.npz, restart.unf, reporter XLSX/CSV, or nohup.out."
            )

        return results

    @staticmethod
    def _parse_restart_npz(npz_path: Path) -> dict[str, Any]:
        """Extract key variables from a NEMS restart.npz file.

        The .npz is written by unf_to_npz.convert_unf_to_npz() using
        PyFiler.NEMSRestartIO.to_npz() and contains all pyfiler
        common-block arrays keyed by Fortran variable name.
        """
        summary: dict[str, Any] = {"path": str(npz_path)}
        try:
            with np.load(str(npz_path), allow_pickle=True) as data:
                summary["variables"] = sorted(data.files)
                summary["num_variables"] = len(data.files)

                key_vars = [
                    "wti_price", "ogwprng", "mc_gdp", "mc_cpi",
                    "mc_unemp", "qelas", "qelrs", "prelas",
                    "qclcl", "qlpin", "qlngin", "qngas",
                    "rfqicrd", "efcaputl",
                ]
                extracted = {}
                for var_name in data.files:
                    vl = var_name.lower()
                    for kv in key_vars:
                        if kv in vl:
                            arr = data[var_name]
                            extracted[var_name] = {
                                "shape": list(arr.shape),
                                "dtype": str(arr.dtype),
                                "sample": arr.flat[:10].tolist() if arr.size > 0 else [],
                            }
                            break
                if extracted:
                    summary["key_variables"] = extracted
        except Exception as e:
            summary["parse_error"] = str(e)

        return summary

    @staticmethod
    def _parse_nohup_log(log_path: Path) -> dict[str, Any]:
        """Extract run metadata from nohup.out."""
        info: dict[str, Any] = {"path": str(log_path)}
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
            info["size_bytes"] = len(text)

            cycle_times: list[str] = []
            convergence_warnings: list[str] = []
            for line in text.splitlines():
                if "TOTAL MODEL TIME" in line:
                    cycle_times.append(line.strip())
                elif "Maximum iterations reached" in line:
                    convergence_warnings.append(line.strip())
                elif "Total time (d:hh:mm)" in line:
                    info["total_runtime"] = line.strip()
            if cycle_times:
                info["cycle_completion_times"] = cycle_times
            if convergence_warnings:
                info["convergence_warnings"] = convergence_warnings

            info["tail"] = text[-2000:]
        except OSError as e:
            info["read_error"] = str(e)

        return info

    @staticmethod
    def _parse_gpa(gpa_path: Path) -> dict[str, Any]:
        """Parse GPA.txt for intercycle convergence scores."""
        gpa_data: dict[str, Any] = {}
        try:
            lines = gpa_path.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if "usgpa=" in line and "rgpa=" in line:
                    parts = line.split("::")
                    cycle_part = [p for p in parts if "cycle" in p]
                    cycle_num = i + 1
                    if cycle_part:
                        try:
                            cycle_num = int(cycle_part[0].strip().split()[-1])
                        except (ValueError, IndexError):
                            pass
                    # Extract GPA values
                    try:
                        usgpa = line.split("usgpa=")[1].split()[0].strip("'\"")
                        rgpa = line.split("rgpa=")[1].strip().strip("'\"")
                        gpa_data[f"cycle_{cycle_num}"] = {
                            "us_gpa": float(usgpa),
                            "regional_gpa": float(rgpa),
                        }
                    except (IndexError, ValueError):
                        pass
        except OSError:
            pass
        return gpa_data

    # -- Output standardisation ------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"mode": self._config.mode},
        )
