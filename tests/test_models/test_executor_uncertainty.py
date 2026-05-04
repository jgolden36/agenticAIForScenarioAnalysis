"""Tests for the executor's uncertainty integration.

Verifies that ``ModelExecutor`` honours ``UncertaintyConfig.enabled``
and threads the resulting ``UncertaintyReport`` onto the execution
result so downstream synthesis can read it.
"""

from __future__ import annotations

import asyncio

from src.common.types import (
    AnalyticalLevel,
    CommoditySystem,
    ModelExecutionStatus,
    Scenario,
)
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.executor import ModelExecutor
from src.models.registry import ModelRegistry
from src.models.uncertainty import UncertaintyConfig
from src.pipeline.config import ExecutionConfig


class _LinearAdapter(ModelAdapter):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model_id(self):
        return "linear_uq_adapter"

    @property
    def commodity_system(self):
        return CommoditySystem.OIL

    @property
    def analytical_level(self):
        return AnalyticalLevel.COMMODITY

    @property
    def description(self):
        return "linear test adapter"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        self.calls += 1
        x = float(inputs["x"])
        return ModelOutput(
            model_id=self.model_id,
            outputs={"y": 2.0 * x + 5.0},
        )

    def parse_outputs(self, raw):
        return raw


def test_executor_runs_with_uncertainty_when_enabled():
    adapter = _LinearAdapter()
    registry = ModelRegistry()
    registry.register(adapter)

    cfg = ExecutionConfig(
        max_parallel_models=1,
        uncertainty=UncertaintyConfig(
            enabled=True,
            method="perturbation",
            n_replicates=10,
            perturbation_pct=10.0,
            seed=42,
        ),
    )
    ex = ModelExecutor(registry, cfg)

    try:
        results = asyncio.run(
            ex.execute_all(
                scenario_id=Scenario.A,
                parameter_sets={"linear_uq_adapter": {"x": 100.0}},
            )
        )
    finally:
        ex.shutdown()

    assert len(results) == 1
    r = results[0]
    assert r.status == ModelExecutionStatus.COMPLETED
    assert r.outputs == {"y": 205.0}  # baseline output unchanged
    assert r.uncertainty is not None
    assert r.uncertainty["method"] == "perturbation"
    assert r.uncertainty["n_replicates"] == 10
    estimates = r.uncertainty["estimates"]
    assert "y" in estimates
    quantiles = estimates["y"]["quantiles"]
    assert quantiles["p05"] < quantiles["p95"]
    # Baseline + 10 replicates = 11 total adapter calls.
    assert adapter.calls == 11


def test_executor_skips_uncertainty_when_disabled():
    adapter = _LinearAdapter()
    registry = ModelRegistry()
    registry.register(adapter)

    cfg = ExecutionConfig(
        max_parallel_models=1,
        uncertainty=UncertaintyConfig(enabled=False),
    )
    ex = ModelExecutor(registry, cfg)

    try:
        results = asyncio.run(
            ex.execute_all(
                scenario_id=Scenario.A,
                parameter_sets={"linear_uq_adapter": {"x": 100.0}},
            )
        )
    finally:
        ex.shutdown()

    assert len(results) == 1
    assert results[0].uncertainty is None
    # Only the single baseline run happens.
    assert adapter.calls == 1
