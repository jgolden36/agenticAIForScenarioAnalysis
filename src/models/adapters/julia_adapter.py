"""Julia adapter base class for models using juliacall (PythonCall.jl).

Provides in-process Julia execution with zero-copy array transfer for
numeric data. Falls back to subprocess if juliacall is unavailable.

IMPORTANT: juliacall must be imported BEFORE torch, matplotlib, or any
C-extension library to avoid libstdc++ version conflicts.
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


class JuliaConfig(BaseModel):
    """Configuration for Julia-based model adapters."""

    julia_project_path: Path = Field(
        description="Path to the Julia project environment (contains Project.toml)"
    )
    julia_script_path: Path | None = Field(
        default=None,
        description="Path to the Julia script to execute (for subprocess fallback)",
    )
    use_juliacall: bool = Field(
        default=True,
        description="Use juliacall (in-process) vs subprocess. Prefer juliacall for performance.",
    )
    timeout_seconds: int = 3600
    sysimage_path: Path | None = Field(
        default=None,
        description="Path to a custom sysimage (from PackageCompiler.jl) to eliminate JIT latency.",
    )
    packages: list[str] = Field(
        default_factory=list,
        description="Julia packages to load (e.g., ['MPSGE', 'JuMP'])",
    )


class JuliaAdapter(ModelAdapter):
    """Base class for Julia-based model adapters.

    Uses juliacall for in-process execution with zero-copy NumPy array
    transfer. Falls back to subprocess if juliacall is not available or
    if use_juliacall is False.

    Subclasses implement julia_function_name() to specify which Julia
    function to call, and translate_inputs_for_julia() to prepare arguments.

    Critical: Import juliacall BEFORE torch or matplotlib to avoid
    libstdc++ version conflicts that cause random segfaults.
    """

    # Class-level Julia runtime singleton (shared across all Julia adapters)
    _jl = None
    _jl_initialized = False

    def __init__(self, config: JuliaConfig | None = None) -> None:
        self._config = config

    @property
    def julia_config(self) -> JuliaConfig:
        if self._config is None:
            raise ValueError(
                f"{self.__class__.__name__} requires a JuliaConfig. "
                "Pass it via __init__ or override julia_config."
            )
        return self._config

    @classmethod
    def _ensure_julia(cls, config: JuliaConfig) -> Any:
        """Initialize the Julia runtime singleton.

        Must be called before any Julia operations. Loads specified packages.
        """
        if cls._jl is not None:
            return cls._jl

        try:
            from juliacall import Main as jl  # noqa: F811

            # Activate the project environment
            jl.seval(f'import Pkg; Pkg.activate("{config.julia_project_path}")')

            # Load required packages
            for pkg in config.packages:
                jl.seval(f"using {pkg}")

            cls._jl = jl
            cls._jl_initialized = True
            return jl

        except ImportError:
            raise ImportError(
                "juliacall is not installed. Install with: pip install juliacall\n"
                "Alternatively, set use_juliacall=False in JuliaConfig to use subprocess."
            )

    @property
    @abstractmethod
    def julia_function_name(self) -> str:
        """The Julia function to call for model execution."""

    @abstractmethod
    def translate_inputs_for_julia(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert validated parameters to Julia-compatible arguments.

        Return a dict of keyword arguments to pass to the Julia function.
        NumPy arrays are transferred zero-copy via juliacall.
        """

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return self.translate_inputs_for_julia(params)

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the Julia model via juliacall or subprocess fallback."""
        config = self.julia_config

        if config.use_juliacall:
            return self._execute_juliacall(inputs)
        else:
            return self._execute_subprocess(inputs)

    def _execute_juliacall(self, inputs: dict[str, Any]) -> ModelOutput:
        """Execute via juliacall (in-process, zero-copy arrays)."""
        config = self.julia_config
        jl = self._ensure_julia(config)

        # Call the Julia function with keyword arguments
        julia_fn = jl.seval(self.julia_function_name)
        result = julia_fn(**inputs)

        # Convert Julia result to Python dict
        # Subclasses can override parse_outputs for custom conversion
        import numpy as np

        if hasattr(result, "keys"):
            # Dict-like Julia result
            raw = {}
            for key in result.keys():
                val = result[key]
                # Convert Julia arrays to numpy (zero-copy view)
                if hasattr(val, "__array__"):
                    raw[str(key)] = np.asarray(val).tolist()
                else:
                    raw[str(key)] = val
        else:
            raw = {"result": result}

        return self.parse_outputs(raw)

    def _execute_subprocess(self, inputs: dict[str, Any]) -> ModelOutput:
        """Execute via Julia subprocess (fallback)."""
        config = self.julia_config

        if config.julia_script_path is None:
            raise ValueError(
                "julia_script_path must be set in JuliaConfig for subprocess execution."
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(inputs, f, default=str)
            input_path = f.name

        try:
            cmd = ["julia"]
            if config.sysimage_path:
                cmd.extend(["--sysimage", str(config.sysimage_path)])
            cmd.extend([
                f"--project={config.julia_project_path}",
                str(config.julia_script_path),
                input_path,
            ])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"Julia subprocess failed (rc={result.returncode}): "
                    f"{result.stderr[-500:] if result.stderr else 'no stderr'}"
                )

            raw = json.loads(result.stdout)
            return self.parse_outputs(raw)

        finally:
            os.unlink(input_path)
