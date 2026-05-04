"""Tests for pipeline configuration."""

import tempfile
from pathlib import Path

from src.pipeline.config import PipelineConfig


def test_default_config():
    """Test default configuration values."""
    config = PipelineConfig()
    assert config.llm.provider == "anthropic"
    assert config.llm.temperature == 0.0
    assert config.execution.max_parallel_models == 4
    assert config.consistency.price_tolerance_pct == 20.0
    # 4 matrix quadrants (A-D) + 1 prescribed tail-risk (E: infrastructure_collapse)
    assert config.num_scenarios == 5


def test_config_from_yaml():
    """Test loading configuration from a YAML file."""
    yaml_content = """
llm:
  provider: openai
  temperature: 0.5
execution:
  max_parallel_models: 8
num_scenarios: 3
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = PipelineConfig.from_yaml(f.name)

    assert config.llm.provider == "openai"
    assert config.llm.temperature == 0.5
    assert config.execution.max_parallel_models == 8
    assert config.num_scenarios == 3
    # Defaults preserved for unspecified fields
    assert config.consistency.price_tolerance_pct == 20.0
