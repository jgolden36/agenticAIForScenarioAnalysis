"""Shared pieces for the robustness checks (zero-shock ladder, elasticity LHS, open-loop gap).

Ported in spirit from the AgResilience robustness suite (E0 zero-shock and
linearity ladder, E3 open loop vs fixed point, E9 Latin-hypercube SSA).

The checks run adapters **in-process and directly** (validate -> translate ->
execute), not through ``ModelExecutor``: no process pools, no input
perturbation, no retries. The tier order and the Algorithm 1 step 11
forwarding barrier are reproduced with the same functions the pipeline uses
(``compute_downstream_inputs`` / ``merge_into_params``), so a chain run here
gives the same inputs as the deterministic baseline.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slurm" / "scripts"))

ROBUSTNESS_DIR = ROOT / "configs" / "robustness"
DEFAULT_BASELINE = ROOT / "configs" / "baselines" / "hormuz_2026_analyst.yaml"

# Fixed categorical order (dataviz reference palette, light mode; first three
# slots validate all-pairs, so panels never carry more than three series).
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e4e3df"

# Outputs that are changes / impacts (zero at no shock); anything else is a level.
_CHANGE_TOKENS = ("pct", "change", "impact", "loss", "gap", "delta", "deviation", "surplus")


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def is_change_output(key: str) -> bool:
    k = key.lower()
    return any(t in k for t in _CHANGE_TOKENS)


def baseline_cells(baseline_path: Path = DEFAULT_BASELINE) -> dict[str, dict[str, dict[str, Any]]]:
    """``{scenario: {model: params}}`` from the analyst baseline."""
    from run_deterministic_baseline import baseline_parameter_sets, load_baseline  # type: ignore

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for sid, mid, params in baseline_parameter_sets(load_baseline(baseline_path)):
        out.setdefault(sid, {})[mid] = params
    return out


def scenario_order(baseline_path: Path = DEFAULT_BASELINE) -> list[str]:
    return [s["scenario_id"] for s in load_yaml(baseline_path)["scenarios"]]


def headline_keys() -> dict[str, list[str]]:
    from src.synthesis import templated

    for name in ("HEADLINE_OUTPUTS", "HEADLINE_KEYS", "_HEADLINE_KEYS", "_HEADLINE_OUTPUTS"):
        table = getattr(templated, name, None)
        if isinstance(table, dict):
            return {k: list(v) for k, v in table.items()}
    raise RuntimeError("src/synthesis/templated.py has no headline-output table")


def run_adapter(adapter: Any, params: dict[str, Any]) -> dict[str, Any]:
    """One execution -> ``{status, outputs, error}``; never raises."""
    try:
        validation = adapter.validate_inputs(params)
        if not validation.valid:
            return {"status": "invalid", "outputs": {}, "error": "; ".join(validation.errors)}
        output = adapter.execute(adapter.translate_inputs(params))
        return {"status": "completed", "outputs": dict(output.outputs or {}), "error": None}
    except NotImplementedError as e:
        return {"status": "skipped", "outputs": {}, "error": str(e)[:300]}
    except Exception as e:  # noqa: BLE001 — a robustness sweep records failures
        return {"status": "failed", "outputs": {}, "error": f"{type(e).__name__}: {e}"[:300]}


def build_registry(use_configs: bool = True) -> Any:
    from src.models.registry import build_default_registry, default_config_dir

    return build_default_registry(default_config_dir() if use_configs else None)


def level_groups(registry: Any, model_ids: Iterable[str]) -> list[list[str]]:
    """Model ids grouped by analytical level, in pipeline order."""
    from src.common.types import ANALYTICAL_LEVEL_ORDER

    wanted = set(model_ids)
    groups: list[list[str]] = []
    for level in ANALYTICAL_LEVEL_ORDER:
        ids = sorted(a.model_id for a in registry.get_by_analytical_level(level) if a.model_id in wanted)
        if ids:
            groups.append(ids)
    return groups


def run_chain(
    registry: Any,
    params_by_model: dict[str, dict[str, Any]],
    scenario_id: str,
    model_ids: Iterable[str],
    forwarding: bool = True,
    mapping: Any = None,
) -> dict[str, dict[str, Any]]:
    """Run ``model_ids`` level by level for one scenario, forwarding between levels.

    Returns ``{model_id: {status, outputs, error, inputs, overrides}}``.
    """
    from src.pipeline.upstream_forwarding import compute_downstream_inputs, load_mapping, merge_into_params

    mapping = mapping if mapping is not None else load_mapping()
    results: dict[str, dict[str, Any]] = {}
    for group in level_groups(registry, model_ids):
        upstream = [{"scenario_id": scenario_id, "model_id": m, "status": r["status"], "outputs": r["outputs"]}
                    for m, r in results.items()]
        for mid in group:
            if mid not in params_by_model:
                continue
            params = copy.deepcopy(params_by_model[mid])
            overrides: list[dict[str, Any]] = []
            if forwarding:
                computed = compute_downstream_inputs(scenario_id, upstream, mapping, target_models={mid})
                params, recs = merge_into_params(mid, params, computed.get(mid, []))
                overrides = [r.to_dict() for r in recs]
            res = run_adapter(registry.get(mid), params)
            res.update(inputs=params, overrides=overrides)
            results[mid] = res
    return results


# ------------------------------------------------------------- overrides

class ConstantOverride:
    """Temporarily multiply module-level constants; always restores them."""

    def __init__(self, knobs: list[dict[str, Any]], multipliers: dict[str, float]) -> None:
        self.knobs = knobs
        self.multipliers = multipliers
        self._saved: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> "ConstantOverride":
        import importlib

        for knob in self.knobs:
            if knob.get("kind", "constant") != "constant" or knob["name"] not in self.multipliers:
                continue
            mod = importlib.import_module(knob["module"])
            attr = knob["attribute"]
            original = getattr(mod, attr)
            self._saved.append((mod, attr, original))
            setattr(mod, attr, original * self.multipliers[knob["name"]])
        return self

    def __exit__(self, *exc: Any) -> None:
        for mod, attr, original in reversed(self._saved):
            setattr(mod, attr, original)
        self._saved.clear()


def mapping_with_overrides(mapping: Any, knobs: list[dict[str, Any]], multipliers: dict[str, float]) -> Any:
    """Copy of the forwarding mapping with transform kwargs (e.g. ``elasticity``) scaled."""
    out = copy.copy(mapping)
    out.by_model = dict(mapping.by_model)
    for knob in knobs:
        if knob.get("kind") != "forwarding" or knob["name"] not in multipliers:
            continue
        model, param, idx, fld = knob["model"], knob["param"], int(knob.get("source_index", 0)), knob["field"]
        rules = list(out.by_model.get(model, []))
        for i, rule in enumerate(rules):
            if rule.target_param != param and f"{rule.target_param}__{rule.target_key}" != param:
                continue
            sources = list(rule.sources)
            spec = sources[idx]
            base = getattr(spec, fld)
            if base is None:
                raise ValueError(f"forwarding knob {knob['name']}: {model}.{param}[{idx}].{fld} is unset")
            sources[idx] = dataclasses.replace(spec, **{fld: base * multipliers[knob["name"]]})
            rules[i] = dataclasses.replace(rule, sources=tuple(sources))
        out.by_model[model] = rules
    return out


def latin_hypercube(n: int, names: list[str], low: float, high: float, seed: int) -> list[dict[str, float]]:
    """Seeded LHS: each dimension's n strata are hit exactly once (numpy only)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    cols = []
    for _ in names:
        u = (rng.permutation(n) + rng.random(n)) / n
        cols.append(low + u * (high - low))
    return [dict(zip(names, map(float, row))) for row in zip(*cols)]


def first_order(xs: Iterable[float], ys: Iterable[float], bins: int = 10) -> float:
    """Binned first-order sensitivity index Var(E[Y|X]) / Var(Y).

    Port of AgResilience ``src/experiments/viz/e9_ssa.py::first_order``.
    """
    import numpy as np

    x, y = np.asarray(list(xs), float), np.asarray(list(ys), float)
    # A constant output can still have a tiny nonzero np.var from rounding in
    # the mean; treat spread at round-off level as no variance.
    if len(y) < 3 * bins or np.ptp(y) <= 1e-12 * max(1.0, float(np.max(np.abs(y)))):
        return float("nan")
    edges = np.quantile(x, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, bins - 1)
    means = np.array([y[idx == b].mean() for b in range(bins) if (idx == b).any()])
    counts = np.array([(idx == b).sum() for b in range(bins) if (idx == b).any()])
    return float(np.sum(counts * (means - y.mean()) ** 2) / len(y) / np.var(y))


def style_axes(ax: Any) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
        ax.spines[side].set_linewidth(0.6)
    ax.tick_params(colors=INK_MUTED, labelsize=7, width=0.6)
    ax.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        if math.isnan(v):
            return "nan"
        return f"{v:.{digits}g}"
    return str(v)

