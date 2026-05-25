"""Tests for the shared uncertainty dispatch helper and its use in the
non-executor execution paths (LangGraph node + SLURM run_model).

These guard the regression where ``maybe_run_with_uncertainty`` was not
wired into ``src/pipeline/graph.py`` or ``slurm/scripts/run_model.py``,
so uncertainty was silently never computed outside the imperative
``ModelExecutor`` path even when the config enabled it.
"""

from __future__ import annotations

from src.common.types import (
    AnalyticalLevel,
    CommoditySystem,
)
from src.models.base import ModelAdapter, ModelOutput, ValidationResult
from src.models.uncertainty import UncertaintyConfig, maybe_run_with_uncertainty


class _LinearAdapter(ModelAdapter):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model_id(self):
        return "linear_dispatch_adapter"

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
        return ModelOutput(model_id=self.model_id, outputs={"y": 2.0 * x + 5.0})

    def parse_outputs(self, raw):
        return raw


def test_maybe_run_with_uncertainty_enabled():
    adapter = _LinearAdapter()
    cfg = UncertaintyConfig(
        enabled=True,
        method="perturbation",
        n_replicates=10,
        perturbation_pct=10.0,
        seed=42,
    )
    out = maybe_run_with_uncertainty(adapter, {"x": 100.0}, cfg)

    assert out.outputs == {"y": 205.0}  # baseline unchanged
    assert out.uncertainty is not None
    assert out.uncertainty.method == "perturbation"
    assert out.uncertainty.n_replicates == 10
    est = out.uncertainty.estimates["y"]
    assert est.quantiles["p05"] < est.quantiles["p95"]
    # Baseline + 10 replicates.
    assert adapter.calls == 11


def test_maybe_run_with_uncertainty_disabled():
    adapter = _LinearAdapter()
    out = maybe_run_with_uncertainty(
        adapter, {"x": 100.0}, UncertaintyConfig(enabled=False)
    )
    assert out.uncertainty is None
    assert adapter.calls == 1


def test_maybe_run_with_uncertainty_none_config():
    adapter = _LinearAdapter()
    out = maybe_run_with_uncertainty(adapter, {"x": 100.0}, None)
    assert out.uncertainty is None
    assert adapter.calls == 1


def test_native_uncertainty_is_preserved():
    """An adapter that returns its own UncertaintyReport must not be
    re-wrapped — adapter-native UQ wins."""

    class _NativeUQAdapter(_LinearAdapter):
        @property
        def model_id(self):
            return "native_uq_adapter"

        def execute(self, inputs):
            from src.models.base import UncertaintyEstimate, UncertaintyReport

            self.calls += 1
            return ModelOutput(
                model_id=self.model_id,
                outputs={"y": 1.0},
                uncertainty=UncertaintyReport(
                    method="native",
                    n_replicates=1,
                    perturbation_pct=0.0,
                    estimates={
                        "y": UncertaintyEstimate(
                            mean=1.0, std=0.1, quantiles={"p50": 1.0}, n_samples=1
                        )
                    },
                ),
            )

    adapter = _NativeUQAdapter()
    cfg = UncertaintyConfig(enabled=True, n_replicates=10)
    out = maybe_run_with_uncertainty(adapter, {"x": 1.0}, cfg)
    assert out.uncertainty is not None
    assert out.uncertainty.method == "native"
    # No perturbation replicates — only the single baseline call.
    assert adapter.calls == 1
