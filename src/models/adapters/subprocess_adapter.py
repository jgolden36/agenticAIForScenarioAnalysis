"""Generic subprocess adapter for any model executable via command line.

This is the universal fallback: any model can be wrapped in a thin script
that reads JSON, runs the model, and writes JSON — regardless of native language.
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

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the model via subprocess with JSON file I/O.

        Args:
            inputs: Dict from translate_inputs (must contain 'scenario_id' or defaults to 'default').

        Returns:
            ModelOutput with parsed results and execution metadata.
        """
        scenario_id = inputs.get("scenario_id", "default") if isinstance(inputs, dict) else "default"
        config = self.subprocess_config
        run_dir = self._get_run_dir(scenario_id)
        input_path = run_dir / "inputs.json"
        output_path = run_dir / "outputs.json"

        # Write inputs
        input_data = inputs if isinstance(inputs, dict) else {"data": inputs}
        with open(input_path, "w") as f:
            json.dump(input_data, f, default=str)

        # Build command
        cmd = config.command_template.format(
            input_path=str(input_path),
            output_path=str(output_path),
            run_dir=str(run_dir),
        )

        env = {**os.environ, **config.extra_env}

        result = subprocess.run(
            cmd.split(),
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
        }

        if result.returncode != 0:
            raise RuntimeError(
                f"{self.model_id} subprocess failed (rc={result.returncode}): "
                f"{result.stderr[-500:] if result.stderr else 'no stderr'}"
            )

        # Read output
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
        return output
