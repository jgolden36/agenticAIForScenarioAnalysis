#!/usr/bin/env python3
"""How much do the pipeline's one-pass couplings miss? (AgResilience E3 port)

Two comparisons:

(a) **APSIM-GTAP open loop vs fixed point.** Every ``apsim_gtap`` record
    carries arm A (one pass: shock -> GTAP -> nitrogen -> yield, no yield
    feedback) and arm C (yield fed back to GTAP until it stops changing).
    Their difference bounds the error of running the crop-economy coupling
    one way only, which is what the pipeline's forwarding barrier does for
    every other model pair.

(b) **Forwarding barrier on vs off.** The analytical chain is run on the
    analyst-baseline inputs twice, with the Algorithm 1 step 11 barrier and
    without it (each downstream model keeps its own extracted/analyst
    inputs). The difference is how much the barrier changes downstream and
    macro outputs.

    python scripts/revision/open_loop_gap.py --out-dir docs/revision/runs/<id>/robustness \
        --state-dir data/pipeline_state_may_apsimgtap --run-id 20260504_222710
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import robustness_common as rc  # noqa: E402

GAP_KEYS = ("yield_change_pct", "us_gro_price_pct", "us_gro_production_pct", "us_gdp_pct")


def apsim_gtap_gaps(state_dirs: list[Path], run_ids: list[str] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sd in state_dirs:
        for path in sorted(sd.glob("*_model_*apsim_gtap*.json")):
            rec = json.loads(path.read_text(encoding="utf-8"))
            if rec.get("model_id") != "apsim_gtap":
                continue
            run_id = path.name.split("_model_")[0]
            if run_ids and run_id not in run_ids:
                continue
            out = rec.get("outputs") or {}
            base = {"state_dir": str(sd), "run_id": run_id, "scenario_id": rec.get("scenario_id"),
                    "status": rec.get("status"), "iterations": out.get("fixed_point_iterations"),
                    "converged": out.get("converged")}
            if rec.get("status") != "completed":
                rows.append({**base, "variable": None})
                continue
            a, c = out.get("arm_a") or {}, out.get("arm_c") or {}
            for k in GAP_KEYS:
                av, cv = a.get(k), c.get(k)
                gap = (cv - av) if rc.is_number(av) and rc.is_number(cv) else None
                rel = (gap / av * 100.0) if gap is not None and av else None
                rows.append({**base, "variable": k, "one_pass": av, "fixed_point": cv, "gap": gap, "gap_pct_of_one_pass": rel})
    return rows


def forwarding_ablation(spec_models: list[str], outputs: dict[str, list[str]], baseline: Path,
                        use_configs: bool) -> list[dict[str, Any]]:
    registry = rc.build_registry(use_configs)
    cells = rc.baseline_cells(baseline)
    rows: list[dict[str, Any]] = []
    for sid in rc.scenario_order(baseline):
        on = rc.run_chain(registry, cells.get(sid, {}), sid, spec_models, forwarding=True)
        off = rc.run_chain(registry, cells.get(sid, {}), sid, spec_models, forwarding=False)
        for mid, keys in outputs.items():
            n_over = len((on.get(mid) or {}).get("overrides") or [])
            for k in keys:
                v_on = ((on.get(mid) or {}).get("outputs") or {}).get(k)
                v_off = ((off.get(mid) or {}).get("outputs") or {}).get(k)
                diff = (v_on - v_off) if rc.is_number(v_on) and rc.is_number(v_off) else None
                rel = (diff / v_off * 100.0) if diff is not None and v_off else None
                rows.append({"scenario_id": sid, "model_id": mid, "variable": k, "forwarded_inputs": n_over,
                             "with_forwarding": v_on, "without_forwarding": v_off, "difference": diff,
                             "difference_pct": rel})
    return rows


def render(result: dict[str, Any]) -> str:
    lines = ["# Open loop vs fixed point, and the forwarding barrier", "",
             f"Generated {result['generated_at']}. Port of the AgResilience E3 comparison.", "",
             "## (a) APSIM-GTAP: one pass vs GTAP-crop fixed point", ""]
    gaps = result["apsim_gtap"]
    if not gaps:
        lines += ["No `apsim_gtap` records found in the given state directories (the model needs "
                  "`configs/model_configs/apsim_gtap.yaml`; run `scripts/revision/run_apsim_gtap_fill.py` first)."]
    else:
        lines += ["| run | scenario | variable | one pass | fixed point | gap | gap % | iterations |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in gaps:
            if r["variable"] is None:
                lines.append(f"| {r['run_id']} | {r['scenario_id']} | ({r['status']}) | | | | | |")
                continue
            lines.append(f"| {r['run_id']} | {r['scenario_id']} | {r['variable']} | {rc.fmt(r['one_pass'])} | "
                         f"{rc.fmt(r['fixed_point'])} | {rc.fmt(r['gap'])} | {rc.fmt(r['gap_pct_of_one_pass'], 3)} | {r['iterations']} |")
    lines += ["", "## (b) Forwarding barrier on vs off (analyst-baseline inputs)", "",
              "`forwarded inputs` counts the inputs the barrier replaced for that model and scenario.", "",
              "| scenario | model | output | forwarded inputs | with barrier | without | difference | difference % |",
              "|---|---|---|---|---|---|---|---|"]
    for r in result["forwarding_ablation"]:
        lines.append(f"| {r['scenario_id']} | {r['model_id']} | {r['variable']} | {r['forwarded_inputs']} | "
                     f"{rc.fmt(r['with_forwarding'])} | {rc.fmt(r['without_forwarding'])} | {rc.fmt(r['difference'])} | "
                     f"{rc.fmt(r['difference_pct'], 3)} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--state-dir", action="append", default=[], help="state dir(s) with apsim_gtap records")
    p.add_argument("--run-id", action="append", default=None, help="restrict (a) to these run ids")
    p.add_argument("--baseline", default=str(rc.DEFAULT_BASELINE))
    p.add_argument("--spec", default=str(rc.ROBUSTNESS_DIR / "elasticities.yaml"),
                   help="model chain and outputs for (b) (the elasticity LHS spec)")
    p.add_argument("--no-configs", action="store_true")
    args = p.parse_args(argv)

    spec = rc.load_yaml(Path(args.spec))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "apsim_gtap": apsim_gtap_gaps([Path(s) for s in args.state_dir], args.run_id),
        "forwarding_ablation": forwarding_ablation(spec["models"], spec["outputs"], Path(args.baseline), not args.no_configs),
    }
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "open_loop_gap.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    rc.write_csv(out / "open_loop_gap_apsim_gtap.csv", result["apsim_gtap"])
    rc.write_csv(out / "open_loop_gap_forwarding.csv", result["forwarding_ablation"])
    (out / "open_loop_gap.md").write_text(render(result), encoding="utf-8")
    changed = [r for r in result["forwarding_ablation"] if r["difference"]]
    print(f"[open_loop_gap] apsim_gtap rows {len(result['apsim_gtap'])}; forwarding changes "
          f"{len(changed)} of {len(result['forwarding_ablation'])} downstream outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
