"""AnyLogic adapter base class for agent-based models.

Executes exported standalone Java applications (JARs) via subprocess.
Supports multiple stochastic replications with statistical aggregation.

Applies to: Argonne Helium ABM.
"""

from __future__ import annotations

import json
import os
import subprocess
from abc import abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.base import ModelAdapter, ModelOutput


class AnyLogicConfig(BaseModel):
    """Configuration for AnyLogic-based model adapters."""

    model_dir: Path = Field(description="Directory containing the exported AnyLogic model")
    model_name: str = Field(description="Base name of the exported model (used to find startup script)")
    java_home: Path | None = Field(
        default=None, description="Path to JRE/JDK 11+ (defaults to system JAVA_HOME)"
    )
    max_memory_mb: int = Field(default=4096, description="Max JVM heap size in MB")
    timeout_seconds: int = 3600
    num_replications: int = Field(
        default=30,
        description=(
            "Number of stochastic replications to run. ABMs are inherently "
            "stochastic; run multiple replications and aggregate."
        ),
    )
    use_cloud_api: bool = Field(
        default=False,
        description="Use AnyLogic Cloud REST API instead of local execution.",
    )
    cloud_api_url: str | None = None
    cloud_api_key: str | None = None


class AnyLogicAdapter(ModelAdapter):
    """Base class for AnyLogic-based agent-based model adapters.

    Executes the model via an exported standalone Java application (JAR).
    The exported model must be instrumented for headless use: accept
    command-line parameters, run without GUI, and write results to files.

    Subclasses implement:
    - build_cli_args(): construct command-line arguments for the model
    - aggregate_replications(): combine results from multiple stochastic runs
    - validate_inputs(): parameter validation

    NOTE: Export requires AnyLogic Professional license. The free Personal
    Learning Edition cannot export standalone applications.
    """

    def __init__(self, config: AnyLogicConfig | None = None) -> None:
        self._config = config

    @property
    def anylogic_config(self) -> AnyLogicConfig:
        if self._config is None:
            raise ValueError(
                f"{self.__class__.__name__} requires an AnyLogicConfig. "
                "Pass it via __init__ or override anylogic_config."
            )
        return self._config

    def _get_run_dir(self, scenario_id: str, replication: int = 0) -> Path:
        run_dir = (
            self.anylogic_config.model_dir
            / "runs"
            / f"{self.model_id}_{scenario_id}_rep{replication}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    @abstractmethod
    def build_cli_args(self, params: dict[str, Any]) -> list[str]:
        """Build CLI arguments for the exported AnyLogic model.

        Args:
            params: Validated parameter dictionary.

        Returns:
            List of command-line arguments to pass to the startup script.
        """

    @abstractmethod
    def aggregate_replications(self, replication_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate results across stochastic replications.

        Typically computes mean, std, and confidence intervals.

        Args:
            replication_results: List of result dicts, one per replication.

        Returns:
            Aggregated results dict.
        """

    def translate_inputs(self, params: dict[str, Any]) -> Any:
        return params

    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the AnyLogic model with multiple replications."""
        config = self.anylogic_config
        scenario_id = inputs.get("scenario_id", "default") if isinstance(inputs, dict) else "default"

        replication_results = []
        for rep in range(config.num_replications):
            run_dir = self._get_run_dir(scenario_id, rep)

            # Write inputs
            input_path = run_dir / "scenario_params.json"
            with open(input_path, "w") as f:
                json.dump({**inputs, "replication": rep, "random_seed": rep + 42}, f, default=str)

            # Build startup command
            startup_script = config.model_dir / f"{config.model_name}_linux.sh"
            if not startup_script.exists():
                startup_script = config.model_dir / f"{config.model_name}.sh"

            cli_args = self.build_cli_args(inputs)

            env = {**os.environ}
            if config.java_home:
                env["JAVA_HOME"] = str(config.java_home)
            env["JAVA_OPTS"] = f"-Xmx{config.max_memory_mb}m"

            result = subprocess.run(
                [str(startup_script), str(input_path)] + cli_args,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                cwd=str(config.model_dir),
                env=env,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"AnyLogic replication {rep} failed (rc={result.returncode}): "
                    f"{result.stderr[-500:] if result.stderr else 'no stderr'}"
                )

            # Read output
            output_path = run_dir / "results.json"
            if not output_path.exists():
                raise FileNotFoundError(
                    f"Replication {rep}: expected output at {output_path}"
                )

            with open(output_path) as f:
                replication_results.append(json.load(f))

        # Aggregate across replications
        aggregated = self.aggregate_replications(replication_results)

        return ModelOutput(
            model_id=self.model_id,
            outputs=aggregated,
            metadata={
                "num_replications": config.num_replications,
                "scenario_id": scenario_id,
            },
        )

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
