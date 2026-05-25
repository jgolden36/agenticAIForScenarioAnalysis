"""Uncertainty quantification for domain-model adapters.

This module provides a thin perturbation/bootstrap wrapper around any
``ModelAdapter.execute()`` implementation. It is invoked by
``ModelExecutor`` when ``UncertaintyConfig.enabled`` is true and the
adapter did **not** populate ``ModelOutput.uncertainty`` itself.

Design contract:

* **Adapter-native UQ wins.** If ``adapter.execute()`` returns a
  ``ModelOutput`` whose ``uncertainty`` field is already populated
  (e.g. an ensemble adapter that drew posterior samples internally),
  the wrapper is a no-op — we trust the adapter's own quantification.
* **Otherwise, perturbation or bootstrap.** The wrapper re-runs the
  adapter ``n_replicates`` times with multiplicatively perturbed
  numeric inputs and aggregates the per-output-key distribution into
  mean / std / quantiles. Non-numeric inputs and non-numeric outputs
  pass through unchanged.
* **Graceful degradation.** Replicate failures are caught and counted
  in ``UncertaintyReport.failures`` rather than aborting the whole
  uncertainty pass. If too many replicates fail, the report is
  returned with whatever samples succeeded; if zero succeed, the
  baseline ``ModelOutput`` is returned with ``uncertainty=None`` and a
  log warning.
* **Determinism.** A run-level RNG seed (``UncertaintyConfig.seed``)
  controls perturbation noise so two runs with the same seed produce
  identical UQ output.

The wrapper is deliberately schema-agnostic: it inspects the inputs
dict (or namedtuple-like object) for numeric leaves and perturbs
those, leaving structure intact. This works for every adapter in the
inventory without per-adapter code.
"""

from __future__ import annotations

import copy
import math
import random
import statistics
from typing import Any, Callable

from pydantic import BaseModel, Field

from src.common.logging import get_logger
from src.common.types import UncertaintyMethod
from src.models.base import (
    ModelAdapter,
    ModelOutput,
    UncertaintyEstimate,
    UncertaintyReport,
)

logger = get_logger(__name__)


_DEFAULT_QUANTILES: tuple[float, ...] = (0.05, 0.25, 0.50, 0.75, 0.95)


class UncertaintyConfig(BaseModel):
    """Pipeline-wide uncertainty quantification settings."""

    enabled: bool = Field(
        default=False,
        description="Master switch. False disables UQ for the entire pipeline.",
    )
    method: str = Field(
        default=UncertaintyMethod.PERTURBATION.value,
        description=(
            "UQ method. One of 'perturbation', 'bootstrap', or 'none'. "
            "'none' is equivalent to enabled=false. Adapters that "
            "return native uncertainty are not wrapped regardless of "
            "this setting."
        ),
    )
    n_replicates: int = Field(
        default=20,
        ge=1,
        description="Number of perturbed replicate runs per adapter.",
    )
    perturbation_pct: float = Field(
        default=10.0,
        ge=0.0,
        description=(
            "Symmetric multiplicative noise applied to numeric adapter "
            "inputs. e.g. 10.0 -> each numeric leaf is multiplied by "
            "1 + N(0, 0.10)."
        ),
    )
    bootstrap_jitter_pct: float = Field(
        default=5.0,
        ge=0.0,
        description=(
            "Equivalent jitter for the 'bootstrap' method. Bootstrap "
            "without an empirical sample falls back to jitter+resample."
        ),
    )
    quantiles: list[float] = Field(
        default_factory=lambda: list(_DEFAULT_QUANTILES),
        description="Quantile breakpoints to record (between 0 and 1).",
    )
    seed: int | None = Field(
        default=None,
        description=(
            "Random seed applied at the start of each adapter's UQ pass "
            "(combined with the adapter id). None means non-deterministic."
        ),
    )
    max_failure_fraction: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "If more than this fraction of replicates raise, the wrapper "
            "logs a warning but still returns whatever samples succeeded."
        ),
    )


# --------------------------------------------------------------------
# Numeric perturbation of arbitrary nested input structures.
# --------------------------------------------------------------------


def _perturb_value(
    value: Any,
    rng: random.Random,
    sigma: float,
) -> Any:
    """Apply multiplicative Gaussian noise to a numeric leaf.

    ``sigma`` is the standard deviation as a fraction (e.g. 0.10 for
    10% noise). Booleans, strings, and non-finite floats pass through
    unchanged. Lists/tuples/dicts are recursed into.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value == 0.0:
            return value
        factor = 1.0 + rng.gauss(0.0, sigma)
        # Don't flip the sign of an input — clamp at a tiny positive
        # fraction of the original. This is what "perturbation" means
        # in practice for crisis-economics inputs (mb/d, percent
        # shocks, durations) — the structural sign is part of the
        # scenario, only magnitude is uncertain.
        if factor <= 0.0:
            factor = 0.05
        out = value * factor
        return int(round(out)) if isinstance(value, int) else out
    if isinstance(value, dict):
        return {k: _perturb_value(v, rng, sigma) for k, v in value.items()}
    if isinstance(value, list):
        return [_perturb_value(v, rng, sigma) for v in value]
    if isinstance(value, tuple):
        return tuple(_perturb_value(v, rng, sigma) for v in value)
    return value


def perturb_inputs(
    inputs: Any,
    rng: random.Random,
    perturbation_pct: float,
) -> Any:
    """Return a deep-copied perturbed version of ``inputs``.

    The original object is never mutated. Adapters can therefore reuse
    the same translated-input object across replicates without worry.
    """
    sigma = max(0.0, perturbation_pct) / 100.0
    return _perturb_value(copy.deepcopy(inputs), rng, sigma)


# --------------------------------------------------------------------
# Aggregation of replicate outputs into per-key quantile estimates.
# --------------------------------------------------------------------


def _is_numeric(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, float)) and math.isfinite(float(v))


def _quantile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolation quantile (matches numpy.quantile default)."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _quantile_label(q: float) -> str:
    return f"p{int(round(q * 100)):02d}"


def _collect_numeric_keys(samples: list[dict[str, Any]]) -> list[str]:
    """Return output keys whose values are numeric in *every* sample.

    Heterogeneous-type keys (sometimes float, sometimes a list) are
    skipped so the aggregator never produces nonsense quantiles.
    """
    if not samples:
        return []
    keys: list[str] = []
    candidate = set(samples[0].keys())
    for s in samples[1:]:
        candidate &= set(s.keys())
    for k in candidate:
        if k.startswith("_"):
            # Skip provenance / metadata fields like _applied_shocks.
            continue
        if all(_is_numeric(s.get(k)) for s in samples):
            keys.append(k)
    return sorted(keys)


def aggregate_replicates(
    baseline_outputs: dict[str, Any],
    replicate_outputs: list[dict[str, Any]],
    quantiles: list[float],
) -> dict[str, UncertaintyEstimate]:
    """Compute per-output-key mean / std / quantiles across replicates.

    ``baseline_outputs`` is included as one of the samples so the
    central tendency of the distribution is anchored to the unperturbed
    run. Numeric keys missing from any replicate are skipped.
    """
    samples: list[dict[str, Any]] = [baseline_outputs] + list(replicate_outputs)
    keys = _collect_numeric_keys(samples)
    estimates: dict[str, UncertaintyEstimate] = {}
    for key in keys:
        vals = sorted(float(s[key]) for s in samples)
        n = len(vals)
        mean = sum(vals) / n
        std = statistics.pstdev(vals) if n > 1 else 0.0
        q_dict: dict[str, float] = {}
        for q in quantiles:
            q_dict[_quantile_label(q)] = round(_quantile(vals, q), 6)
        estimates[key] = UncertaintyEstimate(
            mean=round(mean, 6),
            std=round(std, 6),
            quantiles=q_dict,
            n_samples=n,
        )
    return estimates


# --------------------------------------------------------------------
# Public entry point: run the adapter N times with perturbed inputs.
# --------------------------------------------------------------------


ExecuteFn = Callable[[Any], ModelOutput]


def maybe_run_with_uncertainty(
    adapter: ModelAdapter,
    native_inputs: Any,
    config: "UncertaintyConfig | None",
    *,
    execute_fn: ExecuteFn | None = None,
) -> ModelOutput:
    """Execute ``adapter`` once, wrapping it in the UQ loop iff enabled.

    This is the single dispatch point every model-execution driver
    (the ``ModelExecutor`` thread/process pools, the LangGraph
    ``_execute_one_model_node``, and the SLURM ``run_model.py`` array
    task) should call so uncertainty quantification fires consistently
    no matter how the pipeline is launched.

    When ``config`` is ``None`` or ``config.enabled`` is false the
    adapter's ``execute()`` is called directly and the returned
    ``ModelOutput.uncertainty`` is left as the adapter produced it.
    """
    if config is not None and config.enabled:
        return run_with_uncertainty(
            adapter, native_inputs, config, execute_fn=execute_fn
        )
    runner = execute_fn or adapter.execute
    return runner(native_inputs)


def run_with_uncertainty(
    adapter: ModelAdapter,
    native_inputs: Any,
    config: UncertaintyConfig,
    *,
    execute_fn: ExecuteFn | None = None,
) -> ModelOutput:
    """Run ``adapter.execute()`` once for the baseline plus N perturbed
    replicates, attach an ``UncertaintyReport`` to the baseline output.

    Parameters:
        adapter: The model adapter to execute.
        native_inputs: Already translated, ready-to-execute inputs.
        config: Uncertainty configuration.
        execute_fn: Optional injection point. Defaults to
            ``adapter.execute``. Tests use this to count calls.

    Returns:
        The baseline ``ModelOutput`` with ``uncertainty`` populated.
        If the adapter returned native uncertainty, that is preserved
        and the wrapper is a no-op.

    Raises:
        Whatever ``adapter.execute()`` raises on the *baseline* run.
        Replicate failures are caught and counted, not propagated.
    """
    runner = execute_fn or adapter.execute

    baseline = runner(native_inputs)
    if not isinstance(baseline, ModelOutput):
        # Adapters that violate the contract are not our problem here —
        # let the executor surface the type error normally.
        return baseline

    if baseline.uncertainty is not None:
        # Adapter-native UQ. Trust it.
        return baseline

    method = (config.method or "").lower()
    if not config.enabled or method in ("", "none", UncertaintyMethod.NONE.value):
        return baseline

    if method not in (
        UncertaintyMethod.PERTURBATION.value,
        UncertaintyMethod.BOOTSTRAP.value,
    ):
        logger.warning(
            "UncertaintyConfig.method=%r is not recognised; skipping UQ for %s.",
            config.method,
            adapter.model_id,
        )
        return baseline

    sigma_pct = (
        config.perturbation_pct
        if method == UncertaintyMethod.PERTURBATION.value
        else config.bootstrap_jitter_pct
    )

    seed_input = config.seed if config.seed is not None else random.randrange(2**31)
    # Mix the model id into the seed so two adapters running in the
    # same scheduler tick get independent noise streams. random.Random
    # only accepts hashable scalars, so combine via a string seed.
    rng = random.Random(f"{seed_input}:{adapter.model_id}")

    replicate_outputs: list[dict[str, Any]] = []
    failures = 0
    for i in range(config.n_replicates):
        perturbed = perturb_inputs(native_inputs, rng, sigma_pct)
        try:
            rep_out = runner(perturbed)
        except Exception as exc:  # noqa: BLE001 — UQ never crashes the run
            failures += 1
            logger.debug(
                "Replicate %d/%d failed for %s: %s",
                i + 1,
                config.n_replicates,
                adapter.model_id,
                exc,
            )
            continue
        if isinstance(rep_out, ModelOutput) and isinstance(rep_out.outputs, dict):
            replicate_outputs.append(rep_out.outputs)

    failure_fraction = (
        failures / config.n_replicates if config.n_replicates else 0.0
    )
    if failure_fraction > config.max_failure_fraction:
        logger.warning(
            "Uncertainty pass for %s saw %d/%d replicate failures "
            "(threshold %.0f%%). Reporting partial estimates.",
            adapter.model_id,
            failures,
            config.n_replicates,
            config.max_failure_fraction * 100.0,
        )

    if not replicate_outputs:
        baseline.uncertainty = UncertaintyReport(
            method=method,
            n_replicates=config.n_replicates,
            perturbation_pct=sigma_pct,
            estimates={},
            notes=(
                "All perturbation replicates failed; uncertainty not "
                "estimated. Treat baseline as a point estimate."
            ),
            failures=failures,
        )
        return baseline

    estimates = aggregate_replicates(
        baseline.outputs,
        replicate_outputs,
        list(config.quantiles) or list(_DEFAULT_QUANTILES),
    )

    baseline.uncertainty = UncertaintyReport(
        method=method,
        n_replicates=config.n_replicates,
        perturbation_pct=sigma_pct,
        estimates=estimates,
        notes=(
            f"Estimated by re-running {adapter.model_id} "
            f"{len(replicate_outputs)}/{config.n_replicates} times with "
            f"+/- {sigma_pct:.1f}% multiplicative input perturbation. "
            "Adapters with native UQ override this."
        ),
        failures=failures,
    )
    return baseline
