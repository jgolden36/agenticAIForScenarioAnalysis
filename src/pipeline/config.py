"""Pipeline configuration and constants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "anthropic"
    model: str | None = None
    temperature: float = 0.0
    extra_kwargs: dict[str, Any] = Field(default_factory=dict)


class ExecutionConfig(BaseModel):
    """Model execution configuration."""

    max_parallel_models: int = 4
    default_timeout_seconds: int = 3600
    retry_failed_models: bool = False
    capture_stderr: bool = True


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
    num_scenarios: int = 4

    @classmethod
    def from_yaml(cls, path: str | Path) -> PipelineConfig:
        """Load pipeline configuration from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
