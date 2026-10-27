#!/usr/bin/env python3
"""Anchor-only cross-scenario comparison (Reviewer 2, point 3).

The model portfolio that contributed differs by scenario, so a naive
cross-scenario comparison mixes scenario effects with portfolio changes.
This script restricts the comparison to the "anchor" models that
completed under *every* scenario of the run and reports their headline
variables side by side, plus a portfolio table showing which non-anchor
models contributed where.

Inputs are the Stage 5 CSVs of one run (``csv/model_status.csv`` and
``csv/quantitative_results.csv``), so it runs on the artefacts already in
the repository::

    python scripts/revision/anchor_comparison.py \
        --report-dir data/20260504_222710 --out-dir docs/revision

Outputs (``anchor_comparison_<run_id>.{csv,md,tex,png}``):

* long-form CSV ``scenario_id, model_id, variable, value``;
* Markdown + LaTeX tables, one per variable (rows = scenarios, columns =
  anchor models);
* a multi-panel figure (one panel per variable, grouped bars by model).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SCENARIO_ORDER = [
    "swift_contained", "prolonged_contained", "swift_escalated",
    "prolonged_escalated", "infrastructure_collapse",
]
SCENARIO_SHORT = {
    "swift_contained": "A", "prolonged_contained": "B", "swift_escalated": "C",
    "prolonged_escalated": "D", "infrastructure_collapse": "E",
}
DEFAULT_VARIABLES = [
    "oil_price_change_pct",
    "peak_gdp_impact_pct",
    "peak_cpi_impact_pp",
    "gdp_impact_pct",
    "cpi_inflation_pct",
    "natural_gas_price_change_pct",
    "welfare_pct_change",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_anchors(status_rows: list[dict], scenarios: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Models with status completed in every scenario present in the run."""
    completed: dict[str, set[str]] = defaultdict(set)
    present: set[str] = set()
    for r in status_rows:
        present.add(r["scenario_id"])
        if (r.get("status") or "").lower() == "completed":
            completed[r["model_id"]].add(r["scenario_id"])
    scen = scenarios or [s for s in SCENARIO_ORDER if s in present] or sorted(present)
    anchors = sorted(m for m, s in completed.items() if set(scen) <= s)
    return anchors, scen


def portfolio_table(status_rows: list[dict], scenarios: list[str]) -> dict[str, list[str]]:
    completed: dict[str, set[str]] = defaultdict(set)
    for r in status_rows:
        if (r.get("status") or "").lower() == "completed":
            completed[r["model_id"]].add(r["scenario_id"])
    return {m: [s for s in scenarios if s in completed[m]] for m in sorted(completed)}


def extract_values(
    quant_rows: list[dict], anchors: list[str], scenarios: list[str], variables: list[str]
) -> list[dict[str, Any]]:
    out = []
    for r in quant_rows:
        if r.get("model_id") not in anchors or r.get("scenario_id") not in scenarios:
            continue
        if r.get("output_key") not in variables:
            continue
        if (r.get("is_numeric") or "").lower() != "true":
            continue
        try:
            v = float(r["value_numeric"])
        except (TypeError, ValueError):
            continue
        out.append({"scenario_id": r["scenario_id"], "model_id": r["model_id"],
                    "variable": r["output_key"], "value": v})
    return out


def _pivot(values: list[dict], variable: str, scenarios: list[str], anchors: list[str]) -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {s: {} for s in scenarios}
    for v in values:
        if v["variable"] == variable:
            table[v["scenario_id"]][v["model_id"]] = v["value"]
    return table


def render_markdown(run_id: str, anchors: list[str], scenarios: list[str], variables: list[str],
                    values: list[dict], portfolio: dict[str, list[str]]) -> str:
    lines = [f"# Anchor-only comparison for run `{run_id}`", "",
             f"Anchors (completed in all {len(scenarios)} scenarios): " + ", ".join(f"`{a}`" for a in anchors), ""]
    for var in variables:
        table = _pivot(values, var, scenarios, anchors)
        models = [m for m in anchors if any(m in table[s] for s in scenarios)]
        if not models:
            continue
        lines += [f"## `{var}`", "", "| scenario | " + " | ".join(f"`{m}`" for m in models) + " |",
                  "|---|" + "|".join("---" for _ in models) + "|"]
        for s in scenarios:
            lines.append(f"| {SCENARIO_SHORT.get(s, s)} ({s}) | " + " | ".join(
                f"{table[s][m]:.4g}" if m in table[s] else "-" for m in models) + " |")
        lines.append("")
    lines += ["## Portfolio: scenarios in which each model completed", "", "| model | anchor | scenarios |", "|---|---|---|"]
    for m, scen in portfolio.items():
        lines.append(f"| `{m}` | {'yes' if m in anchors else ''} | {', '.join(SCENARIO_SHORT.get(s, s) for s in scen)} |")
    lines.append("")
    return "\n".join(lines)


def _tex(s: str) -> str:
    return str(s).replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")


def render_latex(run_id: str, anchors: list[str], scenarios: list[str], variables: list[str], values: list[dict]) -> str:
    out = ["% Generated by scripts/revision/anchor_comparison.py; do not edit by hand."]
    for var in variables:
        table = _pivot(values, var, scenarios, anchors)
        models = [m for m in anchors if any(m in table[s] for s in scenarios)]
        if not models:
            continue
        out += ["\\begin{table}[t]", "\\centering", "\\small",
                f"\\caption{{{_tex(var)} across scenarios, anchor models only (run {_tex(run_id)}).}}",
                f"\\label{{tab:anchor_{var}}}",
                "\\begin{tabular}{l" + "r" * len(models) + "}", "\\toprule",
                "Scenario & " + " & ".join(f"\\texttt{{{_tex(m)}}}" for m in models) + " \\\\", "\\midrule"]
        for s in scenarios:
            out.append(f"{SCENARIO_SHORT.get(s, s)} & " + " & ".join(
                f"{table[s][m]:.4g}" if m in table[s] else "--" for m in models) + " \\\\")
        out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(out)


def plot(values: list[dict], anchors: list[str], scenarios: list[str], variables: list[str], out: Path) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return None
    panels = [v for v in variables if any(x["variable"] == v for x in values)]
    if not panels:
        return None
    from matplotlib.patches import Patch

    ncols = 2 if len(panels) > 1 else 1
    nrows = (len(panels) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.0 * ncols, 3.2 * nrows + 0.9), squeeze=False)
    width = 0.8 / max(1, len(anchors))
    cmap = plt.get_cmap("tab10")
    colors = {m: cmap(i % 10) for i, m in enumerate(anchors)}  # stable colour per anchor
    for i, var in enumerate(panels):
        ax = axes[i // ncols][i % ncols]
        table = _pivot(values, var, scenarios, anchors)
        models = [m for m in anchors if any(m in table[s] for s in scenarios)]
        for j, m in enumerate(models):
            xs = [k + (j - (len(models) - 1) / 2) * width for k in range(len(scenarios))]
            ys = [table[s].get(m, float("nan")) for s in scenarios]
            ax.bar(xs, ys, width=width, color=colors[m])
        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels([SCENARIO_SHORT.get(s, s) for s in scenarios])
        ax.set_title(var, fontsize=9)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.grid(True, axis="y", alpha=0.3)
    for k in range(len(panels), nrows * ncols):
        axes[k // ncols][k % ncols].set_visible(False)
    handles = [Patch(facecolor=colors[m], label=m) for m in anchors]
    fig.legend(handles=handles, loc="lower center", ncol=min(len(anchors), 5), fontsize=8, frameon=False,
               bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("Anchor models across scenarios (same portfolio in every panel)", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def run(report_dir: Path, out_dir: Path, run_id: str | None = None,
        anchors: list[str] | None = None, variables: list[str] | None = None) -> dict[str, Any]:
    csv_dir = report_dir / "csv"
    status_rows = _read_csv(csv_dir / "model_status.csv")
    quant_rows = _read_csv(csv_dir / "quantitative_results.csv")
    if not status_rows:
        raise FileNotFoundError(f"No model_status.csv under {csv_dir}")
    run_id = run_id or report_dir.name
    auto_anchors, scenarios = find_anchors(status_rows)
    anchors = anchors or auto_anchors
    variables = variables or DEFAULT_VARIABLES
    values = extract_values(quant_rows, anchors, scenarios, variables)
    portfolio = portfolio_table(status_rows, scenarios)

    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"anchor_comparison_{run_id}"
    with open(base.with_suffix(".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "model_id", "variable", "value"])
        w.writeheader()
        w.writerows(values)
    base.with_suffix(".md").write_text(render_markdown(run_id, anchors, scenarios, variables, values, portfolio))
    base.with_suffix(".tex").write_text(render_latex(run_id, anchors, scenarios, variables, values))
    png = plot(values, anchors, scenarios, variables, base.with_suffix(".png"))
    summary = {"run_id": run_id, "anchors": anchors, "scenarios": scenarios, "variables": variables,
               "n_values": len(values), "portfolio": portfolio, "png": str(png) if png else None}
    base.with_suffix(".json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--report-dir", required=True, help="Run report directory containing csv/.")
    p.add_argument("--out-dir", default="docs/revision")
    p.add_argument("--run-id", default=None)
    p.add_argument("--anchors", default=None, help="Comma-separated model ids; default = completed in every scenario.")
    p.add_argument("--variables", default=None, help="Comma-separated output keys.")
    args = p.parse_args(argv)
    summary = run(
        Path(args.report_dir), Path(args.out_dir), args.run_id,
        anchors=args.anchors.split(",") if args.anchors else None,
        variables=args.variables.split(",") if args.variables else None,
    )
    print(json.dumps({k: summary[k] for k in ("run_id", "anchors", "scenarios", "n_values", "png")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
