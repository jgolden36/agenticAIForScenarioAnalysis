"""Generic subprocess adapter for any model executable via command line.

This is the universal fallback: any model can be wrapped in a thin script
that reads JSON, runs the model, and writes JSON — regardless of native language.

Cluster features:
- GPU device assignment via CUDA_VISIBLE_DEVICES injection
- Optional srun wrapping for SLURM-aware multi-node execution
- Thread/process affinity control via OMP_NUM_THREADS et al.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.base import ModelAdapter, ModelOutput


class SubprocessConfig(BaseModel):
    """Configuration for a subprocess-based model adapter."""

    command_template: str = Field(
        description=(
            "Command template with {input_path}, {output_path}, {run_dir} placeholders. "
            "Example: 'python run_model.py --input {input_path} --output {output_path}'"
        )
    )
    working_directory: Path | None = None
    timeout_seconds: int = 3600
    extra_env: dict[str, str] = Field(default_factory=dict)
    run_dir_base: Path = Field(default_factory=lambda: Path(tempfile.gettempdir()))
    srun_enabled: bool = Field(
        default=False,
        description="Wrap the command with srun for SLURM-aware execution",
    )
    srun_args: list[str] = Field(
        default_factory=list,
        description="Extra srun arguments (e.g., ['--ntasks=1', '--cpus-per-task=4'])",
    )
    gpu_device: int | None = Field(
        default=None,
        description="CUDA device index to bind (set by the executor at runtime)",
    )
    num_threads: int = Field(
        default=1,
        description="CPU threads for this model (sets OMP/MKL/OpenBLAS thread vars)",
    )


class SubprocessAdapter(ModelAdapter):
    """Base class for models invoked via subprocess with JSON I/O.

    Subclasses must implement validate_inputs(), translate_inputs_to_dict(),
    parse_outputs(), and the model metadata properties. The execute() method
    handles subprocess invocation, temp file management, and error capture.

    Convention: inputs are JSON in, outputs are JSON out, communicated via temp files.
    """

    def __init__(self, config: SubprocessConfig | None = None) -> None:
        self._config = config

    @property
    def subprocess_config(self) -> SubprocessConfig:
        if self._config is None:
            raise ValueError(
                f"{self.__class__.__name__} requires a SubprocessConfig. "
                "Pass it via __init__ or override subprocess_config."
            )
        return self._config

    def _get_run_dir(self, scenario_id: str) -> Path:
        """Create an isolated run directory for this execution."""
        run_dir = self.subprocess_config.run_dir_base / f"{self.model_id}_{scenario_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    @abstractmethod
    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert validated parameters to the JSON-serializable dict
        that will be written to the input file."""

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Default implementation delegates to translate_inputs_to_dict."""
        return self.translate_inputs_to_dict(params)

    def _build_env(self) -> dict[str, str]:
        """Build the environment for the subprocess, including GPU and thread control."""
        config = self.subprocess_config
        env = {**os.environ, **config.extra_env}

        if config.gpu_device is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(config.gpu_device)

        threads = str(config.num_threads)
        env.setdefault("OMP_NUM_THREADS", threads)
        env.setdefault("MKL_NUM_THREADS", threads)
        env.setdefault("OPENBLAS_NUM_THREADS", threads)
        env.setdefault("JULIA_NUM_THREADS", threads)

        return env

    def _build_command(self, cmd_str: str) -> list[str]:
        """Build the final command, optionally wrapping with srun.

        Uses shlex.split (posix=True) so quoted arguments — including paths
        that contain spaces — are preserved as single tokens. Adapters that
        embed Windows paths in command_template should pre-convert them to
        forward-slash form (e.g., via Path.as_posix()) so shlex does not
        consume backslashes as escape characters.
        """
        config = self.subprocess_config
        parts = shlex.split(cmd_str, posix=True)

        if config.srun_enabled:
            srun_cmd = ["srun"] + config.srun_args
            if config.gpu_device is not None:
                srun_cmd.extend(["--gres", f"gpu:1"])
            return srun_cmd + parts

        return parts

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the model via subprocess with JSON file I/O.

        Respects GPU device assignment and srun wrapping if configured.
        """
        scenario_id = inputs.get("scenario_id", "default") if isinstance(inputs, dict) else "default"
        config = self.subprocess_config
        run_dir = self._get_run_dir(scenario_id)
        input_path = run_dir / "inputs.json"
        output_path = run_dir / "outputs.json"

        input_data = inputs if isinstance(inputs, dict) else {"data": inputs}
        with open(input_path, "w") as f:
            json.dump(input_data, f, default=str)

        cmd_str = config.command_template.format(
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
            run_dir=run_dir.as_posix(),
        )

        cmd = self._build_command(cmd_str)
        env = self._build_env()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            cwd=str(config.working_directory) if config.working_directory else None,
            env=env,
        )

        metadata = {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-2000:] if result.stderr else "",
            "run_dir": str(run_dir),
            "gpu_device": config.gpu_device,
            "srun_enabled": config.srun_enabled,
        }

        if result.returncode != 0:
            raise RuntimeError(
                f"{self.model_id} subprocess failed (rc={result.returncode}): "
                f"{result.stderr[-500:] if result.stderr else 'no stderr'}"
            )

        if not output_path.exists():
            raise FileNotFoundError(
                f"{self.model_id}: expected output file at {output_path} but it does not exist. "
                f"stdout: {result.stdout[-500:]}"
            )

        with open(output_path) as f:
            raw = json.load(f)

        output = self.parse_outputs(raw)
        if isinstance(output, ModelOutput):
            output.metadata.update(metadata)
            output.gpu_device = config.gpu_device
        return output
