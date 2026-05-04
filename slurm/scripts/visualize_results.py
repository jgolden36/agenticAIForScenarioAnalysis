#!/usr/bin/env python3
"""SLURM stage 6 — Visualization suite for the Hormuz pipeline.

Consumes the CSVs and qualitative narratives that
``slurm/scripts/export_results.py`` writes under
``data/reports/<run_id>/`` and produces a self-contained visualization
bundle under ``data/reports/<run_id>/figures/``:

* ``model_status_by_scenario.png`` — stacked bar of model run status
  (completed / skipped / failed) per scenario.
* ``model_status_by_system.png`` — same data, grouped by commodity
  system (best-effort lookup against the model registry; falls back to
  per-model ``model_id`` when the registry can't be built).
* ``synthesis_outcomes_grid.png`` — grid of bar charts, one panel per
  ``(time_horizon, outcome_scope)`` combination, plotting the headline
  numerics from ``synthesis_outcomes.csv``.
* ``quantitative_heatmap.png`` — value-normalised heatmap of every
  scalar output across (scenario, model, output_key) triples extracted
  from ``quantitative_results.csv``. Useful for spotting which models
  swing with scenario assumptions.
* ``consistency_flags.png`` — bar chart of consistency-flag severities
  (only emitted when ``consistency_flags.csv`` is non-empty).
* ``timeseries/<scenario>__<model>__<series>.png`` — line plot per
  long-form CSV under ``csv/raw/``. Categorical x-axes are detected
  automatically and rendered as bar charts instead.
* ``regional_impact_heatmap.png`` — unified-region heatmap built from
  ``regional_outcomes_unified.csv``. Rows are ``(model, value_label)``,
  columns are unified regions; one panel per scenario. The headline
  "who is hit hardest" chart.
* ``regional_distribution_<scenario>.png`` — per-scenario sorted bar
  of unified regions for the most-populated value_label.
* ``sectoral_distribution_<scenario>.png`` — per-scenario sectoral
  bar chart from ``sectoral_outcomes.csv``.
* ``regional_crosswalk_audit.png`` — small-multiples sanity check
  showing how native ids rolled up into the unified taxonomy.
* ``index.html`` — single-file dashboard that embeds every figure
  inline, renders the per-scenario qualitative narrative markdown
  alongside its figures, and links the underlying CSVs so a reviewer
  can drill from chart to table to JSON in two clicks.

Design notes:

* The script is **best-effort and idempotent**: rerunning overwrites
  the figure set but never mutates pipeline state. A missing optional
  dependency (matplotlib, markdown, pandas) downgrades the relevant
  feature instead of failing the stage. When matplotlib is entirely
  missing the script still emits ``index.html`` with embedded HTML
  tables built from the CSVs (no images), so the run still produces a
  shareable report on minimal environments.
* No LLM calls are made here. All narrative text is taken verbatim
  from the qualitative markdown produced by Stage 5 — this keeps
  Stage 6 fast and reproducible.

Standalone use::

    python slurm/scripts/visualize_results.py --run-id 20260423_125906
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import os
import re
import sys
import traceback
from collections import defaultdict, OrderedDict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (  # noqa: E402
    get_project_root,
    get_run_id,
    log_slurm_context,
    logger,
)


# --------------------------------------------------------------------
# Optional-dependency gates. Each capability degrades to a documented
# fallback rather than raising so the stage stays opportunistic.
# --------------------------------------------------------------------

try:  # matplotlib drives every PNG output.
    import matplotlib  # noqa: WPS433
    matplotlib.use("Agg")  # headless backend; the cluster has no display.
    import matplotlib.pyplot as plt  # noqa: WPS433
    HAS_MPL = True
except Exception as _mpl_exc:  # pragma: no cover
    plt = None  # type: ignore[assignment]
    HAS_MPL = False
    _MPL_ERR = str(_mpl_exc)

try:  # markdown -> HTML for the dashboard narrative blocks.
    import markdown as _markdown_lib  # noqa: WPS433
    HAS_MARKDOWN = True
except Exception:
    _markdown_lib = None  # type: ignore[assignment]
    HAS_MARKDOWN = False


# --------------------------------------------------------------------
# Path helpers (mirror export_results.py so artefacts land beside it).
# --------------------------------------------------------------------


def reports_root(run_id: str) -> Path:
    return get_project_root() / "data" / "reports" / run_id


def csv_root(run_id: str) -> Path:
    return reports_root(run_id) / "csv"


def qualitative_root(run_id: str) -> Path:
    return reports_root(run_id) / "qualitative"


def figures_root(run_id: str) -> Path:
    d = reports_root(run_id) / "figures"
    d.mkdir(parents=True, exist_ok=True)
    (d / "timeseries").mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------
# CSV loading. Stdlib only so a thin standalone-export environment
# without pandas can still produce charts (matplotlib does not require
# pandas).
# --------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _coerce_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    # Drop common decoration so synthesis-outcome strings like "21%"
    # or "$110/bbl" still surface in the bar charts.
    cleaned = s.replace(",", "").replace("%", "").replace("$", "")
    cleaned = re.sub(r"[A-Za-z/]+$", "", cleaned).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# --------------------------------------------------------------------
# Best-effort registry lookup (commodity system per model_id) for the
# system-grouped status chart. Falls back to "unknown" silently.
# --------------------------------------------------------------------


def _commodity_system_map() -> dict[str, str]:
    try:
        from src.models.registry import build_default_registry  # noqa: WPS433

        reg = build_default_registry()
        out: dict[str, str] = {}
        for adapter in reg.all_adapters():
            out[adapter.model_id] = adapter.commodity_system.value
        return out
    except Exception:
        return {}


# --------------------------------------------------------------------
# Figure: model status by scenario (stacked bar).
# --------------------------------------------------------------------


_STATUS_ORDER = ["completed", "skipped", "failed"]
_STATUS_COLORS = {
    "completed": "#2ca02c",
    "skipped": "#ff7f0e",
    "failed": "#d62728",
}


def plot_model_status_by_scenario(rows: list[dict], out: Path) -> Path | None:
    if not HAS_MPL or not rows:
        return None
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        scen = r.get("scenario_id") or "unknown"
        status = (r.get("status") or "unknown").lower()
        counts[scen][status] += 1
    scenarios = sorted(counts.keys())
    fig, ax = plt.subplots(figsize=(max(8, len(scenarios) * 1.5), 5))
    bottoms = [0] * len(scenarios)
    for status in _STATUS_ORDER:
        vals = [counts[s].get(status, 0) for s in scenarios]
        ax.bar(
            scenarios, vals, bottom=bottoms,
            label=status, color=_STATUS_COLORS.get(status, "gray"),
        )
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Model runs")
    ax.set_xlabel("Scenario")
    ax.set_title("Model run status by scenario")
    ax.legend(loc="upper right")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_model_status_by_system(rows: list[dict], out: Path) -> Path | None:
    if not HAS_MPL or not rows:
        return None
    sysmap = _commodity_system_map()
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        sys_name = sysmap.get(r.get("model_id") or "", "unknown")
        status = (r.get("status") or "unknown").lower()
        counts[sys_name][status] += 1
    if not counts:
        return None
    systems = sorted(counts.keys())
    fig, ax = plt.subplots(figsize=(max(8, len(systems) * 1.6), 5))
    bottoms = [0] * len(systems)
    for status in _STATUS_ORDER:
        vals = [counts[s].get(status, 0) for s in systems]
        ax.bar(
            systems, vals, bottom=bottoms,
            label=status, color=_STATUS_COLORS.get(status, "gray"),
        )
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Model runs (across all scenarios)")
    ax.set_xlabel("Commodity system")
    ax.set_title("Model run status by commodity system")
    ax.legend(loc="upper right")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# --------------------------------------------------------------------
# Figure: synthesis outcomes grid (one panel per time_horizon × scope).
# --------------------------------------------------------------------


def plot_synthesis_outcomes_grid(rows: list[dict], out: Path) -> Path | None:
    if not HAS_MPL or not rows:
        return None
    panels: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        th = r.get("time_horizon") or "unknown"
        scope = r.get("outcome_scope") or "unknown"
        panels[(th, scope)].append(r)
    keys = sorted(panels.keys())
    if not keys:
        return None
    cols = 2
    n_rows = (len(keys) + cols - 1) // cols
    fig, axes = plt.subplots(
        n_rows, cols, figsize=(14, max(4, 3.5 * n_rows)), squeeze=False,
    )
    for idx, (key, entries) in enumerate(zip(keys, [panels[k] for k in keys])):
        ax = axes[idx // cols][idx % cols]
        # Aggregate (variable, scenario) -> numeric value, dropping
        # rows whose value isn't parseable as a float (e.g. "Not Available").
        numeric: list[tuple[str, str, float]] = []
        for r in entries:
            v = _coerce_float(r.get("value"))
            if v is None:
                continue
            numeric.append((
                r.get("outcome_variable") or "?",
                r.get("scenario_id") or "?",
                v,
            ))
        if not numeric:
            ax.text(
                0.5, 0.5, "no numeric values\n(see qualitative narrative)",
                ha="center", va="center", transform=ax.transAxes,
                color="gray", fontsize=10,
            )
            ax.set_title(f"{key[0]} · {key[1]}", fontsize=11)
            ax.set_xticks([])
            ax.set_yticks([])
            continue
        variables = list(OrderedDict.fromkeys(t[0] for t in numeric))
        scenarios = list(OrderedDict.fromkeys(t[1] for t in numeric))
        bar_w = 0.8 / max(1, len(scenarios))
        x = list(range(len(variables)))
        for s_idx, scen in enumerate(scenarios):
            vals = []
            for var in variables:
                match = next(
                    (v for (vv, ss, v) in numeric if vv == var and ss == scen),
                    None,
                )
                vals.append(match if match is not None else 0)
            ax.bar(
                [xi + s_idx * bar_w for xi in x], vals,
                width=bar_w, label=scen,
            )
        ax.set_xticks([xi + bar_w * (len(scenarios) - 1) / 2 for xi in x])
        ax.set_xticklabels(variables, rotation=25, ha="right", fontsize=8)
        ax.set_title(f"{key[0]} · {key[1]}", fontsize=11)
        ax.legend(fontsize=7, loc="best")
    # Hide any leftover axes in the last row.
    total = n_rows * cols
    for idx in range(len(keys), total):
        axes[idx // cols][idx % cols].axis("off")
    fig.suptitle("Headline synthesised outcomes by horizon × scope", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# --------------------------------------------------------------------
# Figure: quantitative heatmap (scenarios × output_keys).
# --------------------------------------------------------------------


def plot_quantitative_heatmap(rows: list[dict], out: Path) -> Path | None:
    if not HAS_MPL or not rows:
        return None
    # Long-form: (model_id, output_key) -> {scenario -> value}.
    cells: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in rows:
        if (r.get("is_numeric") or "").lower() != "true":
            continue
        v = _coerce_float(r.get("value_numeric"))
        if v is None:
            continue
        scen = r.get("scenario_id") or "?"
        model = r.get("model_id") or "?"
        key = r.get("output_key") or "?"
        cells[(model, key)][scen] = v
    if not cells:
        return None
    scenarios = sorted({s for d in cells.values() for s in d.keys()})
    rows_keys = sorted(cells.keys())
    # Per-row min-max normalisation so units (USD/bbl vs %) coexist on
    # one heatmap. Constant rows become 0.5 so they don't disappear.
    norm_matrix: list[list[float]] = []
    for rk in rows_keys:
        vals = [cells[rk].get(s, float("nan")) for s in scenarios]
        finite = [v for v in vals if v == v]  # NaN-safe
        if not finite:
            norm_matrix.append([0.0] * len(scenarios))
            continue
        lo, hi = min(finite), max(finite)
        if hi == lo:
            norm_matrix.append([0.5 if v == v else 0.0 for v in vals])
        else:
            norm_matrix.append([
                (v - lo) / (hi - lo) if v == v else 0.0 for v in vals
            ])
    height = max(4, 0.32 * len(rows_keys))
    fig, ax = plt.subplots(figsize=(max(8, 1.4 * len(scenarios) + 5), height))
    im = ax.imshow(norm_matrix, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels(scenarios, rotation=20, ha="right", fontsize=9)
    ax.set_yticks(range(len(rows_keys)))
    ax.set_yticklabels(
        [f"{m} · {k}" for (m, k) in rows_keys], fontsize=7,
    )
    ax.set_title(
        "Per-row normalised scalar outputs (scenarios × model.output)\n"
        "darker = lower within row, brighter = higher within row",
        fontsize=11,
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("normalised value [0, 1]", fontsize=9)
    # Annotate raw values when the matrix is small enough to read.
    if len(rows_keys) * len(scenarios) <= 200:
        for i, rk in enumerate(rows_keys):
            for j, scen in enumerate(scenarios):
                v = cells[rk].get(scen)
                if v is None:
                    continue
                ax.text(
                    j, i, f"{v:g}", ha="center", va="center",
                    fontsize=6,
                    color="white" if norm_matrix[i][j] < 0.55 else "black",
                )
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# --------------------------------------------------------------------
# Figure: per-output uncertainty bands (error-bar plots).
#
# Driven by ``uncertainty_bands.csv`` (written by export_results.py
# when any model returned an UncertaintyReport). One panel per
# (model_id, output_key) showing scenario-by-scenario p05-p95 bars
# with the median (p50) marked.
# --------------------------------------------------------------------


def plot_uncertainty_error_bars(
    rows: list[dict], out: Path, max_panels: int = 24
) -> Path | None:
    """Forest-style error-bar grid of p05-p95 uncertainty bands.

    Each panel = one (model, output_key). Within a panel, each row is
    one scenario; the horizontal bar shows the p05-p95 range, and a
    dot marks the p50 (or mean when p50 is missing). Multi-output
    runs get a 2-column grid; single-output runs get one tall panel.

    Returns ``None`` when matplotlib is missing or there are no UQ
    rows (so the dashboard simply omits the figure rather than
    erroring).
    """
    if not HAS_MPL or not rows:
        return None

    # Group rows by (model_id, output_key) -> {scenario_id: row}.
    panels: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for r in rows:
        model = r.get("model_id") or "?"
        key = r.get("output_key") or "?"
        scen = r.get("scenario_id") or "?"
        panels[(model, key)][scen] = r

    if not panels:
        return None

    # Score panels by total band width (p95-p05 across scenarios) so the
    # plot prioritises outputs where uncertainty actually matters when
    # we have to truncate.
    def _band_width(panel: dict[str, dict]) -> float:
        spread = 0.0
        for r in panel.values():
            p05 = _coerce_float(r.get("p05"))
            p95 = _coerce_float(r.get("p95"))
            if p05 is not None and p95 is not None:
                spread = max(spread, p95 - p05)
        return spread

    panel_keys = sorted(panels.keys(), key=lambda k: -_band_width(panels[k]))
    truncated = len(panel_keys) > max_panels
    panel_keys = panel_keys[:max_panels]

    n = len(panel_keys)
    cols = 2 if n > 1 else 1
    rows_grid = (n + cols - 1) // cols
    fig, axes = plt.subplots(
        rows_grid, cols,
        figsize=(7.5 * cols, max(2.4, 1.0 * rows_grid + 0.6 * n / cols)),
        squeeze=False,
    )

    for idx, (model, key) in enumerate(panel_keys):
        ax = axes[idx // cols][idx % cols]
        panel = panels[(model, key)]
        scenarios = sorted(panel.keys())
        ys = list(range(len(scenarios)))
        means = [_coerce_float(panel[s].get("mean")) for s in scenarios]
        p50s = [_coerce_float(panel[s].get("p50")) for s in scenarios]
        p05s = [_coerce_float(panel[s].get("p05")) for s in scenarios]
        p95s = [_coerce_float(panel[s].get("p95")) for s in scenarios]
        p25s = [_coerce_float(panel[s].get("p25")) for s in scenarios]
        p75s = [_coerce_float(panel[s].get("p75")) for s in scenarios]
        centers = [m if m is not None else (p if p is not None else 0.0)
                   for m, p in zip(p50s, means)]

        # 90% band (p05-p95) as a thin error bar; 50% band (p25-p75) as
        # a thicker overlay so the analyst can read both at once.
        for y, lo, hi in zip(ys, p05s, p95s):
            if lo is None or hi is None:
                continue
            ax.plot([lo, hi], [y, y], color="#1f77b4", lw=1.3,
                    solid_capstyle="butt", alpha=0.7)
        for y, lo, hi in zip(ys, p25s, p75s):
            if lo is None or hi is None:
                continue
            ax.plot([lo, hi], [y, y], color="#1f77b4", lw=4.5,
                    solid_capstyle="butt", alpha=0.95)
        ax.scatter(
            [c for c in centers], ys,
            color="#d62728", zorder=3, s=22,
            label="median" if idx == 0 else None,
        )

        ax.set_yticks(ys)
        ax.set_yticklabels(scenarios, fontsize=8)
        ax.invert_yaxis()
        ax.set_title(f"{model} · {key}", fontsize=9)
        ax.grid(axis="x", alpha=0.25, linestyle=":")
        ax.tick_params(axis="x", labelsize=7)

    # Hide any leftover panels in the grid.
    for j in range(n, rows_grid * cols):
        axes[j // cols][j % cols].axis("off")

    title = "Per-output uncertainty: 90% band (thin), 50% band (thick), median (dot)"
    if truncated:
        title += f"\n(showing {len(panel_keys)} widest panels of {len(panels)})"
    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_synthesis_outcomes_with_bands(
    rows: list[dict], out: Path
) -> Path | None:
    """Bar chart of synthesis outcomes with p05-p95 whiskers when available.

    Reads from ``quantitative_results.csv`` (extended schema with
    ``mean`` / ``p05`` / ``p95``). Picks the most informative
    headline-numeric rows per scenario — those whose 90% band is
    widest in absolute terms — and plots them grouped by scenario so
    a reviewer immediately sees scale and uncertainty side by side.
    """
    if not HAS_MPL or not rows:
        return None
    have_band_rows: list[dict] = []
    for r in rows:
        if (r.get("is_numeric") or "").lower() != "true":
            continue
        if _coerce_float(r.get("p05")) is None:
            continue
        if _coerce_float(r.get("p95")) is None:
            continue
        have_band_rows.append(r)
    if not have_band_rows:
        return None

    # Pick the top 8 (model, output) pairs by mean band width.
    by_pair: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in have_band_rows:
        by_pair[(r.get("model_id") or "?", r.get("output_key") or "?")].append(r)

    def _avg_width(rs: list[dict]) -> float:
        widths: list[float] = []
        for r in rs:
            lo = _coerce_float(r.get("p05"))
            hi = _coerce_float(r.get("p95"))
            if lo is not None and hi is not None:
                widths.append(hi - lo)
        return sum(widths) / len(widths) if widths else 0.0

    pairs = sorted(by_pair.keys(), key=lambda k: -_avg_width(by_pair[k]))[:8]
    if not pairs:
        return None
    scenarios = sorted({
        r.get("scenario_id") for rs in by_pair.values() for r in rs
        if r.get("scenario_id")
    })
    if not scenarios:
        return None

    fig, axes = plt.subplots(
        len(pairs), 1,
        figsize=(max(7.0, 1.4 * len(scenarios) + 4.0), 1.6 * len(pairs) + 1.0),
        squeeze=False,
    )
    for i, (model, key) in enumerate(pairs):
        ax = axes[i][0]
        rs = {r.get("scenario_id"): r for r in by_pair[(model, key)]}
        xs = list(range(len(scenarios)))
        means = [_coerce_float(rs.get(s, {}).get("mean") or rs.get(s, {}).get("value_numeric"))
                 for s in scenarios]
        p05s = [_coerce_float(rs.get(s, {}).get("p05")) for s in scenarios]
        p95s = [_coerce_float(rs.get(s, {}).get("p95")) for s in scenarios]
        # Asymmetric error bars relative to the mean.
        lower_err: list[float] = []
        upper_err: list[float] = []
        valid_means: list[float] = []
        for m, lo, hi in zip(means, p05s, p95s):
            if m is None:
                valid_means.append(0.0)
                lower_err.append(0.0)
                upper_err.append(0.0)
                continue
            valid_means.append(m)
            lower_err.append(max(0.0, m - lo) if lo is not None else 0.0)
            upper_err.append(max(0.0, hi - m) if hi is not None else 0.0)
        ax.bar(xs, valid_means, color="#4c72b0", alpha=0.75)
        ax.errorbar(
            xs, valid_means,
            yerr=[lower_err, upper_err],
            fmt="none", ecolor="#222", capsize=4, lw=1.3,
        )
        ax.set_xticks(xs)
        ax.set_xticklabels(scenarios, rotation=15, ha="right", fontsize=8)
        ax.set_title(f"{model} · {key}", fontsize=9)
        ax.grid(axis="y", alpha=0.25, linestyle=":")
        ax.tick_params(axis="y", labelsize=7)
    fig.suptitle(
        "Headline outcomes with 90% uncertainty band (p05-p95)", fontsize=11
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# --------------------------------------------------------------------
# Figure: consistency flags (severity bar). Only when present.
# --------------------------------------------------------------------


def plot_consistency_flags(rows: list[dict], out: Path) -> Path | None:
    if not HAS_MPL or not rows:
        return None
    sev_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        sev = (r.get("severity") or r.get("level") or "unknown").lower()
        sev_counts[sev] += 1
    if not sev_counts:
        return None
    labels = sorted(sev_counts.keys())
    vals = [sev_counts[k] for k in labels]
    fig, ax = plt.subplots(figsize=(max(5, 1.2 * len(labels) + 2), 4))
    ax.bar(labels, vals, color="#9467bd")
    ax.set_ylabel("Flag count")
    ax.set_title(f"Cross-model consistency flags ({sum(vals)} total)")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# --------------------------------------------------------------------
# Figure: per-model long-form time series (one PNG per CSV).
# --------------------------------------------------------------------


_X_AXIS_HINTS = ("year", "period", "step", "timestamp", "date", "t", "horizon")


def _pick_x_column(cols: list[str]) -> str | None:
    for hint in _X_AXIS_HINTS:
        for c in cols:
            if c.lower() == hint or c.lower().endswith("_" + hint):
                return c
    return None


def plot_timeseries_csvs(run_id: str) -> list[Path]:
    """Walk csv/raw/<scenario>/<model>__<series>.csv and emit one
    PNG per CSV. Returns the list of generated paths."""
    written: list[Path] = []
    if not HAS_MPL:
        return written
    raw_dir = csv_root(run_id) / "raw"
    if not raw_dir.exists():
        return written
    out_root = figures_root(run_id) / "timeseries"
    for scen_dir in sorted(raw_dir.iterdir()):
        if not scen_dir.is_dir():
            continue
        scenario = scen_dir.name
        for csv_path in sorted(scen_dir.glob("*.csv")):
            stem = csv_path.stem
            if stem.endswith("__scalars"):
                continue
            try:
                rows = _read_csv(csv_path)
            except Exception:
                continue
            if not rows:
                continue
            cols = list(rows[0].keys())
            x_col = _pick_x_column(cols)
            if x_col is None:
                # Fall back to the first non-numeric column, else
                # an integer index.
                x_col = cols[0]
            y_cols = [c for c in cols if c != x_col]
            # Restrict to numeric y columns; skip the figure if none.
            numeric_y: list[str] = []
            for c in y_cols:
                if any(_coerce_float(r.get(c)) is not None for r in rows):
                    numeric_y.append(c)
            if not numeric_y:
                continue
            x_raw = [r.get(x_col, "") for r in rows]
            x_num = [_coerce_float(v) for v in x_raw]
            x_is_numeric = all(v is not None for v in x_num)
            try:
                fig, ax = plt.subplots(figsize=(10, 5))
                if x_is_numeric:
                    xs = x_num
                    for c in numeric_y[:6]:  # cap legend churn
                        ys = [_coerce_float(r.get(c)) for r in rows]
                        # Drop None pairs together.
                        pairs = [
                            (xv, yv) for xv, yv in zip(xs, ys)
                            if xv is not None and yv is not None
                        ]
                        if not pairs:
                            continue
                        xx, yy = zip(*pairs)
                        ax.plot(xx, yy, marker="o", label=c, linewidth=1.5)
                    ax.set_xlabel(x_col)
                else:
                    # Categorical x → grouped bar.
                    cat_x = [str(v) for v in x_raw]
                    width = 0.8 / max(1, len(numeric_y))
                    indices = list(range(len(cat_x)))
                    for i, c in enumerate(numeric_y[:6]):
                        ys = [_coerce_float(r.get(c)) or 0.0 for r in rows]
                        ax.bar(
                            [xi + i * width for xi in indices], ys,
                            width=width, label=c,
                        )
                    ax.set_xticks(
                        [xi + width * (len(numeric_y[:6]) - 1) / 2 for xi in indices]
                    )
                    ax.set_xticklabels(cat_x, rotation=25, ha="right", fontsize=8)
                    ax.set_xlabel(x_col)
                # Recover the (model, series) tuple from the filename
                # (encoded by export_results.py as ``<model>__<series>.csv``).
                if "__" in stem:
                    model, series = stem.split("__", 1)
                else:
                    model, series = stem, "series"
                ax.set_title(f"{scenario} · {model} · {series}")
                ax.legend(fontsize=8, loc="best")
                ax.grid(True, alpha=0.3)
                fig.tight_layout()
                out_path = out_root / f"{scenario}__{stem}.png"
                fig.savefig(out_path, dpi=130)
                plt.close(fig)
                written.append(out_path)
            except Exception:
                logger.warning(
                    f"timeseries plot failed for {csv_path.name}: "
                    f"{traceback.format_exc().splitlines()[-1]}"
                )
                plt.close("all")
    if written:
        logger.info(f"wrote {len(written)} time-series PNG(s) under {out_root}")
    return written


# --------------------------------------------------------------------
# Distributional figures (regional + sectoral).
# --------------------------------------------------------------------


_UNIFIED_REGION_ORDER = (
    "US", "CHN", "IND", "EU", "MENA_GCC", "MENA_OTHER",
    "SSA", "LAC", "ROW", "GLOBAL",
)


def _group_regional_by_scenario(
    rows: list[dict],
) -> dict[str, dict[tuple[str, str, str], dict[str, float]]]:
    """Group ``regional_outcomes_unified.csv`` rows by scenario into a
    nested ``{scenario: {(model, output_key, value_label): {region: v}}}``.
    """
    out: dict[str, dict[tuple[str, str, str], dict[str, float]]] = defaultdict(dict)
    for r in rows:
        scen = r.get("scenario_id") or "unknown"
        model = r.get("model_id") or "?"
        output_key = r.get("output_key") or "?"
        value_label = r.get("value_label") or "value"
        region = r.get("unified_region") or "ROW"
        v = _coerce_float(r.get("value"))
        if v is None:
            continue
        out[scen].setdefault((model, output_key, value_label), {})[region] = v
    return out


def plot_regional_impact_heatmap(rows: list[dict], out: Path) -> Path | None:
    if not HAS_MPL or not rows:
        return None
    by_scenario = _group_regional_by_scenario(rows)
    scenarios = sorted(by_scenario.keys())
    if not scenarios:
        return None
    all_keys: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for scen in scenarios:
        for k in by_scenario[scen].keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)
    all_keys.sort()
    n_panels = len(scenarios)
    cols = min(n_panels, 2)
    n_rows = (n_panels + cols - 1) // cols
    height = max(4, 0.32 * len(all_keys) + 1)
    fig, axes = plt.subplots(
        n_rows, cols,
        figsize=(max(8, 1.4 * len(_UNIFIED_REGION_ORDER) + 4), height * n_rows),
        squeeze=False,
    )
    for idx, scen in enumerate(scenarios):
        ax = axes[idx // cols][idx % cols]
        cells = by_scenario[scen]
        matrix: list[list[float]] = []
        for k in all_keys:
            region_vals = cells.get(k, {})
            row_vals = [region_vals.get(reg, float("nan")) for reg in _UNIFIED_REGION_ORDER]
            finite = [v for v in row_vals if v == v]
            if finite and max(finite) != min(finite):
                lo, hi = min(finite), max(finite)
                norm = [(v - lo) / (hi - lo) if v == v else 0.0 for v in row_vals]
            elif finite:
                norm = [0.5 if v == v else 0.0 for v in row_vals]
            else:
                norm = [0.0] * len(_UNIFIED_REGION_ORDER)
            matrix.append(norm)
        im = ax.imshow(matrix, aspect="auto", cmap="RdYlBu_r")
        ax.set_xticks(range(len(_UNIFIED_REGION_ORDER)))
        ax.set_xticklabels(_UNIFIED_REGION_ORDER, rotation=20, ha="right", fontsize=8)
        ax.set_yticks(range(len(all_keys)))
        ax.set_yticklabels(
            [f"{m} · {o} · {v}" for (m, o, v) in all_keys], fontsize=7,
        )
        ax.set_title(f"Scenario · {scen}", fontsize=10)
        if len(all_keys) * len(_UNIFIED_REGION_ORDER) <= 200:
            for i, k in enumerate(all_keys):
                region_vals = cells.get(k, {})
                for j, reg in enumerate(_UNIFIED_REGION_ORDER):
                    v = region_vals.get(reg)
                    if v is None:
                        continue
                    ax.text(
                        j, i, f"{v:g}", ha="center", va="center",
                        fontsize=6, color="black",
                    )
    for idx in range(len(scenarios), n_rows * cols):
        axes[idx // cols][idx % cols].axis("off")
    fig.suptitle(
        "Regional impact heatmap — unified taxonomy (per-row normalised)",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def _pick_headline_value_label(
    cells: dict[tuple[str, str, str], dict[str, float]],
) -> tuple[str, str, str] | None:
    """Pick the (model, output_key, value_label) with the most regional
    coverage so the per-scenario distribution chart picks a sensible
    series. Prefer MIRAGRODEP welfare/GDP when available.
    """
    if not cells:
        return None
    preferred = [
        ("miragrodep", None, "welfare_pct"),
        ("miragrodep", None, "gdp_pct"),
        ("miragrodep", "regional_vars", "value"),
    ]
    for pref_model, pref_key, pref_label in preferred:
        for k in cells.keys():
            m, o, lbl = k
            if m != pref_model:
                continue
            if pref_key and o != pref_key:
                continue
            if lbl == pref_label:
                return k
    return max(cells.keys(), key=lambda k: len(cells[k]))


def plot_regional_distribution_per_scenario(
    rows: list[dict], fig_dir: Path,
) -> list[Path]:
    written: list[Path] = []
    if not HAS_MPL or not rows:
        return written
    by_scenario = _group_regional_by_scenario(rows)
    for scen, cells in sorted(by_scenario.items()):
        key = _pick_headline_value_label(cells)
        if key is None:
            continue
        region_vals = cells[key]
        items = sorted(region_vals.items(), key=lambda kv: kv[1])
        regions = [r for r, _ in items]
        values = [v for _, v in items]
        if not regions:
            continue
        try:
            fig, ax = plt.subplots(figsize=(9, max(3, 0.35 * len(regions) + 1)))
            colors = ["#d62728" if v < 0 else "#2ca02c" for v in values]
            ax.barh(regions, values, color=colors)
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_xlabel(f"{key[2]} (signed)")
            ax.set_title(
                f"{scen} · regional distribution\n"
                f"({key[0]} · {key[1]} · {key[2]})",
                fontsize=10,
            )
            ax.grid(True, axis="x", alpha=0.3)
            for i, v in enumerate(values):
                ax.text(
                    v, i, f" {v:g}", va="center",
                    ha="left" if v >= 0 else "right", fontsize=8,
                )
            fig.tight_layout()
            out = fig_dir / f"regional_distribution_{scen}.png"
            fig.savefig(out, dpi=140)
            plt.close(fig)
            written.append(out)
        except Exception:
            logger.warning(
                f"regional_distribution plot failed for {scen}: "
                f"{traceback.format_exc().splitlines()[-1]}"
            )
            plt.close("all")
    return written


def plot_sectoral_distribution_per_scenario(
    rows: list[dict], fig_dir: Path,
) -> list[Path]:
    written: list[Path] = []
    if not HAS_MPL or not rows:
        return written
    grouped: dict[str, dict[tuple[str, str, str], dict[str, list[float]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    for r in rows:
        scen = r.get("scenario_id") or "unknown"
        model = r.get("model_id") or "?"
        output_key = r.get("output_key") or "?"
        value_label = r.get("value_label") or "value"
        sector = r.get("sector") or "?"
        v = _coerce_float(r.get("value"))
        if v is None:
            continue
        grouped[scen][(model, output_key, value_label)][sector].append(v)
    # Average duplicates (multi-region rows of regional_sectoral collapse
    # to a sector view).
    grouped_mean: dict[str, dict[tuple[str, str, str], dict[str, float]]] = {}
    for scen, by_key in grouped.items():
        out: dict[tuple[str, str, str], dict[str, float]] = {}
        for k, sector_vals in by_key.items():
            out[k] = {s: sum(vs) / len(vs) for s, vs in sector_vals.items() if vs}
        grouped_mean[scen] = out
    grouped = grouped_mean  # type: ignore[assignment]
    for scen, cells in sorted(grouped.items()):
        if not cells:
            continue
        n_panels = min(len(cells), 4)
        keys = sorted(cells.keys())[:n_panels]
        fig, axes = plt.subplots(
            n_panels, 1, figsize=(9, 3 * n_panels), squeeze=False,
        )
        for i, k in enumerate(keys):
            ax = axes[i][0]
            sector_vals = cells[k]
            items = sorted(sector_vals.items(), key=lambda kv: kv[1])
            sectors = [s for s, _ in items]
            values = [v for _, v in items]
            colors = ["#d62728" if v < 0 else "#2ca02c" for v in values]
            ax.barh(sectors, values, color=colors)
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_xlabel(k[2])
            ax.set_title(f"{k[0]} · {k[1]}", fontsize=10)
            ax.grid(True, axis="x", alpha=0.3)
        fig.suptitle(f"{scen} · sectoral distribution", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        out = fig_dir / f"sectoral_distribution_{scen}.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        written.append(out)
    return written


def plot_native_vs_unified_audit(
    native_rows: list[dict], out: Path,
) -> Path | None:
    """Show how native ids rolled up to the unified taxonomy.

    One bar per unified region with a stacked breakdown of contributing
    native ids per (model, value_label). Helps analysts spot where ROW
    is hiding many distinct countries.
    """
    if not HAS_MPL or not native_rows:
        return None
    unified_to_natives: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in native_rows:
        unified = r.get("unified_region") or "ROW"
        native = r.get("native_region") or "?"
        unified_to_natives[unified][native] += 1
    if not unified_to_natives:
        return None
    unified_keys = [u for u in _UNIFIED_REGION_ORDER if u in unified_to_natives]
    fig, ax = plt.subplots(figsize=(max(8, 1.2 * len(unified_keys) + 2), 5))
    bar_heights = [
        sum(unified_to_natives[u].values()) for u in unified_keys
    ]
    ax.bar(unified_keys, bar_heights, color="#1f77b4")
    for i, u in enumerate(unified_keys):
        natives = unified_to_natives[u]
        top_natives = sorted(natives.items(), key=lambda kv: -kv[1])[:5]
        label = ", ".join(n for n, _ in top_natives)
        if len(natives) > 5:
            label += f", +{len(natives) - 5} more"
        ax.text(
            i, bar_heights[i] + max(bar_heights) * 0.01,
            label, ha="center", va="bottom", fontsize=7, rotation=0,
            wrap=True,
        )
    ax.set_ylabel("# native records routed to this unified region")
    ax.set_title("Native -> unified region crosswalk audit")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# --------------------------------------------------------------------
# HTML dashboard. Self-contained: figures embedded as base64 so the
# index.html renders even when shipped off-cluster as a single file.
# --------------------------------------------------------------------


_INDEX_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       margin: 0; padding: 24px 36px; color: #1a1a1a; background: #fafafa; }
h1 { margin-top: 0; font-size: 1.7rem; }
h2 { margin-top: 2.2rem; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
h3 { margin-top: 1.6rem; color: #444; }
section { background: white; padding: 16px 22px; margin-bottom: 18px;
          border: 1px solid #e0e0e0; border-radius: 6px;
          box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
img.figure { max-width: 100%; height: auto; display: block;
             margin: 12px auto; border: 1px solid #eee; border-radius: 4px; }
.meta { color: #666; font-size: 0.85rem; }
.badge { display: inline-block; padding: 2px 8px; margin-right: 6px;
         border-radius: 10px; font-size: 0.75rem; color: white; }
.badge.completed { background: #2ca02c; }
.badge.skipped   { background: #ff7f0e; }
.badge.failed    { background: #d62728; }
.badge.unknown   { background: #888; }
table { border-collapse: collapse; width: 100%; font-size: 0.82rem;
        margin: 8px 0 16px 0; }
th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left;
         vertical-align: top; }
th { background: #f0f0f0; }
tr:nth-child(even) td { background: #fafafa; }
details { margin: 6px 0 14px 0; }
summary { cursor: pointer; font-weight: 600; color: #444; }
.narrative { background: #fcfcfc; border-left: 3px solid #1f77b4;
             padding: 10px 14px; margin: 10px 0 14px 0; }
.narrative h2 { font-size: 1.1rem; border-bottom: none; margin-top: 8px; }
.narrative h3 { font-size: 1.0rem; color: #333; }
.toc a { display: block; padding: 2px 0; color: #1f77b4; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
"""


def _embed_image(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f'<img class="figure" alt="{html.escape(path.name)}" src="data:image/png;base64,{b64}" />'


def _md_to_html(text: str) -> str:
    if HAS_MARKDOWN:
        try:
            return _markdown_lib.markdown(
                text, extensions=["extra", "sane_lists"]
            )
        except Exception:
            pass
    # Stdlib fallback: escape, then thinly format headers / bullets.
    escaped = html.escape(text)
    escaped = re.sub(r"^## (.+)$", r"<h2>\1</h2>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^# (.+)$",  r"<h1>\1</h1>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^- (.+)$",  r"<li>\1</li>", escaped, flags=re.MULTILINE)
    return f"<pre style='white-space:pre-wrap'>{escaped}</pre>"


def _csv_to_html_table(path: Path, max_rows: int = 25) -> str:
    rows = _read_csv(path)
    if not rows:
        return ""
    cols = list(rows[0].keys())
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body_parts: list[str] = []
    for r in rows[:max_rows]:
        cells = "".join(
            f"<td>{html.escape(str(r.get(c, '')))}</td>" for c in cols
        )
        body_parts.append(f"<tr>{cells}</tr>")
    suffix = ""
    if len(rows) > max_rows:
        suffix = (
            f"<p class='meta'>… {len(rows) - max_rows} more row(s) "
            f"hidden; full table at <code>{html.escape(path.name)}</code>.</p>"
        )
    return (
        f"<table><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_parts)}</tbody></table>{suffix}"
    )


def _summary_badges(model_status_rows: list[dict]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for r in model_status_rows:
        counts[(r.get("status") or "unknown").lower()] += 1
    parts = []
    for status in ("completed", "skipped", "failed", "unknown"):
        n = counts.get(status, 0)
        if n == 0 and status == "unknown":
            continue
        parts.append(
            f'<span class="badge {status}">{status}: {n}</span>'
        )
    return " ".join(parts)


def _summarise_top_bottom_unified(
    unified_rows: list[dict], top_n: int = 5,
) -> str:
    """Build the HTML table of top-N gainers / bottom-N losers from
    ``regional_outcomes_unified.csv``. Returns ``""`` when no rows.
    """
    if not unified_rows:
        return ""
    parsed = []
    for r in unified_rows:
        v = _coerce_float(r.get("value"))
        if v is None:
            continue
        parsed.append({
            "scenario_id": r.get("scenario_id") or "?",
            "model_id": r.get("model_id") or "?",
            "output_key": r.get("output_key") or "?",
            "value_label": r.get("value_label") or "value",
            "unified_region": r.get("unified_region") or "?",
            "value": v,
        })
    if not parsed:
        return ""
    parsed.sort(key=lambda r: r["value"])
    bottom = parsed[:top_n]
    top = list(reversed(parsed[-top_n:]))
    head = (
        "<tr><th>Rank</th><th>Scenario</th><th>Model</th>"
        "<th>Output / value_label</th><th>Region</th><th>Value</th></tr>"
    )

    def _row(rank_label: str, r: dict) -> str:
        return (
            f"<tr><td>{html.escape(rank_label)}</td>"
            f"<td>{html.escape(r['scenario_id'])}</td>"
            f"<td>{html.escape(r['model_id'])}</td>"
            f"<td>{html.escape(r['output_key'])} · {html.escape(r['value_label'])}</td>"
            f"<td>{html.escape(r['unified_region'])}</td>"
            f"<td>{r['value']:g}</td></tr>"
        )

    body_top = "".join(_row(f"+{i+1}", r) for i, r in enumerate(top))
    body_bot = "".join(_row(f"-{i+1}", r) for i, r in enumerate(bottom))
    return (
        "<h3>Most-positively-affected unified regions</h3>"
        f"<table><thead>{head}</thead><tbody>{body_top}</tbody></table>"
        "<h3>Most-negatively-affected unified regions</h3>"
        f"<table><thead>{head}</thead><tbody>{body_bot}</tbody></table>"
    )


def write_index_html(
    run_id: str,
    figures: dict[str, Path],
    timeseries_pngs: list[Path],
    model_status_rows: list[dict],
    synthesis_md_path: Path,
    qualitative_dir: Path,
    regional_distribution_pngs: list[Path] | None = None,
    sectoral_distribution_pngs: list[Path] | None = None,
    synthesis_distributions_rows: list[dict] | None = None,
    unified_rows: list[dict] | None = None,
) -> Path:
    fig_dir = figures_root(run_id)
    out = fig_dir / "index.html"
    csv_dir_rel = "../csv"
    qual_dir_rel = "../qualitative"

    sections: list[str] = []

    # --- Header + summary ---
    sections.append(
        f'<section><h1>Hormuz pipeline visualisation — '
        f'<code>{html.escape(run_id)}</code></h1>'
        f'<p class="meta">Generated by '
        f'<code>slurm/scripts/visualize_results.py</code>. '
        f'Reads CSVs in <code>{csv_dir_rel}/</code> and qualitative '
        f'narratives in <code>{qual_dir_rel}/</code>.</p>'
        f'<p>{_summary_badges(model_status_rows)}</p>'
        f'</section>'
    )

    # --- Top-of-page synthesis markdown (if present) ---
    if synthesis_md_path.exists():
        try:
            md = synthesis_md_path.read_text(encoding="utf-8")
            sections.append(
                "<section class='narrative'>"
                + _md_to_html(md)
                + "</section>"
            )
        except Exception:
            pass

    # --- Run-wide figures ---
    fig_blocks: list[tuple[str, Path]] = []
    for label, key in (
        ("Model status by scenario", "status_scenario"),
        ("Model status by commodity system", "status_system"),
        ("Headline synthesised outcomes", "outcomes_grid"),
        ("Cross-model quantitative heatmap", "quant_heatmap"),
        ("Cross-model consistency flags", "consistency"),
    ):
        p = figures.get(key)
        if p and p.exists():
            fig_blocks.append((label, p))
    if fig_blocks:
        body = ""
        for label, p in fig_blocks:
            body += f"<h3>{html.escape(label)}</h3>" + _embed_image(p)
        sections.append(f"<section><h2>Run-wide figures</h2>{body}</section>")

    # --- Distributional impacts (regional + sectoral) ---
    dist_blocks: list[str] = []
    for label, key in (
        ("Regional impact heatmap (unified taxonomy, per-scenario panels)",
         "regional_heatmap"),
        ("Native -> unified region crosswalk audit", "regional_audit"),
    ):
        p = figures.get(key)
        if p and p.exists():
            dist_blocks.append(
                f"<h3>{html.escape(label)}</h3>" + _embed_image(p)
            )
    rd_pngs = sorted(regional_distribution_pngs or [])
    if rd_pngs:
        dist_blocks.append(
            "<h3>Per-scenario regional distribution</h3>"
            + "".join(_embed_image(p) for p in rd_pngs)
        )
    sd_pngs = sorted(sectoral_distribution_pngs or [])
    if sd_pngs:
        dist_blocks.append(
            "<h3>Per-scenario sectoral distribution</h3>"
            + "".join(_embed_image(p) for p in sd_pngs)
        )
    if unified_rows:
        ranking = _summarise_top_bottom_unified(unified_rows)
        if ranking:
            dist_blocks.append(ranking)
    if dist_blocks:
        sections.append(
            "<section><h2>Distributional impacts (regional & sectoral)</h2>"
            "<p class='meta'>Built from <code>regional_outcomes_unified.csv</code>, "
            "<code>regional_outcomes_native.csv</code>, "
            "<code>sectoral_outcomes.csv</code>, and "
            "<code>synthesis_distributions.csv</code>. Native model regions are "
            "rolled up via <code>configs/region_crosswalk.yaml</code>.</p>"
            + "".join(dist_blocks)
            + "</section>"
        )

    # --- Quantitative tables (top of CSVs) ---
    table_blocks: list[str] = []
    for label, fname in (
        ("Synthesis outcomes", "synthesis_outcomes.csv"),
        ("Model status", "model_status.csv"),
        ("Consistency flags", "consistency_flags.csv"),
    ):
        p = csv_root(run_id) / fname
        if p.exists():
            tbl = _csv_to_html_table(p)
            if tbl:
                table_blocks.append(
                    f"<details><summary>{html.escape(label)} "
                    f"(<code>{fname}</code>)</summary>{tbl}</details>"
                )
    if table_blocks:
        sections.append(
            "<section><h2>Quantitative tables</h2>"
            + "".join(table_blocks)
            + "</section>"
        )

    # --- Executive overview (Stage 5 second LLM pass on cross_scenario.md) ---
    exec_md = qualitative_dir / "user_executive_summary.md"
    if exec_md.exists():
        sections.append(
            "<section><h2>Executive overview (principal user)</h2>"
            "<p class='meta'>Generated by reading "
            "<code>cross_scenario.md</code> in a dedicated LLM pass "
            "(<code>user_executive_summary.md</code>).</p>"
            "<div class='narrative'>"
            + _md_to_html(exec_md.read_text(encoding="utf-8"))
            + "</div></section>"
        )

    # --- Per-scenario blocks: narrative + scenario time-series figures ---
    qual_files = sorted(qualitative_dir.glob("*.md")) if qualitative_dir.exists() else []
    _reserved_qualitative = frozenset(
        {"cross_scenario.md", "user_executive_summary.md"}
    )
    per_scenario_files = [
        p for p in qual_files if p.name not in _reserved_qualitative
    ]
    ts_by_scenario: dict[str, list[Path]] = defaultdict(list)
    for p in timeseries_pngs:
        # Filenames are <scenario>__<model>__<series>.png (see plot_timeseries_csvs).
        parts = p.stem.split("__", 1)
        if parts:
            ts_by_scenario[parts[0]].append(p)
    syn_dist_by_scenario: dict[str, list[dict]] = defaultdict(list)
    for r in synthesis_distributions_rows or []:
        syn_dist_by_scenario[r.get("scenario_id") or "unknown"].append(r)
    rd_by_scenario = {
        p.stem.replace("regional_distribution_", ""): p
        for p in (regional_distribution_pngs or [])
    }
    sd_by_scenario = {
        p.stem.replace("sectoral_distribution_", ""): p
        for p in (sectoral_distribution_pngs or [])
    }
    for q in per_scenario_files:
        scenario_id = q.stem
        body = "<div class='narrative'>" + _md_to_html(
            q.read_text(encoding="utf-8")
        ) + "</div>"
        ts_pngs = sorted(ts_by_scenario.get(scenario_id, []))
        if ts_pngs:
            body += "<h3>Time-series outputs</h3>"
            for p in ts_pngs:
                body += _embed_image(p)
        spotlight = ""
        rd = rd_by_scenario.get(scenario_id)
        sd = sd_by_scenario.get(scenario_id)
        notes = syn_dist_by_scenario.get(scenario_id) or []
        if rd or sd or notes:
            spotlight += "<h3>Regional / sectoral spotlight</h3>"
            if rd:
                spotlight += _embed_image(rd)
            if sd:
                spotlight += _embed_image(sd)
            if notes:
                seen_notes: set[tuple[str, str]] = set()
                bullet_lines: list[str] = []
                for n in notes:
                    note = (n.get("distribution_note") or "").strip()
                    if not note:
                        continue
                    key = (n.get("outcome_variable") or "", note)
                    if key in seen_notes:
                        continue
                    seen_notes.add(key)
                    bullet_lines.append(
                        f"<li><b>{html.escape(n.get('outcome_variable') or '?')}"
                        f"</b> ({html.escape(n.get('source_model_id') or '?')}): "
                        f"{html.escape(note)}</li>"
                    )
                if bullet_lines:
                    spotlight += (
                        "<p><b>Distributional notes from synthesis:</b></p>"
                        f"<ul>{''.join(bullet_lines)}</ul>"
                    )
        body += spotlight
        sections.append(
            f"<section id='scenario-{html.escape(scenario_id)}'>"
            f"<h2>Scenario · <code>{html.escape(scenario_id)}</code></h2>"
            f"{body}</section>"
        )

    # --- Cross-scenario narrative comparison (if present) ---
    cross_md = qualitative_dir / "cross_scenario.md"
    if cross_md.exists():
        sections.append(
            "<section><h2>Cross-scenario qualitative comparison</h2>"
            "<div class='narrative'>"
            + _md_to_html(cross_md.read_text(encoding="utf-8"))
            + "</div></section>"
        )

    # --- Footer with TOC of all generated artefacts ---
    artefact_links: list[str] = []
    for fname in sorted(p.name for p in fig_dir.glob("*.png")):
        artefact_links.append(f"<a href='{fname}'>figures/{fname}</a>")
    ts_dir = fig_dir / "timeseries"
    if ts_dir.exists():
        for fname in sorted(p.name for p in ts_dir.glob("*.png")):
            artefact_links.append(
                f"<a href='timeseries/{fname}'>figures/timeseries/{fname}</a>"
            )
    sections.append(
        "<section class='toc'><h2>All generated artefacts</h2>"
        + "".join(artefact_links)
        + "</section>"
    )

    if not HAS_MPL:
        sections.insert(
            1,
            "<section style='border-color:#d62728'>"
            "<h2 style='color:#d62728'>matplotlib not available</h2>"
            "<p>This dashboard was generated without matplotlib, so no PNG "
            "figures are embedded. Install the <code>[viz]</code> extra "
            "(<code>pip install -e \".[viz]\"</code>) and re-run "
            "<code>slurm/scripts/visualize_results.py</code> to produce the "
            "full chart set.</p></section>",
        )

    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8' />"
        f"<title>Hormuz pipeline · {html.escape(run_id)}</title>"
        f"<style>{_INDEX_CSS}</style></head><body>"
        + "".join(sections)
        + "</body></html>"
    )
    out.write_text(html_doc, encoding="utf-8")
    logger.info(f"wrote {out}")
    return out


# --------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-id",
        default=None,
        help="Pipeline run ID (default: $HORMUZ_RUN_ID or current UTC timestamp).",
    )
    parser.add_argument(
        "--no-timeseries",
        action="store_true",
        help="Skip per-CSV time-series PNGs (faster on runs with many series).",
    )
    args = parser.parse_args(argv)

    log_slurm_context()
    run_id = args.run_id or get_run_id()

    logger.info(f"=== Stage 6: Visualization (run_id={run_id}) ===")
    if not HAS_MPL:
        logger.warning(
            f"matplotlib not importable ({_MPL_ERR if not HAS_MPL else ''}); "
            "PNG figures will be skipped, dashboard will be text-only."
        )
    if not HAS_MARKDOWN:
        logger.info(
            "markdown package not available; narrative blocks will use a "
            "stdlib fallback renderer."
        )

    fig_dir = figures_root(run_id)
    csv_dir = csv_root(run_id)
    qual_dir = qualitative_root(run_id)

    if not csv_dir.exists():
        logger.warning(
            f"No CSV directory at {csv_dir}; did Stage 5 (export_results.py) run? "
            "Skipping visualization."
        )
        return 0

    model_status_rows = _read_csv(csv_dir / "model_status.csv")
    synthesis_rows = _read_csv(csv_dir / "synthesis_outcomes.csv")
    quantitative_rows = _read_csv(csv_dir / "quantitative_results.csv")
    consistency_rows = _read_csv(csv_dir / "consistency_flags.csv")
    regional_unified_rows = _read_csv(csv_dir / "regional_outcomes_unified.csv")
    regional_native_rows = _read_csv(csv_dir / "regional_outcomes_native.csv")
    sectoral_rows = _read_csv(csv_dir / "sectoral_outcomes.csv")
    synthesis_dist_rows = _read_csv(csv_dir / "synthesis_distributions.csv")
    uncertainty_rows = _read_csv(csv_dir / "uncertainty_bands.csv")

    figures: dict[str, Path] = {}
    try:
        p = plot_model_status_by_scenario(
            model_status_rows, fig_dir / "model_status_by_scenario.png"
        )
        if p:
            figures["status_scenario"] = p
        p = plot_model_status_by_system(
            model_status_rows, fig_dir / "model_status_by_system.png"
        )
        if p:
            figures["status_system"] = p
        p = plot_synthesis_outcomes_grid(
            synthesis_rows, fig_dir / "synthesis_outcomes_grid.png"
        )
        if p:
            figures["outcomes_grid"] = p
        p = plot_quantitative_heatmap(
            quantitative_rows, fig_dir / "quantitative_heatmap.png"
        )
        if p:
            figures["quant_heatmap"] = p
        p = plot_consistency_flags(
            consistency_rows, fig_dir / "consistency_flags.png"
        )
        if p:
            figures["consistency"] = p
        p = plot_uncertainty_error_bars(
            uncertainty_rows, fig_dir / "uncertainty_error_bars.png"
        )
        if p:
            figures["uncertainty_error_bars"] = p
        p = plot_synthesis_outcomes_with_bands(
            quantitative_rows, fig_dir / "synthesis_outcomes_with_bands.png"
        )
        if p:
            figures["uncertainty_outcomes_bars"] = p
        p = plot_regional_impact_heatmap(
            regional_unified_rows, fig_dir / "regional_impact_heatmap.png"
        )
        if p:
            figures["regional_heatmap"] = p
        p = plot_native_vs_unified_audit(
            regional_native_rows, fig_dir / "regional_crosswalk_audit.png"
        )
        if p:
            figures["regional_audit"] = p
        for label, p in figures.items():
            logger.info(f"wrote {p}")
    except Exception:
        logger.error("Run-wide figure generation failed:\n" + traceback.format_exc())

    regional_distribution_pngs: list[Path] = []
    sectoral_distribution_pngs: list[Path] = []
    try:
        regional_distribution_pngs = plot_regional_distribution_per_scenario(
            regional_unified_rows, fig_dir,
        )
        sectoral_distribution_pngs = plot_sectoral_distribution_per_scenario(
            sectoral_rows, fig_dir,
        )
        if regional_distribution_pngs:
            logger.info(
                f"wrote {len(regional_distribution_pngs)} per-scenario "
                f"regional distribution PNG(s)"
            )
        if sectoral_distribution_pngs:
            logger.info(
                f"wrote {len(sectoral_distribution_pngs)} per-scenario "
                f"sectoral distribution PNG(s)"
            )
    except Exception:
        logger.error(
            "Distributional figure generation failed:\n" + traceback.format_exc()
        )

    timeseries_pngs: list[Path] = []
    if not args.no_timeseries:
        try:
            timeseries_pngs = plot_timeseries_csvs(run_id)
        except Exception:
            logger.error("Timeseries figure generation failed:\n" + traceback.format_exc())

    try:
        write_index_html(
            run_id=run_id,
            figures=figures,
            timeseries_pngs=timeseries_pngs,
            model_status_rows=model_status_rows,
            synthesis_md_path=reports_root(run_id) / "synthesis.md",
            qualitative_dir=qual_dir,
            regional_distribution_pngs=regional_distribution_pngs,
            sectoral_distribution_pngs=sectoral_distribution_pngs,
            synthesis_distributions_rows=synthesis_dist_rows,
            unified_rows=regional_unified_rows,
        )
    except Exception:
        logger.error("HTML dashboard generation failed:\n" + traceback.format_exc())
        return 1

    logger.info(
        f"Visualization complete. Open: {figures_root(run_id) / 'index.html'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
