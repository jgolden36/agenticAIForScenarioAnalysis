#!/usr/bin/env python3
"""Cross-week visualisation of how the pipeline's model predictions
evolve as new weekly news arrives.

This is the *temporal* counterpart to ``visualize_results.py``. Where
that script renders a single ``HORMUZ_RUN_ID``'s figures and dashboard,
this script aggregates the per-week artefacts produced by
``weekly_news_pipeline.job`` / ``empire_ai_alpha_weekly.job`` and
plots the evolution of headline outcomes, scalar model outputs,
model-run status, and consistency flags across the weekly backfill
window.

Inputs
------
For each week, the per-week pipeline rerun (run_id ``weekly_<YYYYMMDD>``)
produces the standard Stage 5 CSVs at::

    data/reports/weekly_<YYYYMMDD>/csv/synthesis_outcomes.csv
    data/reports/weekly_<YYYYMMDD>/csv/quantitative_results.csv
    data/reports/weekly_<YYYYMMDD>/csv/model_status.csv
    data/reports/weekly_<YYYYMMDD>/csv/consistency_flags.csv

This script discovers every ``weekly_*`` run under ``data/reports/``,
sorts them chronologically, and writes:

    data/reports/weekly_evolution/<batch_id>/figures/
        synthesis_outcome_evolution__<scope>__<time_horizon>.png
        quantitative_evolution__top_movers.png
        model_status_evolution.png
        consistency_flags_evolution.png
        scenario_divergence__<variable>.png  (one per high-volatility variable)
        index.html
    data/reports/weekly_evolution/<batch_id>/csv/
        synthesis_outcomes_long.csv         (week, scenario, scope, horizon, var, value)
        quantitative_long.csv               (week, scenario, model, key, value)
        model_status_long.csv               (week, scenario, status, count)
        consistency_flags_long.csv          (week, scenario, flag, severity)

Usage
-----

    python slurm/scripts/visualize_weekly_evolution.py
    python slurm/scripts/visualize_weekly_evolution.py --batch-id 20260504
    python slurm/scripts/visualize_weekly_evolution.py \
        --reports-root /custom/path \
        --output-dir /tmp/cross_week

The script is best-effort: a missing matplotlib install drops PNGs but
still writes the long-form CSVs and an HTML dashboard with embedded
tables.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import get_project_root, log_slurm_context, logger  # noqa: E402

try:
    import matplotlib  # noqa: WPS433
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: WPS433
    HAS_MPL = True
except Exception as _mpl_exc:  # pragma: no cover
    plt = None  # type: ignore[assignment]
    HAS_MPL = False
    _MPL_ERR = str(_mpl_exc)


WEEKLY_RUN_RE = re.compile(r"^weekly_(\d{8})$")


# --------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------

def reports_root() -> Path:
    return get_project_root() / "data" / "reports"


def output_root(batch_id: str, override: Path | None = None) -> Path:
    if override is not None:
        d = override
    else:
        d = reports_root() / "weekly_evolution" / batch_id
    (d / "figures").mkdir(parents=True, exist_ok=True)
    (d / "csv").mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------
# Discovery + CSV loading (stdlib only).
# --------------------------------------------------------------------

def discover_weeks(root: Path) -> list[tuple[str, Path]]:
    """Return [(week_iso_date, run_dir)] sorted ascending."""
    if not root.exists():
        return []
    weeks: list[tuple[str, Path]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        m = WEEKLY_RUN_RE.match(child.name)
        if not m:
            continue
        tag = m.group(1)
        try:
            iso = datetime.strptime(tag, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            continue
        weeks.append((iso, child))
    weeks.sort(key=lambda x: x[0])
    return weeks


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as exc:
        logger.warning(f"could not read {path}: {exc}")
        return []


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
    cleaned = s.replace(",", "").replace("%", "").replace("$", "")
    cleaned = re.sub(r"[A-Za-z/]+$", "", cleaned).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# --------------------------------------------------------------------
# Long-form aggregation across weeks.
# --------------------------------------------------------------------

def aggregate_long_form(weeks: list[tuple[str, Path]]) -> dict[str, list[dict]]:
    """Walk every week's CSVs and emit four long-form tables."""
    synthesis_long: list[dict] = []
    quant_long: list[dict] = []
    status_long: list[dict] = []
    flags_long: list[dict] = []

    for week_date, run_dir in weeks:
        csv_dir = run_dir / "csv"
        if not csv_dir.exists():
            logger.info(f"[{week_date}] no csv/ subdir under {run_dir}; skipping")
            continue

        # synthesis_outcomes.csv -> (scenario, time_horizon, scope, variable, value)
        for r in _read_csv(csv_dir / "synthesis_outcomes.csv"):
            v = _coerce_float(r.get("value"))
            if v is None:
                continue
            synthesis_long.append({
                "week": week_date,
                "scenario_id": r.get("scenario_id") or "",
                "time_horizon": r.get("time_horizon") or "",
                "outcome_scope": r.get("outcome_scope") or "",
                "outcome_variable": r.get("outcome_variable") or "",
                "value": v,
                "source_model_id": r.get("source_model_id") or "",
            })

        # quantitative_results.csv -> (scenario, model, key, numeric value)
        for r in _read_csv(csv_dir / "quantitative_results.csv"):
            if (r.get("is_numeric") or "").lower() != "true":
                continue
            v = _coerce_float(r.get("value_numeric"))
            if v is None:
                continue
            quant_long.append({
                "week": week_date,
                "scenario_id": r.get("scenario_id") or "",
                "model_id": r.get("model_id") or "",
                "output_key": r.get("output_key") or "",
                "value": v,
            })

        # model_status.csv -> (week, scenario, status, count)
        status_counts: dict[tuple[str, str], int] = defaultdict(int)
        for r in _read_csv(csv_dir / "model_status.csv"):
            scen = r.get("scenario_id") or "unknown"
            status = (r.get("status") or "unknown").lower()
            status_counts[(scen, status)] += 1
        for (scen, status), n in status_counts.items():
            status_long.append({
                "week": week_date,
                "scenario_id": scen,
                "status": status,
                "count": n,
            })

        # consistency_flags.csv -> (week, scenario, flag_kind, severity)
        for r in _read_csv(csv_dir / "consistency_flags.csv"):
            flags_long.append({
                "week": week_date,
                "scenario_id": r.get("scenario_id") or "",
                "flag_kind": r.get("kind") or r.get("flag_kind") or r.get("type") or "",
                "severity": r.get("severity") or "",
                "message": r.get("message") or r.get("description") or "",
            })

    return {
        "synthesis": synthesis_long,
        "quantitative": quant_long,
        "status": status_long,
        "flags": flags_long,
    }


def write_long_csv(path: Path, header: list[str], rows: list[dict]) -> Path | None:
    if not rows:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    logger.info(f"wrote {path}  ({len(rows)} rows)")
    return path


# --------------------------------------------------------------------
# Plotting.
#
# Each plot helper takes a long-form row list and a destination path.
# Returns the path on success, None otherwise (missing matplotlib,
# empty input, or all-degenerate series).
# --------------------------------------------------------------------

_SCENARIO_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
]


def _scenario_colors(scenarios: list[str]) -> dict[str, str]:
    return {s: _SCENARIO_PALETTE[i % len(_SCENARIO_PALETTE)]
            for i, s in enumerate(sorted(scenarios))}


def plot_synthesis_outcome_evolution(
    rows: list[dict], out_dir: Path
) -> list[Path]:
    """One PNG per (outcome_scope, time_horizon).

    Each panel shows one line per scenario × outcome_variable, x = week.
    This is the headline "how do scenario predictions evolve as news
    arrives" view.
    """
    if not HAS_MPL or not rows:
        return []

    # Group by (scope, horizon).
    panels: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        panels[(r["outcome_scope"], r["time_horizon"])].append(r)

    out_paths: list[Path] = []
    for (scope, horizon), panel_rows in sorted(panels.items()):
        # Within a panel: one subplot per outcome_variable. Each series
        # is one scenario over weeks.
        by_var: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        for r in panel_rows:
            by_var[r["outcome_variable"]][r["scenario_id"]][r["week"]] = r["value"]
        if not by_var:
            continue
        variables = sorted(by_var.keys())
        n = len(variables)
        ncols = 2 if n > 1 else 1
        nrows = (n + ncols - 1) // ncols
        fig, axes = plt.subplots(
            nrows, ncols,
            figsize=(7.5 * ncols, 3.2 * nrows + 0.5),
            squeeze=False,
        )
        all_scenarios = sorted({s for d in by_var.values() for s in d.keys()})
        colors = _scenario_colors(all_scenarios)
        all_weeks = sorted({r["week"] for r in panel_rows})

        for idx, var in enumerate(variables):
            ax = axes[idx // ncols][idx % ncols]
            for scen, week_vals in sorted(by_var[var].items()):
                xs = [w for w in all_weeks if w in week_vals]
                ys = [week_vals[w] for w in xs]
                if len(xs) < 1:
                    continue
                ax.plot(
                    xs, ys, marker="o",
                    color=colors.get(scen, "#444"),
                    label=scen,
                )
            ax.set_title(var, fontsize=10)
            ax.tick_params(axis="x", rotation=30, labelsize=7)
            ax.tick_params(axis="y", labelsize=8)
            ax.grid(True, alpha=0.25)
        # Hide unused subplots.
        for idx in range(n, nrows * ncols):
            axes[idx // ncols][idx % ncols].set_visible(False)
        # Single legend.
        handles = [
            plt.Line2D([0], [0], color=colors[s], marker="o", label=s)
            for s in all_scenarios
        ]
        fig.legend(
            handles=handles,
            loc="lower center",
            ncol=min(len(all_scenarios), 6),
            bbox_to_anchor=(0.5, -0.02),
            fontsize=9,
        )
        fig.suptitle(
            f"Synthesis outcome evolution — scope={scope}, horizon={horizon}",
            fontsize=12,
        )
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        slug = re.sub(r"[^A-Za-z0-9]+", "_",
                      f"{scope}_{horizon}").strip("_") or "panel"
        out = out_dir / f"synthesis_outcome_evolution__{slug}.png"
        fig.savefig(out, dpi=140, bbox_inches="tight")
        plt.close(fig)
        out_paths.append(out)
        logger.info(f"wrote {out}")
    return out_paths


def plot_quantitative_top_movers(
    rows: list[dict], out: Path, top_k: int = 16
) -> Path | None:
    """One PNG showing the ``top_k`` (model_id, output_key) pairs that
    move the most across weeks (largest range / mean ratio).

    Each subplot has one line per scenario, x = week, y = value.
    """
    if not HAS_MPL or not rows:
        return None

    # Group: (model, key, scenario) -> {week: value}
    series: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for r in rows:
        series[(r["model_id"], r["output_key"], r["scenario_id"])][r["week"]] = r["value"]

    # Score variability per (model, key) collapsed across scenarios:
    # use the max over scenarios of (max-min)/(|mean|+epsilon) so we
    # surface variables where any scenario shows movement, not just
    # ones with high absolute variance.
    by_var: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (model, key, scen), week_vals in series.items():
        vals = list(week_vals.values())
        if len(vals) < 2:
            continue
        spread = max(vals) - min(vals)
        denom = abs(sum(vals) / len(vals)) + 1e-9
        by_var[(model, key)].append(spread / denom)

    if not by_var:
        return None

    ranked = sorted(by_var.items(), key=lambda kv: max(kv[1]), reverse=True)
    selected = [k for k, _ in ranked[:top_k]]
    if not selected:
        return None

    all_scenarios = sorted({s for (_, _, s) in series.keys()})
    colors = _scenario_colors(all_scenarios)
    all_weeks = sorted({w for d in series.values() for w in d.keys()})

    n = len(selected)
    ncols = 2 if n > 1 else 1
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(7.5 * ncols, 2.8 * nrows + 0.6),
        squeeze=False,
    )
    for idx, (model, key) in enumerate(selected):
        ax = axes[idx // ncols][idx % ncols]
        for scen in all_scenarios:
            week_vals = series.get((model, key, scen), {})
            xs = [w for w in all_weeks if w in week_vals]
            ys = [week_vals[w] for w in xs]
            if not xs:
                continue
            ax.plot(
                xs, ys, marker="o", color=colors[scen], label=scen,
            )
        ax.set_title(f"{model} · {key}", fontsize=9)
        ax.tick_params(axis="x", rotation=30, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)
        ax.grid(True, alpha=0.25)
    for idx in range(n, nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    handles = [
        plt.Line2D([0], [0], color=colors[s], marker="o", label=s)
        for s in all_scenarios
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=min(len(all_scenarios), 6),
        bbox_to_anchor=(0.5, -0.01),
        fontsize=9,
    )
    fig.suptitle(
        f"Quantitative model-output trajectories — top {len(selected)} "
        "movers across the backfill window",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"wrote {out}")
    return out


def plot_model_status_evolution(rows: list[dict], out: Path) -> Path | None:
    """Stacked bar per week summing completed/skipped/failed model
    runs across scenarios. Tells you whether the pipeline got
    healthier or sicker as the crisis unfolded."""
    if not HAS_MPL or not rows:
        return None
    by_week: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_week[r["week"]][r["status"]] += int(r.get("count") or 0)
    weeks = sorted(by_week.keys())
    statuses = ["completed", "skipped", "failed"]
    colors = {"completed": "#2ca02c", "skipped": "#ff7f0e", "failed": "#d62728"}

    fig, ax = plt.subplots(figsize=(max(8, len(weeks) * 1.0), 4.5))
    bottoms = [0] * len(weeks)
    for status in statuses:
        vals = [by_week[w].get(status, 0) for w in weeks]
        ax.bar(
            weeks, vals, bottom=bottoms,
            label=status, color=colors[status],
        )
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Model runs (across all scenarios)")
    ax.set_xlabel("Week")
    ax.set_title("Model run status by week")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    logger.info(f"wrote {out}")
    return out


def plot_consistency_flags_evolution(rows: list[dict], out: Path) -> Path | None:
    """Line per scenario × week showing flag count, with a stacked
    severity breakdown."""
    if not HAS_MPL or not rows:
        return None
    by_week_severity: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        sev = (r.get("severity") or "info").lower()
        by_week_severity[r["week"]][sev] += 1
    weeks = sorted(by_week_severity.keys())
    severities = ["error", "warning", "info"]
    colors = {"error": "#d62728", "warning": "#ff7f0e", "info": "#1f77b4"}

    fig, ax = plt.subplots(figsize=(max(8, len(weeks) * 1.0), 4.5))
    bottoms = [0] * len(weeks)
    for sev in severities:
        vals = [by_week_severity[w].get(sev, 0) for w in weeks]
        if not any(vals):
            continue
        ax.bar(
            weeks, vals, bottom=bottoms,
            label=sev, color=colors.get(sev, "#888"),
        )
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylabel("Consistency flags")
    ax.set_xlabel("Week")
    ax.set_title("Cross-model consistency flags by week")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    logger.info(f"wrote {out}")
    return out


def plot_scenario_divergence(
    rows: list[dict], out_dir: Path, top_k: int = 6
) -> list[Path]:
    """Per-variable scenario divergence plot.

    For each of the top_k synthesis variables with the highest
    cross-scenario spread (averaged over weeks), plot all scenarios on
    one chart over time. This is the "are scenarios pulling apart or
    converging?" view.
    """
    if not HAS_MPL or not rows:
        return []
    by_var: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for r in rows:
        by_var[r["outcome_variable"]][r["scenario_id"]][r["week"]] = r["value"]

    # Score: average across weeks of cross-scenario spread.
    scored: list[tuple[str, float]] = []
    for var, by_scen in by_var.items():
        all_weeks = sorted({w for d in by_scen.values() for w in d.keys()})
        spreads: list[float] = []
        for w in all_weeks:
            vals = [d[w] for d in by_scen.values() if w in d]
            if len(vals) >= 2:
                spreads.append(max(vals) - min(vals))
        if not spreads:
            continue
        scored.append((var, sum(spreads) / len(spreads)))
    if not scored:
        return []
    scored.sort(key=lambda kv: kv[1], reverse=True)

    out_paths: list[Path] = []
    all_scenarios = sorted({s for d in by_var.values() for s in d.keys()})
    colors = _scenario_colors(all_scenarios)

    for var, _score in scored[:top_k]:
        by_scen = by_var[var]
        all_weeks = sorted({w for d in by_scen.values() for w in d.keys()})
        if len(all_weeks) < 2:
            continue
        fig, ax = plt.subplots(figsize=(max(7, len(all_weeks) * 0.9), 4.5))
        for scen in all_scenarios:
            week_vals = by_scen.get(scen, {})
            xs = [w for w in all_weeks if w in week_vals]
            ys = [week_vals[w] for w in xs]
            if not xs:
                continue
            ax.plot(
                xs, ys, marker="o", color=colors[scen], label=scen, linewidth=2,
            )
        # Shade the cross-scenario range per week to highlight divergence.
        per_week_min: list[float] = []
        per_week_max: list[float] = []
        x_band: list[str] = []
        for w in all_weeks:
            vals = [d[w] for d in by_scen.values() if w in d]
            if len(vals) >= 2:
                per_week_min.append(min(vals))
                per_week_max.append(max(vals))
                x_band.append(w)
        if x_band:
            ax.fill_between(
                x_band, per_week_min, per_week_max,
                alpha=0.08, color="#444", label="cross-scenario spread",
            )
        ax.set_title(f"Scenario divergence — {var}")
        ax.set_xlabel("Week")
        ax.set_ylabel("Value")
        ax.tick_params(axis="x", rotation=30)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        slug = re.sub(r"[^A-Za-z0-9]+", "_", var).strip("_") or "var"
        out = out_dir / f"scenario_divergence__{slug}.png"
        fig.savefig(out, dpi=140)
        plt.close(fig)
        out_paths.append(out)
        logger.info(f"wrote {out}")
    return out_paths


# --------------------------------------------------------------------
# HTML dashboard
# --------------------------------------------------------------------

_HTML_HEAD_TEMPLATE = """\
<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Hormuz weekly evolution — __BATCH__</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       margin: 1.5rem auto; max-width: 1200px; padding: 0 1.5rem; color: #222; }
h1 { border-bottom: 1px solid #ccc; padding-bottom: 0.4rem; }
h2 { margin-top: 2rem; border-left: 4px solid #1f77b4; padding-left: 0.6rem; }
img.figure { max-width: 100%; height: auto; display: block; margin: 0.6rem 0; }
.meta { color: #666; font-size: 0.9rem; }
table { border-collapse: collapse; margin: 0.6rem 0; font-size: 0.85rem; }
th, td { border: 1px solid #ddd; padding: 0.3rem 0.55rem; text-align: left; }
th { background: #f5f5f5; }
code { background: #f3f3f3; padding: 0 0.25rem; border-radius: 3px; }
.badge { display: inline-block; padding: 0.2rem 0.55rem; border-radius: 4px;
         color: #fff; font-size: 0.8rem; margin-right: 0.4rem; }
.badge.completed { background: #2ca02c; }
.badge.skipped   { background: #ff7f0e; }
.badge.failed    { background: #d62728; }
.badge.unknown   { background: #7f7f7f; }
</style></head><body>
"""


def _embed_image(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return (f'<img class="figure" alt="{html.escape(path.name)}" '
            f'src="data:image/png;base64,{b64}" />')


def _summary_table(weeks: list[tuple[str, Path]]) -> str:
    if not weeks:
        return "<p class='meta'>No weekly runs discovered.</p>"
    rows = "".join(
        f"<tr><td>{html.escape(d)}</td><td><code>weekly_{d.replace('-', '')}"
        f"</code></td><td><code>{html.escape(str(p.relative_to(reports_root().parent)))}"
        f"</code></td></tr>"
        for d, p in weeks
    )
    return (
        "<table><thead><tr><th>Week</th><th>Run ID</th><th>Reports dir</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )


def write_dashboard(
    out_dir: Path,
    batch_id: str,
    weeks: list[tuple[str, Path]],
    long_csv_paths: dict[str, Path | None],
    figures: list[tuple[str, Path]],
    divergence_pngs: list[Path],
    synthesis_evolution_pngs: list[Path],
) -> Path:
    fig_dir = out_dir / "figures"
    csv_dir_rel = "../csv"

    sections: list[str] = []
    sections.append(
        f"<section><h1>Hormuz crisis — weekly evolution dashboard "
        f"(<code>{html.escape(batch_id)}</code>)</h1>"
        f"<p class='meta'>Generated by "
        f"<code>slurm/scripts/visualize_weekly_evolution.py</code>. "
        f"Aggregates per-week artefacts from <code>data/reports/weekly_*</code> "
        f"so analysts can see how the pipeline's predictions evolve as new "
        f"intelligence arrives.</p>"
        f"<p class='meta'>Generated at "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
        f"from {len(weeks)} weekly run(s).</p></section>"
    )

    sections.append(
        "<section><h2>Weekly runs aggregated</h2>"
        + _summary_table(weeks)
        + "</section>"
    )

    if synthesis_evolution_pngs:
        body = (
            "<p class='meta'>Each panel grid shows one combination of "
            "<code>(outcome_scope, time_horizon)</code>. Within a panel, "
            "subplots are headline outcome variables; lines are colour-coded "
            "by scenario; the x-axis is the calendar week. This is the "
            "primary view for tracking how scenario-conditioned forecasts "
            "shift as news arrives.</p>"
        )
        for p in synthesis_evolution_pngs:
            body += f"<h3>{html.escape(p.stem)}</h3>" + _embed_image(p)
        sections.append(
            "<section><h2>Synthesis outcome evolution</h2>" + body + "</section>"
        )

    if divergence_pngs:
        body = (
            "<p class='meta'>Headline outcome variables ranked by average "
            "cross-scenario spread. The shaded band is the per-week "
            "min-max range across scenarios — narrowing means scenarios "
            "are converging on a single forecast, widening means they are "
            "pulling apart.</p>"
        )
        for p in divergence_pngs:
            body += f"<h3>{html.escape(p.stem)}</h3>" + _embed_image(p)
        sections.append(
            "<section><h2>Scenario divergence per outcome</h2>" + body + "</section>"
        )

    health_blocks: list[tuple[str, Path]] = [
        (label, p) for (label, p) in figures
        if p.exists() and ("model_status" in p.name or "consistency" in p.name)
    ]
    if health_blocks:
        body = ""
        for label, p in health_blocks:
            body += f"<h3>{html.escape(label)}</h3>" + _embed_image(p)
        sections.append(
            "<section><h2>Pipeline health over time</h2>" + body + "</section>"
        )

    quant_blocks = [(label, p) for (label, p) in figures
                    if p.exists() and "top_movers" in p.name]
    if quant_blocks:
        body = (
            "<p class='meta'>Top model-output keys ranked by relative "
            "spread <code>(max-min)/|mean|</code> across the backfill "
            "window. Each panel is one (model, key); lines are scenarios.</p>"
        )
        for label, p in quant_blocks:
            body += f"<h3>{html.escape(label)}</h3>" + _embed_image(p)
        sections.append(
            "<section><h2>Quantitative model output trajectories</h2>"
            + body + "</section>"
        )

    csv_links: list[str] = []
    for label, key in (
        ("Synthesis outcomes (long form)", "synthesis"),
        ("Quantitative model outputs (long form)", "quantitative"),
        ("Model status counts (long form)", "status"),
        ("Consistency flags (long form)", "flags"),
    ):
        p = long_csv_paths.get(key)
        if p is not None and p.exists():
            rel = os.path.relpath(p, fig_dir)
            csv_links.append(f"<li>{html.escape(label)}: <code>{html.escape(rel)}</code></li>")
    if csv_links:
        sections.append(
            "<section><h2>Long-form CSV exports</h2>"
            f"<p class='meta'>All long-form tables under "
            f"<code>{csv_dir_rel}/</code>. Importable into pandas / R for "
            f"custom downstream analysis.</p><ul>"
            + "".join(csv_links)
            + "</ul></section>"
        )

    out_path = fig_dir / "index.html"
    head = _HTML_HEAD_TEMPLATE.replace("__BATCH__", html.escape(batch_id))
    out_path.write_text(
        head + "\n".join(sections) + "</body></html>",
        encoding="utf-8",
    )
    logger.info(f"wrote {out_path}")
    return out_path


# --------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-id",
        default=None,
        help=(
            "Batch tag for the output folder "
            "(default: $HORMUZ_BATCH_ID or current UTC timestamp)."
        ),
    )
    parser.add_argument(
        "--reports-root",
        default=None,
        help=(
            "Override the directory scanned for weekly_<YYYYMMDD> runs "
            "(default: <project>/data/reports)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Custom output directory; default is "
            "data/reports/weekly_evolution/<batch_id>/."
        ),
    )
    parser.add_argument(
        "--top-quant",
        type=int,
        default=16,
        help="How many top-mover (model, key) pairs to plot (default: 16).",
    )
    parser.add_argument(
        "--top-divergence",
        type=int,
        default=6,
        help="How many highest-spread synthesis variables to plot (default: 6).",
    )
    args = parser.parse_args(argv)

    log_slurm_context()

    batch_id = (
        args.batch_id
        or os.environ.get("HORMUZ_BATCH_ID")
        or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )

    src_root = Path(args.reports_root) if args.reports_root else reports_root()
    weeks = discover_weeks(src_root)
    logger.info(
        f"=== Cross-week visualisation (batch_id={batch_id}, "
        f"weeks_found={len(weeks)}) ==="
    )
    if not weeks:
        logger.warning(
            f"No weekly_<YYYYMMDD> run directories found under {src_root}. "
            "Nothing to plot."
        )
        return 0

    out_root = output_root(
        batch_id, Path(args.output_dir) if args.output_dir else None
    )
    fig_dir = out_root / "figures"
    csv_dir = out_root / "csv"

    long_form = aggregate_long_form(weeks)
    long_csv_paths: dict[str, Path | None] = {
        "synthesis": write_long_csv(
            csv_dir / "synthesis_outcomes_long.csv",
            ["week", "scenario_id", "time_horizon", "outcome_scope",
             "outcome_variable", "value", "source_model_id"],
            long_form["synthesis"],
        ),
        "quantitative": write_long_csv(
            csv_dir / "quantitative_long.csv",
            ["week", "scenario_id", "model_id", "output_key", "value"],
            long_form["quantitative"],
        ),
        "status": write_long_csv(
            csv_dir / "model_status_long.csv",
            ["week", "scenario_id", "status", "count"],
            long_form["status"],
        ),
        "flags": write_long_csv(
            csv_dir / "consistency_flags_long.csv",
            ["week", "scenario_id", "flag_kind", "severity", "message"],
            long_form["flags"],
        ),
    }

    if not HAS_MPL:
        logger.warning(
            f"matplotlib not importable ({_MPL_ERR}); PNG figures skipped, "
            "long-form CSVs and HTML index still written."
        )

    synthesis_evolution_pngs = plot_synthesis_outcome_evolution(
        long_form["synthesis"], fig_dir
    )

    quant_top = plot_quantitative_top_movers(
        long_form["quantitative"], fig_dir / "quantitative_evolution__top_movers.png",
        top_k=args.top_quant,
    )
    status_evo = plot_model_status_evolution(
        long_form["status"], fig_dir / "model_status_evolution.png",
    )
    flags_evo = plot_consistency_flags_evolution(
        long_form["flags"], fig_dir / "consistency_flags_evolution.png",
    )
    divergence_pngs = plot_scenario_divergence(
        long_form["synthesis"], fig_dir, top_k=args.top_divergence,
    )

    figures: list[tuple[str, Path]] = []
    if quant_top:
        figures.append(("Quantitative top movers", quant_top))
    if status_evo:
        figures.append(("Model status evolution", status_evo))
    if flags_evo:
        figures.append(("Consistency flag evolution", flags_evo))

    write_dashboard(
        out_root,
        batch_id=batch_id,
        weeks=weeks,
        long_csv_paths=long_csv_paths,
        figures=figures,
        divergence_pngs=divergence_pngs,
        synthesis_evolution_pngs=synthesis_evolution_pngs,
    )

    logger.info(
        f"Cross-week visualisation complete. Open "
        f"{(out_root / 'figures' / 'index.html').resolve()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
