"""R adapter base class for statistical and econometric models.

Uses subprocess (Rscript) by default for safety. In-process rpy2 is
available as an alternative but risks environment conflicts.

Applies to: Various statistical/econometric models with R implementations.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.base import ModelAdapter, ModelOutput


class RConfig(BaseModel):
    """Configuration for R-based model adapters."""

    r_script_path: Path = Field(description="Path to the R script to execute")
    use_rpy2: bool = Field(
        default=False,
        description=(
            "Use rpy2 (in-process) instead of subprocess. "
            "Subprocess is the safer default to avoid environment conflicts."
        ),
    )
    r_executable: str = Field(
        default="Rscript",
        description="Path or name of the Rscript executable.",
    )
    timeout_seconds: int = 3600
    r_libs_path: Path | None = Field(
        default=None, description="Custom R library path (R_LIBS_USER)"
    )
    extra_args: list[str] = Field(
        default_factory=list,
        description="Extra arguments to pass to Rscript (e.g., ['--vanilla'])",
    )
    num_threads: int = Field(
        default=1,
        description="CPU threads (sets MKL/OpenBLAS thread vars for R's BLAS backend)",
    )
    srun_enabled: bool = Field(
        default=False,
        description="Wrap Rscript calls with srun for SLURM-aware execution",
    )
    srun_args: list[str] = Field(
        default_factory=list,
        description="Extra srun arguments",
    )


class RAdapter(ModelAdapter):
    """Base class for R-based model adapters.

    Uses Rscript subprocess by default. The R script must accept a JSON
    input file path as its first argument and write JSON to stdout.

    Convention:
    - Input: JSON file path passed as CLI argument
    - Output: JSON written to stdout

    Subclasses implement:
    - r_function_name(): the R function to call (for rpy2 mode)
    - validate_inputs(): parameter validation
    """

    def __init__(self, config: RConfig | None = None) -> None:
        self._config = config

    @property
    def r_config(self) -> RConfig:
        if self._config is None:
            raise ValueError(
                f"{self.__class__.__name__} requires an RConfig. "
                "Pass it via __init__ or override r_config."
            )
        return self._config

    @abstractmethod
    def translate_inputs_to_dict(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert validated parameters to the JSON dict for the R script."""

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return self.translate_inputs_to_dict(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the R model via subprocess or rpy2."""
        config = self.r_config

        if config.use_rpy2:
            return self._execute_rpy2(inputs)
        else:
            return self._execute_subprocess(inputs)

    def _execute_subprocess(self, inputs: dict[str, Any]) -> ModelOutput:
        """Execute via Rscript subprocess with JSON I/O and thread control."""
        config = self.r_config

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(inputs, f, default=str)
            input_path = f.name

        try:
            cmd = [config.r_executable, "--vanilla"] + config.extra_args + [
                str(config.r_script_path),
                input_path,
            ]

            if config.srun_enabled:
                cmd = ["srun"] + config.srun_args + cmd

            env = {**os.environ}
            if config.r_libs_path:
                env["R_LIBS_USER"] = str(config.r_libs_path)

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
                    f"R script failed (rc={result.returncode}): "
                    f"{result.stderr[-500:] if result.stderr else 'no stderr'}"
                )

            raw = json.loads(result.stdout)
            return self.parse_outputs(raw)

        finally:
            os.unlink(input_path)

    def _execute_rpy2(self, inputs: dict[str, Any]) -> ModelOutput:
        """Execute via rpy2 (in-process)."""
        try:
            import rpy2.robjects as ro
            from rpy2.robjects import pandas2ri
        except ImportError:
            raise ImportError(
                "rpy2 is not installed. Install with: pip install rpy2\n"
                "Alternatively, set use_rpy2=False in RConfig to use subprocess."
            )

        config = self.r_config
        pandas2ri.activate()

        # Source the R script
        ro.r.source(str(config.r_script_path))

        # Convert inputs to R-compatible format and call
        r_inputs = ro.ListVector(inputs)
        result = ro.r["run_model"](r_inputs)

        # Convert back to Python dict
        raw = dict(zip(result.names, [list(x) if len(x) > 1 else x[0] for x in result]))

        return self.parse_outputs(raw)

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
