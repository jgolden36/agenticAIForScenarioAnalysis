#!/usr/bin/env python3
"""Zero-shock residual and dose ladder for every runnable model (AgResilience E0 port).

Two checks per model, each model run in isolation on its own analyst-baseline
inputs (no forwarding), for every scenario:

1. **Zero shock.** All shock-carrying inputs (``configs/robustness/shock_fields.yaml``)
   set to their neutral value. Every change-type headline output
   (``src/synthesis/templated.py::HEADLINE_KEYS``) must be within
   ``zero_tolerance_abs`` of 0. Level outputs (prices in $/unit, ...) have
   no zero reference and are reported as levels.
2. **Dose ladder.** Shocks scaled to ``neutral + f x (value - neutral)`` for
   f in ``factors``. Each headline output must move monotonically in f
   (within a small tolerance) and keep one sign relative to its f = 0 value.

The point for the manuscript: if every model is monotone in its own inputs,
a non-monotone ordering of an output across scenarios (e.g. the oil price
across A-E) comes from the inputs the scenarios carry, not from a model.

    python scripts/revision/zero_shock_ladder.py --out-dir docs/revision/runs/<id>/robustness
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import robustness_common as rc  # noqa: E402

MONOTONE_REL_TOL = 1e-6


def scale_value(value: Any, neutral: Any, factor: float, clip: tuple[float, float] | None = None) -> tuple[Any, bool]:
    """Scaled shock value and whether it was clipped."""
    if isinstance(value, bool) or isinstance(neutral, bool):
        return (value if factor > 0 else bool(neutral)), False
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        clipped = False
        for k, v in value.items():
            n = neutral.get(k, 0.0) if isinstance(neutral, dict) else (neutral if rc.is_number(neutral) else 0.0)
            if n is None or not rc.is_number(v):
                out[k] = v
                continue
            out[k], c = scale_value(v, n, factor)
            clipped = clipped or c
        return out, clipped
    if rc.is_number(value) and rc.is_number(neutral):
        scaled = float(neutral) + factor * (float(value) - float(neutral))
        if clip is not None:
            lo, hi = clip
            bounded = min(max(scaled, lo), hi)
            return bounded, bounded != scaled
        return scaled, False
    if isinstance(value, str):
        return (value if factor > 0 else neutral), False
    return value, False


def dose_params(params: dict[str, Any], spec: dict[str, Any], factor: float) -> tuple[dict[str, Any], bool]:
    out = copy.deepcopy(params)
    clipped = False
    clips = spec.get("clip") or {}
    for name, neutral in (spec.get("fields") or {}).items():
        if name not in out:
            continue
        clip = tuple(clips[name]) if name in clips else None
        out[name], c = scale_value(out[name], neutral, factor, clip)
        clipped = clipped or c
    return out, clipped


def is_monotone(values: list[float]) -> bool:
    scale = max((abs(v) for v in values), default=0.0)
    tol = max(MONOTONE_REL_TOL * scale, 1e-9)
    diffs = [b - a for a, b in zip(values, values[1:])]
    return all(d >= -tol for d in diffs) or all(d <= tol for d in diffs)


def sign_consistent(values: list[float], zero_value: float) -> bool:
    signs = {1 if v - zero_value > 1e-9 else -1 if v - zero_value < -1e-9 else 0 for v in values}
    signs.discard(0)
    return len(signs) <= 1


def run_ladder(
    shock_spec: dict[str, Any],
    cells: dict[str, dict[str, dict[str, Any]]],
    registry: Any,
    headlines: dict[str, list[str]],
    scenarios: list[str],
    models: list[str] | None = None,
) -> dict[str, Any]:
    factors = [float(f) for f in shock_spec.get("factors", [0.0, 0.5, 1.0, 1.6])]
    if 0.0 not in factors:
        factors = [0.0] + factors
    tol = float(shock_spec.get("zero_tolerance_abs", 1e-4))
    zero_rows: list[dict[str, Any]] = []
    ladder_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    model_ids = [m for m in shock_spec["models"] if models is None or m in models]
    for mid in model_ids:
        spec = shock_spec["models"][mid]
        adapter = registry.get(mid)
        if adapter is None:
            continue
        keys = list(spec.get("outputs") or headlines.get(mid, []))
        for sid in scenarios:
            params = cells.get(sid, {}).get(mid)
            if params is None:
                continue
            series: dict[str, list[tuple[float, float]]] = {k: [] for k in keys}
            statuses: list[str] = []
            any_clipped = False
            model_factors = sorted({0.0, *(float(x) for x in spec.get("factors", factors))})
            for f in model_factors:
                dosed, clipped = dose_params(params, spec, f)
                any_clipped = any_clipped or clipped
                res = rc.run_adapter(adapter, dosed)
                statuses.append(res["status"])
                for k in keys:
                    v = res["outputs"].get(k)
                    ladder_rows.append({"model_id": mid, "scenario_id": sid, "factor": f, "output": k,
                                        "value": v if rc.is_number(v) else None, "status": res["status"],
                                        "clipped": clipped, "error": res["error"]})
                    if rc.is_number(v):
                        series[k].append((f, float(v)))
                if f == 0.0:
                    for k in keys:
                        v = res["outputs"].get(k)
                        change = rc.is_change_output(k)
                        passed = (abs(float(v)) <= tol) if (change and rc.is_number(v)) else None
                        zero_rows.append({"model_id": mid, "scenario_id": sid, "output": k, "kind": "change" if change else "level",
                                          "value_at_zero_shock": v if rc.is_number(v) else None,
                                          "status": res["status"], "passed": passed, "error": res["error"]})
            for k, pts in series.items():
                vals = [v for _, v in sorted(pts)]
                zero_v = dict(pts).get(0.0)
                summary_rows.append({
                    "model_id": mid, "scenario_id": sid, "output": k, "n_points": len(vals),
                    "monotone": is_monotone(vals) if len(vals) >= 3 else None,
                    "sign_consistent": sign_consistent(vals[1:], zero_v) if zero_v is not None and len(vals) >= 3 else None,
                    "value_at_1": dict(pts).get(1.0), "value_at_0": zero_v,
                    "any_clipped": any_clipped, "statuses": sorted(set(statuses)),
                })
    return {"factors": factors, "zero_tolerance_abs": tol, "zero_shock": zero_rows,
            "ladder": ladder_rows, "summary": summary_rows}


def model_verdicts(result: dict[str, Any]) -> list[dict[str, Any]]:
    by: dict[str, dict[str, Any]] = {}
    for r in result["zero_shock"]:
        v = by.setdefault(r["model_id"], {"model_id": r["model_id"], "zero_checked": 0, "zero_failed": 0,
                                           "ladders": 0, "non_monotone": 0, "sign_flips": 0, "statuses": set()})
        v["statuses"].add(r["status"])
        if r["passed"] is not None:
            v["zero_checked"] += 1
            v["zero_failed"] += 0 if r["passed"] else 1
    for r in result["summary"]:
        v = by.setdefault(r["model_id"], {"model_id": r["model_id"], "zero_checked": 0, "zero_failed": 0,
                                           "ladders": 0, "non_monotone": 0, "sign_flips": 0, "statuses": set()})
        if r["monotone"] is not None:
            v["ladders"] += 1
            v["non_monotone"] += 0 if r["monotone"] else 1
        if r["sign_consistent"] is False:
            v["sign_flips"] += 1
    out = []
    for v in by.values():
        v["statuses"] = ",".join(sorted(v["statuses"]))
        out.append(v)
    return sorted(out, key=lambda r: r["model_id"])


def render(result: dict[str, Any], verdicts: list[dict[str, Any]]) -> str:
    lines = ["# Zero-shock residual and dose ladder", "",
             f"Generated {result['generated_at']}. Each model runs alone on its analyst-baseline inputs "
             "(`configs/baselines/hormuz_2026_analyst.yaml`), with the shock fields in "
             "`configs/robustness/shock_fields.yaml` set to neutral (zero shock) or scaled by "
             f"{', '.join(rc.fmt(f) for f in result['factors'])}. Ported from the AgResilience E0 check.", "",
             f"Zero-shock pass: |change-type headline output| <= {result['zero_tolerance_abs']}. "
             "Monotone: the output never reverses direction along the ladder.", "",
             "## By model", "",
             "| model | run status | zero-shock checks | zero-shock failures | ladders | non-monotone | sign flips |",
             "|---|---|---|---|---|---|---|"]
    for v in verdicts:
        lines.append(f"| {v['model_id']} | {v['statuses']} | {v['zero_checked']} | {v['zero_failed']} | "
                     f"{v['ladders']} | {v['non_monotone']} | {v['sign_flips']} |")
    fails = [r for r in result["zero_shock"] if r["passed"] is False]
    if fails:
        lines += ["", "## Zero-shock failures", "", "| model | scenario | output | value at zero shock |", "|---|---|---|---|"]
        lines += [f"| {r['model_id']} | {r['scenario_id']} | {r['output']} | {rc.fmt(r['value_at_zero_shock'])} |" for r in fails]
    nonmono = [r for r in result["summary"] if r["monotone"] is False or r["sign_consistent"] is False]
    if nonmono:
        lines += ["", "## Non-monotone or sign-changing ladders", "",
                  "| model | scenario | output | monotone | one sign | clipped dose |", "|---|---|---|---|---|---|"]
        lines += [f"| {r['model_id']} | {r['scenario_id']} | {r['output']} | {r['monotone']} | {r['sign_consistent']} | {r['any_clipped']} |"
                  for r in nonmono]
    skipped = sorted({r["model_id"] for r in result["zero_shock"] if r["status"] in ("skipped", "failed", "invalid")})
    if skipped:
        lines += ["", "## Not evaluated", "",
                  "Models whose zero-shock run did not complete (skipped without config, failed, or rejected the "
                  "neutral inputs): " + ", ".join(f"`{m}`" for m in skipped) + ". See `zero_shock_ladder.json` for messages."]
    return "\n".join(lines) + "\n"


def plot(result: dict[str, Any], path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    # One panel per model: each headline output indexed to its value at f = 1
    # (common base, so one axis), mean over scenarios; first three outputs only.
    by_model: dict[str, dict[str, dict[float, list[float]]]] = {}
    for r in result["ladder"]:
        if r["value"] is None:
            continue
        by_model.setdefault(r["model_id"], {}).setdefault(r["output"], {}).setdefault(r["factor"], []).append(
            (r["scenario_id"], r["value"]))
    models = sorted(by_model)
    if not models:
        return False
    ncol = 4
    nrow = (len(models) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 2.2 * nrow), squeeze=False)
    for ax, mid in zip(axes.flat, models):
        rc.style_axes(ax)
        outputs = list(by_model[mid])[:3]
        for color, out in zip(rc.SERIES_COLORS, outputs):
            pts = by_model[mid][out]
            # index each scenario to its own f=1 value, then average
            base = {sid: v for sid, v in pts.get(1.0, [])}
            xs, ys = [], []
            for f in sorted(pts):
                idx = [v / base[sid] for sid, v in pts[f] if base.get(sid)]
                if idx:
                    xs.append(f)
                    ys.append(sum(idx) / len(idx))
            ax.plot(xs, ys, color=color, linewidth=1.5, marker="o", markersize=3, label=out)
        ax.set_title(mid, fontsize=8, color=rc.INK, loc="left")
        ax.legend(fontsize=5.5, frameon=False, loc="best")
    for ax in list(axes.flat)[len(models):]:
        ax.axis("off")
    fig.supxlabel("dose factor f (1 = scenario shock)", fontsize=8, color=rc.INK_MUTED)
    fig.supylabel("output / output at f = 1 (mean over scenarios)", fontsize=8, color=rc.INK_MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--baseline", default=str(rc.DEFAULT_BASELINE))
    p.add_argument("--shock-fields", default=str(rc.ROBUSTNESS_DIR / "shock_fields.yaml"))
    p.add_argument("--models", nargs="*", default=None)
    p.add_argument("--no-configs", action="store_true", help="build adapters without configs/model_configs")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = rc.load_yaml(Path(args.shock_fields))
    result = run_ladder(spec, rc.baseline_cells(Path(args.baseline)), rc.build_registry(not args.no_configs),
                        rc.headline_keys(), rc.scenario_order(Path(args.baseline)), args.models)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    verdicts = model_verdicts(result)
    result["verdicts"] = verdicts
    (out_dir / "zero_shock_ladder.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    rc.write_csv(out_dir / "zero_shock_ladder.csv", result["summary"])
    rc.write_csv(out_dir / "zero_shock_residuals.csv", result["zero_shock"])
    (out_dir / "zero_shock_ladder.md").write_text(render(result, verdicts), encoding="utf-8")
    plot(result, out_dir / "zero_shock_ladder.png")
    n_fail = sum(v["zero_failed"] for v in verdicts)
    n_nonmono = sum(v["non_monotone"] for v in verdicts)
    print(f"[zero_shock_ladder] {len(verdicts)} models; zero-shock failures {n_fail}; non-monotone ladders {n_nonmono}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
