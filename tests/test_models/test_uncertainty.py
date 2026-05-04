"""Tests for the perturbation/bootstrap uncertainty engine."""

from __future__ import annotations

import math
import random

import pytest

from src.common.types import (
    AnalyticalLevel,
    CommoditySystem,
    UncertaintyMethod,
)
from src.models.base import (
    ModelAdapter,
    ModelOutput,
    UncertaintyEstimate,
    UncertaintyReport,
    ValidationResult,
)
from src.models.uncertainty import (
    UncertaintyConfig,
    aggregate_replicates,
    perturb_inputs,
    run_with_uncertainty,
)


class _LinearAdapter(ModelAdapter):
    """y = slope * x + intercept; constant_field never moves."""

    def __init__(self, slope: float = 2.0, intercept: float = 5.0) -> None:
        self.slope = slope
        self.intercept = intercept
        self.calls = 0

    @property
    def model_id(self) -> str:
        return "linear_toy"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "linear toy adapter"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        self.calls += 1
        x = float(inputs["x"])
        return ModelOutput(
            model_id=self.model_id,
            outputs={
                "y": self.slope * x + self.intercept,
                "constant_field": "stable",
            },
        )

    def parse_outputs(self, raw):
        return raw


class _NativeUQAdapter(ModelAdapter):
    """Adapter that returns its own UncertaintyReport — wrapper must skip."""

    @property
    def model_id(self) -> str:
        return "native_uq"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "native UQ adapter"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        return ModelOutput(
            model_id=self.model_id,
            outputs={"y": 42.0},
            uncertainty=UncertaintyReport(
                method=UncertaintyMethod.NATIVE.value,
                n_replicates=500,
                estimates={
                    "y": UncertaintyEstimate(
                        mean=42.0,
                        std=0.5,
                        quantiles={"p05": 41.1, "p50": 42.0, "p95": 42.9},
                        n_samples=500,
                    )
                },
                notes="native posterior draws",
            ),
        )

    def parse_outputs(self, raw):
        return raw


class _FlakyAdapter(ModelAdapter):
    """Crashes every other replicate so we can exercise failure counting."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def model_id(self) -> str:
        return "flaky"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.OIL

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return "flaky adapter"

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        self.calls += 1
        if self.calls > 1 and self.calls % 2 == 0:
            raise RuntimeError("transient failure")
        return ModelOutput(model_id=self.model_id, outputs={"y": float(inputs["x"])})

    def parse_outputs(self, raw):
        return raw


# --------------------------------------------------------------------
# perturb_inputs
# --------------------------------------------------------------------


def test_perturb_inputs_does_not_mutate_original():
    rng = random.Random(0)
    original = {"x": 100.0, "nested": {"y": [1.0, 2.0, 3.0]}}
    snapshot = {"x": 100.0, "nested": {"y": [1.0, 2.0, 3.0]}}
    out = perturb_inputs(original, rng, perturbation_pct=10.0)
    assert original == snapshot, "perturb_inputs must not mutate input"
    assert out is not original
    assert out["nested"] is not original["nested"]


def test_perturb_inputs_preserves_non_numeric_leaves():
    rng = random.Random(0)
    inputs = {
        "x": 100.0,
        "label": "scenario_A",
        "flag": True,
        "count": 7,  # int — should be perturbed but rounded
    }
    out = perturb_inputs(inputs, rng, perturbation_pct=20.0)
    assert out["label"] == "scenario_A"
    assert out["flag"] is True
    assert isinstance(out["count"], int)


def test_perturb_inputs_clamps_sign_flips():
    rng = random.Random(123)
    # Huge sigma + positive value: factor sometimes goes negative,
    # which the implementation must clamp positive.
    out = perturb_inputs({"x": 5.0}, rng, perturbation_pct=500.0)
    assert out["x"] > 0.0


def test_perturb_inputs_zero_value_passes_through():
    rng = random.Random(0)
    out = perturb_inputs({"x": 0.0, "y": 10.0}, rng, perturbation_pct=10.0)
    assert out["x"] == 0.0


# --------------------------------------------------------------------
# aggregate_replicates
# --------------------------------------------------------------------


def test_aggregate_replicates_basic_quantiles():
    baseline = {"y": 10.0}
    replicates = [{"y": float(v)} for v in range(1, 11)]
    estimates = aggregate_replicates(baseline, replicates, [0.05, 0.5, 0.95])
    assert "y" in estimates
    est = estimates["y"]
    # 11 samples: baseline (10.0) + replicates 1..10
    assert est.n_samples == 11
    expected_mean = (10.0 + sum(range(1, 11))) / 11
    assert math.isclose(est.mean, expected_mean, rel_tol=1e-6)
    # Sorted = [1,2,3,4,5,6,7,8,9,10,10]; median is 6.
    assert math.isclose(est.quantiles["p50"], 6.0, abs_tol=0.5)
    assert est.quantiles["p05"] < est.quantiles["p95"]


def test_aggregate_replicates_skips_heterogeneous_keys():
    baseline = {"y": 1.0, "tag": "a"}
    replicates = [
        {"y": 2.0, "tag": "b"},
        {"y": 3.0, "tag": "c"},
    ]
    estimates = aggregate_replicates(baseline, replicates, [0.5])
    assert "y" in estimates
    assert "tag" not in estimates


def test_aggregate_replicates_skips_underscore_keys():
    baseline = {"y": 1.0, "_provenance": 1.0}
    replicates = [{"y": 2.0, "_provenance": 1.0}]
    estimates = aggregate_replicates(baseline, replicates, [0.5])
    assert "y" in estimates
    assert "_provenance" not in estimates


# --------------------------------------------------------------------
# run_with_uncertainty
# --------------------------------------------------------------------


def test_run_with_uncertainty_disabled_returns_baseline():
    adapter = _LinearAdapter()
    cfg = UncertaintyConfig(enabled=False)
    out = run_with_uncertainty(adapter, {"x": 10.0}, cfg)
    assert out.uncertainty is None
    assert adapter.calls == 1


def test_run_with_uncertainty_perturbation_produces_band():
    adapter = _LinearAdapter(slope=2.0, intercept=5.0)
    cfg = UncertaintyConfig(
        enabled=True,
        method=UncertaintyMethod.PERTURBATION.value,
        n_replicates=80,
        perturbation_pct=10.0,
        seed=42,
    )
    out = run_with_uncertainty(adapter, {"x": 100.0}, cfg)
    assert out.uncertainty is not None
    assert out.uncertainty.method == UncertaintyMethod.PERTURBATION.value
    assert out.uncertainty.n_replicates == 80
    assert adapter.calls == 81  # baseline + replicates
    est = out.uncertainty.estimates["y"]
    # Linear model with 10% input noise: output spread should be on
    # the order of 10% of the baseline (y_baseline = 205).
    assert 5.0 < est.std < 50.0
    assert est.quantiles["p05"] < est.quantiles["p95"]
    # The non-numeric output must be excluded.
    assert "constant_field" not in out.uncertainty.estimates


def test_run_with_uncertainty_native_uq_is_preserved():
    adapter = _NativeUQAdapter()
    cfg = UncertaintyConfig(
        enabled=True,
        method=UncertaintyMethod.PERTURBATION.value,
        n_replicates=20,
        seed=1,
    )
    # Track calls — wrapper must NOT re-run an adapter that already
    # populated uncertainty.
    calls = {"n": 0}
    real_execute = adapter.execute

    def counting_execute(inputs):
        calls["n"] += 1
        return real_execute(inputs)

    out = run_with_uncertainty(adapter, {}, cfg, execute_fn=counting_execute)
    assert calls["n"] == 1
    assert out.uncertainty is not None
    assert out.uncertainty.method == UncertaintyMethod.NATIVE.value


def test_run_with_uncertainty_is_deterministic_with_seed():
    cfg = UncertaintyConfig(
        enabled=True, method="perturbation",
        n_replicates=30, perturbation_pct=10.0, seed=7,
    )
    a = run_with_uncertainty(_LinearAdapter(), {"x": 100.0}, cfg)
    b = run_with_uncertainty(_LinearAdapter(), {"x": 100.0}, cfg)
    ay, by = a.uncertainty.estimates["y"], b.uncertainty.estimates["y"]
    assert (ay.mean, ay.std, ay.quantiles) == (by.mean, by.std, by.quantiles)


def test_run_with_uncertainty_counts_failures():
    adapter = _FlakyAdapter()
    cfg = UncertaintyConfig(
        enabled=True, method="perturbation",
        n_replicates=10, perturbation_pct=10.0, seed=5,
    )
    out = run_with_uncertainty(adapter, {"x": 100.0}, cfg)
    assert out.uncertainty is not None
    assert out.uncertainty.failures > 0
    # Baseline succeeded, so the report still has at least some
    # estimates from the surviving replicates (plus the baseline).
    assert "y" in out.uncertainty.estimates


def test_run_with_uncertainty_unknown_method_logs_and_skips():
    adapter = _LinearAdapter()
    cfg = UncertaintyConfig(enabled=True, method="bogus", n_replicates=5)
    out = run_with_uncertainty(adapter, {"x": 10.0}, cfg)
    assert out.uncertainty is None
    assert adapter.calls == 1


def test_run_with_uncertainty_method_none_returns_baseline():
    adapter = _LinearAdapter()
    cfg = UncertaintyConfig(enabled=True, method="none", n_replicates=5)
    out = run_with_uncertainty(adapter, {"x": 10.0}, cfg)
    assert out.uncertainty is None
    assert adapter.calls == 1
