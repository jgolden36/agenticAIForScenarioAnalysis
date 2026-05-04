"""Pipeline configuration and constants."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from src.models.uncertainty import UncertaintyConfig


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "anthropic"
    model: str | None = None
    temperature: float = 0.0
    max_concurrency: int = Field(
        default=8,
        description="Max concurrent LLM requests (rate-limit protection)",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL for local LLM servers (vLLM, Ollama, TGI)",
    )
    extra_kwargs: dict[str, Any] = Field(default_factory=dict)


class GPUConfig(BaseModel):
    """GPU resource configuration for the cluster."""

    available_devices: list[int] = Field(
        default_factory=list,
        description=(
            "CUDA device indices available to this process. "
            "Empty list means auto-detect from CUDA_VISIBLE_DEVICES."
        ),
    )
    memory_per_device_gb: float = Field(
        default=0.0,
        description="GPU memory per device in GB (0 = auto-detect at runtime)",
    )
    reserve_for_llm: int = Field(
        default=0,
        description="Number of GPU devices reserved for local LLM inference",
    )


class ExecutionConfig(BaseModel):
    """Model execution configuration."""

    max_parallel_models: int = Field(
        default=4,
        description="Max domain models running concurrently within a single process",
    )
    default_timeout_seconds: int = 3600
    retry_failed_models: bool = False
    max_retries: int = Field(default=2, description="Retry count for failed models")
    capture_stderr: bool = True
    worker_type: Literal["thread", "process"] = Field(
        default="thread",
        description=(
            "Executor backend. 'thread' for I/O-bound models (subprocess, API calls). "
            "'process' for CPU-bound Python-native models (avoids GIL contention)."
        ),
    )
    cpu_threads_per_model: int = Field(
        default=1,
        description="CPU threads allocated per model (passed via OMP_NUM_THREADS etc.)",
    )
    gpu: GPUConfig = Field(default_factory=GPUConfig)
    srun_enabled: bool = Field(
        default=False,
        description="Wrap subprocess calls with srun for SLURM-aware execution",
    )
    srun_args: list[str] = Field(
        default_factory=list,
        description="Extra srun arguments (e.g., ['--exclusive', '--mem=32G'])",
    )
    uncertainty: UncertaintyConfig = Field(
        default_factory=UncertaintyConfig,
        description=(
            "Uncertainty quantification settings. When enabled, the "
            "executor wraps each adapter's execute() in a perturbation/"
            "bootstrap loop unless the adapter already returned native UQ."
        ),
    )


class OutputConfig(BaseModel):
    """Output directory configuration."""

    base_dir: Path = Path("data")
    inputs_dir: Path = Path("data/inputs")
    outputs_dir: Path = Path("data/outputs")
    reports_dir: Path = Path("data/reports")


class ConsistencyConfig(BaseModel):
    """Thresholds for cross-model consistency checks."""

    price_tolerance_pct: float = 20.0
    quantity_tolerance_pct: float = 15.0
    flag_on_missing_model: bool = True


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    consistency: ConsistencyConfig = Field(default_factory=ConsistencyConfig)
    uncertainty: UncertaintyConfig = Field(default_factory=UncertaintyConfig)
    num_scenarios: int = 5  # 4 matrix quadrants (A-D) + 1 prescribed tail-risk (E: infrastructure_collapse)

    @model_validator(mode="after")
    def _sync_uncertainty_to_execution(self) -> PipelineConfig:
        """Keep ExecutionConfig.uncertainty in sync with the top-level config.

        Users configure ``uncertainty:`` once at the top level of the
        YAML; the executor reads it via its own ``ExecutionConfig``.
        Mirror the top-level setting onto ``execution.uncertainty``
        whenever the executor's copy is still at its defaults (i.e. the
        user didn't override it explicitly).
        """
        exec_unc = self.execution.uncertainty
        if exec_unc == UncertaintyConfig():
            self.execution.uncertainty = self.uncertainty
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> PipelineConfig:
        """Load pipeline configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
