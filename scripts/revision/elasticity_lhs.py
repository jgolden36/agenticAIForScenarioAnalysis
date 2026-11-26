#!/usr/bin/env python3
"""Latin-hypercube sensitivity analysis over calibration elasticities (AgResilience E9 port).

Each draw multiplies every knob in ``configs/robustness/elasticities.yaml``
(macro-kernel elasticities, POLES-JRC demand/supply elasticities, fertilizer
pass-throughs, the forwarding rule's fertilizer demand elasticity, ...) by a
factor in [low, high], then runs the analytical model chain for all five
scenarios on the analyst-baseline inputs, with the Algorithm 1 step 11
forwarding barrier between tiers. Reports:

* p05 / p50 / p95 of each listed headline output, per scenario;
* binned first-order sensitivity indices S1 = Var(E[Y|X_k]) / Var(Y);
* **ordering robustness**: for every scenario pair, the share of draws in
  which the pair keeps the ordering it has at the calibrated point.

Controls: draw ``point`` (all factors 1) must reproduce a run with no
override, which also checks that the overrides are restored between draws.

    python scripts/revision/elasticity_lhs.py --out-dir docs/revision/runs/<id>/robustness [--n 500]
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import robustness_common as rc  # noqa: E402


def headline_values(results: dict[str, dict[str, Any]], outputs: dict[str, list[str]]) -> dict[str, float | None]:
    vals: dict[str, float | None] = {}
    for mid, keys in outputs.items():
        res = results.get(mid) or {}
        for k in keys:
            v = (res.get("outputs") or {}).get(k)
            vals[f"{mid}.{k}"] = float(v) if rc.is_number(v) else None
    return vals


def run_draw(registry: Any, cells: dict[str, dict[str, dict[str, Any]]], scenarios: list[str], spec: dict[str, Any],
             multipliers: dict[str, float], base_mapping: Any) -> dict[str, dict[str, float | None]]:
    knobs = spec["knobs"]
    mapping = rc.mapping_with_overrides(base_mapping, knobs, multipliers)
    out: dict[str, dict[str, float | None]] = {}
    with rc.ConstantOverride(knobs, multipliers):
        for sid in scenarios:
            res = rc.run_chain(registry, cells.get(sid, {}), sid, spec["models"], forwarding=True, mapping=mapping)
            out[sid] = headline_values(res, spec["outputs"])
    return out


def quantiles(values: list[float], qs: tuple[float, ...] = (0.05, 0.5, 0.95)) -> list[float | None]:
    import numpy as np

    if not values:
        return [None] * len(qs)
    return [float(x) for x in np.quantile(np.asarray(values, float), qs)]


def analyse(spec: dict[str, Any], scenarios: list[str], draws: list[dict[str, Any]],
            point: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    knob_names = [k["name"] for k in spec["knobs"]]
    variables = sorted({v for d in draws for s in d["values"].values() for v in s})
    bands, indices, ordering = [], [], []
    for var in variables:
        for sid in scenarios:
            ys = [d["values"][sid].get(var) for d in draws]
            ok = [(d, y) for d, y in zip(draws, ys) if y is not None]
            q05, q50, q95 = quantiles([y for _, y in ok])
            bands.append({"variable": var, "scenario_id": sid, "point": point.get(sid, {}).get(var),
                          "p05": q05, "p50": q50, "p95": q95, "n": len(ok)})
            for name in knob_names:
                s1 = rc.first_order([d["multipliers"][name] for d, _ in ok], [y for _, y in ok])
                indices.append({"variable": var, "scenario_id": sid, "knob": name, "S1": s1})
        for a, b in itertools.combinations(scenarios, 2):
            pa, pb = point.get(a, {}).get(var), point.get(b, {}).get(var)
            if pa is None or pb is None:
                continue
            sign0 = (pa > pb) - (pa < pb)
            pairs = [(d["values"][a].get(var), d["values"][b].get(var)) for d in draws]
            pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
            if not pairs:
                continue
            kept = sum(1 for x, y in pairs if ((x > y) - (x < y)) == sign0)
            ordering.append({"variable": var, "scenario_a": a, "scenario_b": b,
                             "point_order": {1: f"{a} > {b}", -1: f"{a} < {b}", 0: f"{a} = {b} (tie)"}[sign0],
                             "share_kept": kept / len(pairs), "n": len(pairs)})
    return {"bands": bands, "first_order": indices, "ordering": ordering}


def render(result: dict[str, Any]) -> str:
    spec = result["spec"]
    lines = ["# Elasticity Latin hypercube", "",
             f"Generated {result['generated_at']}. {result['n_draws']} seeded draws (seed {spec['seed']}), every knob "
             f"multiplied by a factor in [{spec['low']}, {spec['high']}], each draw re-running the analytical chain "
             f"({', '.join(spec['models'])}) for all scenarios on the analyst-baseline inputs with upstream forwarding. "
             "Port of the AgResilience E9 analysis.", "",
             f"Point control (all factors 1) reproduces the no-override run: **{result['point_control_ok']}**. "
             f"Draws with a missing headline value: {result['draws_with_missing']}. Wall time {result['wall_seconds']:.0f} s.", "",
             "## Knobs", "", "| knob | kind | target | source |", "|---|---|---|---|"]
    for k in spec["knobs"]:
        target = f"{k['module']}.{k['attribute']}" if k.get("kind", "constant") == "constant" else \
            f"{k['model']}.{k['param']} source {k.get('source_index', 0)} `{k['field']}`"
        lines.append(f"| {k['name']} | {k.get('kind', 'constant')} | `{target}` | {k.get('source', '')} |")
    lines += ["", "## Bands (p05 / p50 / p95; point = calibrated)", "",
              "| output | scenario | point | p05 | p50 | p95 |", "|---|---|---|---|---|---|"]
    lines += [f"| {b['variable']} | {b['scenario_id']} | {rc.fmt(b['point'])} | {rc.fmt(b['p05'])} | {rc.fmt(b['p50'])} | {rc.fmt(b['p95'])} |"
              for b in result["bands"]]
    lines += ["", "## Ordering robustness", "",
              "Share of draws in which a scenario pair keeps its calibrated ordering. Below 0.95 is marked.", "",
              "| output | pair (calibrated order) | share kept |", "|---|---|---|"]
    for o in result["ordering"]:
        mark = " **<0.95**" if o["share_kept"] < 0.95 else ""
        lines.append(f"| {o['variable']} | {o['point_order']} | {o['share_kept']:.3f}{mark} |")
    # dominant knob per output (mean S1 over scenarios)
    lines += ["", "## Dominant knobs (mean first-order index over scenarios)", "",
              "| output | top knob | S1 | second | S1 |", "|---|---|---|---|---|"]
    by_var: dict[str, dict[str, list[float]]] = {}
    for r in result["first_order"]:
        if r["S1"] is not None and not math.isnan(r["S1"]):
            by_var.setdefault(r["variable"], {}).setdefault(r["knob"], []).append(r["S1"])
    for var, knobs in sorted(by_var.items()):
        ranked = sorted(((sum(v) / len(v), k) for k, v in knobs.items()), reverse=True)
        top = ranked[:2] + [(None, "-")] * (2 - len(ranked[:2]))
        lines.append(f"| {var} | {top[0][1]} | {rc.fmt(top[0][0], 3)} | {top[1][1]} | {rc.fmt(top[1][0], 3)} |")
    lines += ["", "Variables with no variance across draws (no knob reaches them) have no index."]
    return "\n".join(lines) + "\n"


def plot(result: dict[str, Any], scenarios: list[str], path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    variables = sorted({b["variable"] for b in result["bands"]})
    if not variables:
        return False
    ncol = 3
    nrow = (len(variables) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 2.4 * nrow), squeeze=False)
    labels = [s.replace("_", "\n") for s in scenarios]
    for ax, var in zip(axes.flat, variables):
        rc.style_axes(ax)
        rows = {b["scenario_id"]: b for b in result["bands"] if b["variable"] == var}
        for i, sid in enumerate(scenarios):
            b = rows.get(sid)
            if not b or b["p05"] is None:
                continue
            ax.vlines(i, b["p05"], b["p95"], color=rc.SERIES_COLORS[0], linewidth=3)
            ax.scatter([i], [b["p50"]], color="white", edgecolors=rc.SERIES_COLORS[0], s=22, zorder=3)
            if b["point"] is not None:
                ax.scatter([i], [b["point"]], marker="D", color=rc.SERIES_COLORS[1], s=14, zorder=4)
        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels(labels, fontsize=5.5)
        ax.set_title(var, fontsize=7.5, color=rc.INK, loc="left")
    for ax in list(axes.flat)[len(variables):]:
        ax.axis("off")
    handles = [plt.Line2D([], [], color=rc.SERIES_COLORS[0], linewidth=3, label="p05-p95 across draws"),
               plt.Line2D([], [], marker="o", color="white", markeredgecolor=rc.SERIES_COLORS[0], linestyle="", label="median"),
               plt.Line2D([], [], marker="D", color=rc.SERIES_COLORS[1], linestyle="", label="calibrated elasticities")]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def run(spec: dict[str, Any], out_dir: Path, baseline: Path, n: int | None = None, use_configs: bool = True) -> dict[str, Any]:
    from src.pipeline.upstream_forwarding import load_mapping

    n_draws = int(n if n is not None else spec.get("n_draws", 500))
    registry = rc.build_registry(use_configs)
    cells = rc.baseline_cells(baseline)
    scenarios = rc.scenario_order(baseline)
    base_mapping = load_mapping()
    names = [k["name"] for k in spec["knobs"]]
    t0 = time.monotonic()

    unmodified = run_draw(registry, cells, scenarios, {**spec, "knobs": []}, {}, base_mapping)
    ones = {k: 1.0 for k in names}
    point = run_draw(registry, cells, scenarios, spec, ones, base_mapping)
    point_ok = all(
        (unmodified[s][v] == point[s][v]) or (unmodified[s][v] is not None and point[s][v] is not None
                                               and math.isclose(unmodified[s][v], point[s][v], rel_tol=1e-12, abs_tol=1e-12))
        for s in scenarios for v in unmodified[s])

    draws = []
    for i, mult in enumerate(rc.latin_hypercube(n_draws, names, float(spec["low"]), float(spec["high"]), int(spec["seed"]))):
        draws.append({"draw": i, "multipliers": mult,
                      "values": run_draw(registry, cells, scenarios, spec, mult, base_mapping)})
    after = run_draw(registry, cells, scenarios, {**spec, "knobs": []}, {}, base_mapping)
    restored = after == unmodified

    analysis = analyse(spec, scenarios, draws, point)
    missing = sum(1 for d in draws if any(v is None for s in d["values"].values() for v in s.values()))
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "spec": spec, "n_draws": n_draws,
              "scenarios": scenarios, "point": point, "point_control_ok": bool(point_ok and restored),
              "constants_restored_after_draws": restored, "draws_with_missing": missing,
              "wall_seconds": time.monotonic() - t0, **analysis, "draws": draws}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "elasticity_lhs.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    rc.write_csv(out_dir / "elasticity_lhs_bands.csv", analysis["bands"])
    rc.write_csv(out_dir / "elasticity_lhs_first_order.csv", analysis["first_order"])
    rc.write_csv(out_dir / "elasticity_lhs_ordering.csv", analysis["ordering"])
    (out_dir / "elasticity_lhs.md").write_text(render(result), encoding="utf-8")
    plot(result, scenarios, out_dir / "elasticity_lhs.png")
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--baseline", default=str(rc.DEFAULT_BASELINE))
    p.add_argument("--spec", default=str(rc.ROBUSTNESS_DIR / "elasticities.yaml"))
    p.add_argument("--n", type=int, default=None, help="override n_draws")
    p.add_argument("--no-configs", action="store_true")
    args = p.parse_args(argv)
    result = run(rc.load_yaml(Path(args.spec)), Path(args.out_dir), Path(args.baseline), args.n, not args.no_configs)
    weak = [o for o in result["ordering"] if o["share_kept"] < 0.95]
    print(f"[elasticity_lhs] {result['n_draws']} draws in {result['wall_seconds']:.0f}s; point control "
          f"{result['point_control_ok']}; orderings below 0.95: {len(weak)} of {len(result['ordering'])}")
    return 0 if result["point_control_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
