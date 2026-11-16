"""Compare scenario model outputs with observed crisis-period prices.

Report-only: no model is changed or re-run. For each price that a model
in the run reports, the table puts the model's crisis peak (level and
percent change from the model's own baseline) next to the observed peak
over the crisis window (level and percent change from the observed
pre-crisis mean), per scenario and per run.

Percent changes are compared against each side's own baseline, because
the literature-calibrated adapters use stale baseline levels (e.g. Brent
80 USD/bbl vs an observed Nov 2025 - Jan 2026 mean of about 64).

Observed data: ``data/market/monthly_prices.csv`` from
``scripts/revision/fetch_market_data.py`` (World Bank Pink Sheet,
monthly averages, so intra-month spikes are smoothed).

Usage::

    python scripts/revision/observed_vs_scenario.py \
        --run may=data/20260504_222710 \
        --run supp=data/reports/supp_full_20260504_222710 \
        --out-dir docs/revision/observed_vs_scenario
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.market_calibration import (  # noqa: E402
    PRE_CRISIS_WINDOW,
    load_monthly_prices,
    window_median,
)

CRISIS_WINDOW = ("2026-02", "2026-10")
SCENARIO_ORDER = ["swift_contained", "prolonged_contained", "swift_escalated",
                  "prolonged_escalated", "infrastructure_collapse"]
SCENARIO_SHORT = dict(zip(SCENARIO_ORDER, "ABCDE"))

# observed series -> (model_id, level key, pct key, model baseline key or constant, note)
COMPARISONS: list[dict[str, Any]] = [
    {"series": "brent", "label": "Brent (USD/bbl)", "model": "poles_jrc",
     "level_key": "peak_price_usd_per_bbl", "pct_key": "peak_price_change_pct", "note": ""},
    {"series": "henry_hub", "label": "Henry Hub (USD/MMBtu)", "model": "lngst",
     "level_key": "henry_hub_price", "pct_key": None, "baseline": ("hub_baseline_prices", "henry_hub", 3.0),
     "note": "LNGST reports a post-shock level"},
    {"series": "ttf", "label": "TTF / Europe gas (USD/MMBtu)", "model": "lngst",
     "level_key": "ttf_price", "pct_key": None, "baseline": ("hub_baseline_prices", "ttf", 11.0),
     "note": "LNGST reports a post-shock level"},
    {"series": "lng_japan", "label": "JKM (model) vs Japan LNG import price (observed)", "model": "lngst",
     "level_key": "jkm_price", "pct_key": None, "baseline": ("hub_baseline_prices", "jkm", 13.0),
     "note": "observed series is a contract-weighted proxy, slower than JKM spot"},
    {"series": "urea", "label": "Urea (USD/t)", "model": "world_fertilizer",
     "level_key": None, "pct_key": "price_urea_pct", "note": "model reports percent change only"},
    {"series": "dap", "label": "DAP (USD/t)", "model": "world_fertilizer",
     "level_key": None, "pct_key": "price_dap_pct", "note": "model reports percent change only"},
]
CONTEXT_SERIES = ["wheat", "maize", "soybeans", "rice", "potash"]


def _read_run(report_dir: Path) -> dict[tuple[str, str, str], Any]:
    """(scenario, model, key) -> value from Stage 5 quantitative_results.csv."""
    path = report_dir / "csv" / "quantitative_results.csv"
    out: dict[tuple[str, str, str], Any] = {}
    if not path.exists():
        raise FileNotFoundError(f"{path} not found (run Stage 5 export first)")
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            v: Any = r.get("value_numeric")
            if v not in (None, ""):
                v = float(v)
            else:
                raw = r.get("value_raw") or ""
                try:
                    v = json.loads(raw.replace("'", '"'))
                except ValueError:
                    v = raw
            out[(r["scenario_id"], r["model_id"], r["output_key"])] = v
    return out


def _observed(prices: dict[str, list[tuple[str, float]]], series: str) -> dict[str, Any]:
    pts = prices.get(series, [])
    base = window_median(pts, *PRE_CRISIS_WINDOW)
    crisis = [(m, v) for m, v in pts if CRISIS_WINDOW[0] <= m <= CRISIS_WINDOW[1]]
    if not crisis or base is None:
        return {"baseline": base, "peak": None, "peak_month": None, "peak_pct": None, "last": None}
    # "Peak" = the month furthest from the baseline in either direction
    # (Henry Hub fell during the crisis, so its maximum is not its extreme).
    peak_m, peak_v = max(crisis, key=lambda t: abs(t[1] / base - 1))
    last_m, last_v = crisis[-1]
    return {"baseline": round(base, 3), "peak": round(peak_v, 3), "peak_month": peak_m,
            "peak_pct": round((peak_v / base - 1) * 100, 1),
            "last": round(last_v, 3), "last_month": last_m,
            "last_pct": round((last_v / base - 1) * 100, 1)}


def build_rows(runs: dict[str, dict], prices: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for comp in COMPARISONS:
        obs = _observed(prices, comp["series"])
        for run_label, data in runs.items():
            for sid in SCENARIO_ORDER:
                level = data.get((sid, comp["model"], comp["level_key"])) if comp["level_key"] else None
                pct = data.get((sid, comp["model"], comp["pct_key"])) if comp["pct_key"] else None
                if pct is None and isinstance(level, float) and comp.get("baseline"):
                    key, sub, default = comp["baseline"]
                    bl = data.get((sid, comp["model"], key))
                    b = bl.get(sub) if isinstance(bl, dict) else None
                    if b is None:
                        # Stage 5 flattens dict outputs to "key.sub". Before
                        # this lookup the run's own (calibrated) baseline was
                        # missed and the literature constant used instead.
                        b = data.get((sid, comp["model"], f"{key}.{sub}"))
                    b = float(b) if isinstance(b, (int, float)) else default
                    pct = round((level / b - 1) * 100, 1) if b else None
                if level is None and pct is None:
                    continue
                rows.append({
                    "variable": comp["label"], "series": comp["series"], "run": run_label,
                    "scenario": SCENARIO_SHORT[sid], "scenario_id": sid, "model": comp["model"],
                    "model_level": round(level, 3) if isinstance(level, float) else None,
                    "model_pct": round(pct, 1) if isinstance(pct, float) else None,
                    "observed_baseline": obs["baseline"], "observed_peak": obs["peak"],
                    "observed_peak_month": obs["peak_month"], "observed_peak_pct": obs["peak_pct"],
                    "observed_last_pct": obs.get("last_pct"),
                    "pct_gap_pp": (round(pct - obs["peak_pct"], 1)
                                   if isinstance(pct, float) and obs["peak_pct"] is not None else None),
                    "note": comp["note"],
                })
    return rows


def _md(rows: list[dict[str, Any]], prices: dict, runs: list[str]) -> str:
    lines = [
        "# Scenario outputs vs observed crisis-period prices",
        "",
        f"Observed: World Bank Pink Sheet monthly averages. Pre-crisis baseline = median of "
        f"{PRE_CRISIS_WINDOW[0]} to {PRE_CRISIS_WINDOW[1]}; crisis window {CRISIS_WINDOW[0]} to "
        f"{CRISIS_WINDOW[1]}; the observed peak is the month furthest from the baseline in "
        "either direction. Percent changes are each side relative to its own baseline. "
        "Monthly averages smooth intra-month spikes, and the scenarios are conditional paths, "
        "so this is a plausibility check, not a forecast evaluation.",
        "",
        f"Runs: {', '.join(runs)}.",
        "",
    ]
    for comp in COMPARISONS:
        sub = [r for r in rows if r["series"] == comp["series"]]
        if not sub:
            continue
        o = sub[0]
        lines += [f"## {comp['label']}", "",
                  f"Observed: baseline {o['observed_baseline']}, peak {o['observed_peak']} "
                  f"({o['observed_peak_month']}, {o['observed_peak_pct']:+.1f}%), "
                  f"latest {o['observed_last_pct']:+.1f}%."
                  + (f" Note: {comp['note']}." if comp["note"] else ""), "",
                  "| run | scenario | model level | model % | observed peak % | gap (pp) |",
                  "|---|---|---|---|---|---|"]
        for r in sub:
            lines.append(f"| {r['run']} | {r['scenario']} | {r['model_level'] if r['model_level'] is not None else '-'} | "
                         f"{r['model_pct'] if r['model_pct'] is not None else '-'} | {r['observed_peak_pct']} | "
                         f"{r['pct_gap_pp'] if r['pct_gap_pp'] is not None else '-'} |")
        lines.append("")
    lines += ["## Context: observed series without a model counterpart", "",
              "| series | baseline | crisis peak | peak month | peak % | latest % |", "|---|---|---|---|---|---|"]
    for s in CONTEXT_SERIES:
        o = _observed(prices, s)
        if o["peak"] is None:
            continue
        lines.append(f"| {s} | {o['baseline']} | {o['peak']} | {o['peak_month']} | {o['peak_pct']:+.1f} | {o['last_pct']:+.1f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", action="append", required=True,
                    help="LABEL=REPORT_DIR (a directory containing csv/quantitative_results.csv); repeatable")
    ap.add_argument("--prices", default="data/market/monthly_prices.csv")
    ap.add_argument("--out-dir", default="docs/revision/observed_vs_scenario")
    args = ap.parse_args(argv)

    prices = load_monthly_prices(args.prices)
    runs: dict[str, dict] = {}
    for spec in args.run:
        label, _, path = spec.partition("=")
        runs[label] = _read_run(Path(path))
    rows = build_rows(runs, prices)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "observed_vs_scenario.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["variable"])
        w.writeheader()
        w.writerows(rows)
    (out / "observed_vs_scenario.md").write_text(_md(rows, prices, list(runs)), encoding="utf-8")
    print(f"wrote {out / 'observed_vs_scenario.md'} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
