#!/usr/bin/env python3
"""Armington-elasticity Latin hypercube for APSIM-GTAP (AgResilience E9 design, Hormuz shock).

Each draw scales the calibrated ESUBM (import-source substitution) and ESUBD
(domestic vs imported) elasticities for chemicals and grains in every region
by a factor in [low, high]; the GTAP server re-calibrates to the same
benchmark under the drawn elasticities and reports changes against that
draw's own baseline (AgResilience ``set_parameters!``). All five scenarios
are solved under each draw (GTAP-crop fixed point included).

Run as a SLURM array: ``--chunk $SLURM_ARRAY_TASK_ID --n-chunks $SLURM_ARRAY_TASK_COUNT``
writes ``<work-dir>/chunk_<i>.json``; then ``--aggregate`` writes bands,
first-order indices and cross-scenario ordering robustness to ``--out-dir``
(same tables as ``elasticity_lhs.py``).

    python scripts/revision/apsim_gtap_ssa.py --work-dir data/robustness/apsim_gtap_ssa --chunk 0 --n-chunks 10
    python scripts/revision/apsim_gtap_ssa.py --work-dir data/robustness/apsim_gtap_ssa --aggregate \
        --out-dir docs/revision/robustness/apsim_gtap_ssa

Scenario inputs: ``--inputs <apsim_gtap_fill_inputs.json>`` (a fill's
resolved inputs) or, by default, the analyst baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import robustness_common as rc  # noqa: E402

FACTORS = {  # name -> (GTAP parameter, commodity); as AgResilience experiments/designs/gen_ssa.py
    "esubm_chm": ("esubm", "chm"),
    "esubd_chm": ("esubd", "chm"),
    "esubm_gro": ("esubm", "gro"),
    "esubd_gro": ("esubd", "gro"),
}
OUTPUTS = ["us_gdp_pct", "gulf_gdp_pct", "us_maize_yield_change_pct", "us_gro_price_pct", "us_chm_consumption_pct"]


def parameter_edits(multipliers: dict[str, float]) -> list[dict[str, Any]]:
    return [{"name": FACTORS[k][0], "indices": [FACTORS[k][1], "*"], "operation": "multiply",
             "value": round(float(v), 6)} for k, v in multipliers.items()]


def design(n: int, seed: int, low: float, high: float) -> list[dict[str, Any]]:
    draws = [{"draw": "point", "multipliers": {k: 1.0 for k in FACTORS}}]
    for i, m in enumerate(rc.latin_hypercube(n, list(FACTORS), low, high, seed)):
        draws.append({"draw": i, "multipliers": m})
    return draws


def scenario_inputs(inputs_path: Path | None, baseline: Path) -> dict[str, dict[str, Any]]:
    if inputs_path is not None:
        data = json.loads(inputs_path.read_text(encoding="utf-8"))
        return {c["scenario_id"]: dict(c["inputs"]) for c in data["cells"]}
    cells = rc.baseline_cells(baseline)
    return {sid: dict(models["apsim_gtap"]) for sid, models in cells.items() if "apsim_gtap" in models}


def run_chunk(adapter: Any, draws: list[dict[str, Any]], inputs: dict[str, dict[str, Any]], chunk: int,
              n_chunks: int, work_dir: Path) -> Path:
    cfg = adapter.agres_config
    if cfg is None:
        raise SystemExit("apsim_gtap is not configured (configs/model_configs/apsim_gtap.yaml / HORMUZ_APSIM_GTAP_ROOT)")
    mine = [d for i, d in enumerate(draws) if i % n_chunks == chunk]
    cases, config = [], None
    for d in mine:  # grouped by draw: one re-calibration per draw
        edits = parameter_edits(d["multipliers"]) if d["draw"] != "point" else None
        for sid, params in sorted(inputs.items()):
            payload = adapter.translate_inputs({**params, "scenario_id": sid})
            config = payload.pop("config")
            payload["case_id"] = f"{d['draw']}|{sid}"
            if edits:
                payload["gtap_parameter_edits"] = edits
            cases.append(payload)
    work_dir.mkdir(parents=True, exist_ok=True)
    inp = work_dir / f"chunk_{chunk}_inputs.json"
    out = work_dir / f"chunk_{chunk}.json"
    inp.write_text(json.dumps({"config": config, "cases": cases}, indent=2), encoding="utf-8")
    from src.models.fertilizer.apsim_gtap import DRIVER_PATH

    env = {**os.environ, **cfg.extra_env, "OMP_NUM_THREADS": "4", "JULIA_NUM_THREADS": "4"}
    proc = subprocess.run([cfg.python_executable, str(DRIVER_PATH), "--in", str(inp), "--out", str(out)],
                          cwd=str(cfg.agres_root), env=env, capture_output=True, text=True)
    (work_dir / f"chunk_{chunk}.log").write_text((proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
                                                 encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"driver failed (rc={proc.returncode}); see {work_dir}/chunk_{chunk}.log")
    meta = {"chunk": chunk, "n_chunks": n_chunks, "draws": [d["draw"] for d in mine],
            "multipliers": {str(d["draw"]): d["multipliers"] for d in mine}}
    (work_dir / f"chunk_{chunk}_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out


def aggregate(work_dir: Path, out_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    import elasticity_lhs

    multipliers: dict[str, dict[str, float]] = {}
    values: dict[str, dict[str, dict[str, float | None]]] = {}
    failures: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for meta_path in sorted(work_dir.glob("chunk_*_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        multipliers.update(meta["multipliers"])
        res_path = work_dir / f"chunk_{meta['chunk']}.json"
        if not res_path.exists():
            failures.append({"case_id": f"chunk {meta['chunk']}", "error": "no result file"})
            continue
        for r in json.loads(res_path.read_text(encoding="utf-8"))["results"]:
            draw, sid = r["case_id"].split("|", 1)
            if r["status"] != "completed":
                failures.append({"case_id": r["case_id"], "error": r.get("error")})
                continue
            out = r["outputs"]
            values.setdefault(draw, {})[sid] = {k: out.get(k) if rc.is_number(out.get(k)) else None for k in OUTPUTS}
            gates.append({"case_id": r["case_id"], "converged": out.get("converged"),
                          "zero_shock_residual_gdp_pct": out.get("zero_shock_residual_gdp_pct"),
                          "zero_shock_gate_passed": out.get("zero_shock_gate_passed")})
    scenarios = sorted({s for v in values.values() for s in v})
    point = values.get("point", {})
    draws = [{"draw": d, "multipliers": multipliers[d], "values": {s: v.get(s, {k: None for k in OUTPUTS}) for s in scenarios}}
             for d, v in values.items() if d != "point" and all(s in v for s in scenarios)]
    analysis = elasticity_lhs.analyse({"knobs": [{"name": k} for k in FACTORS]}, scenarios, draws, point)
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "spec": spec, "n_complete_draws": len(draws),
              "failures": failures, "gates": gates,
              "gate_failures": [g for g in gates if g["zero_shock_gate_passed"] is False or g["converged"] is False],
              "scenarios": scenarios, "point": point, **analysis}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "apsim_gtap_ssa.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    rc.write_csv(out_dir / "apsim_gtap_ssa_bands.csv", analysis["bands"])
    rc.write_csv(out_dir / "apsim_gtap_ssa_first_order.csv", analysis["first_order"])
    rc.write_csv(out_dir / "apsim_gtap_ssa_ordering.csv", analysis["ordering"])
    (out_dir / "apsim_gtap_ssa.md").write_text(render(result), encoding="utf-8")
    elasticity_lhs.plot(result, scenarios, out_dir / "apsim_gtap_ssa.png")
    return result


def render(result: dict[str, Any]) -> str:
    spec = result["spec"]
    lines = ["# APSIM-GTAP: Armington-elasticity Latin hypercube", "",
             f"Generated {result['generated_at']}. ESUBM/ESUBD for chemicals and grains in every region scaled by "
             f"factors in [{spec['low']}, {spec['high']}] (seed {spec['seed']}, {spec['n']} draws), GTAP re-calibrated "
             "per draw, all scenarios solved with the GTAP-crop fixed point. Design of AgResilience E9.", "",
             f"Complete draws: {result['n_complete_draws']}. Failed cases: {len(result['failures'])}. "
             f"Cases failing the zero-shock or convergence gate: {len(result['gate_failures'])}.", "",
             "## Bands (p05 / p50 / p95; point = calibrated elasticities)", "",
             "| output | scenario | point | p05 | p50 | p95 |", "|---|---|---|---|---|---|"]
    lines += [f"| {b['variable']} | {b['scenario_id']} | {rc.fmt(b['point'])} | {rc.fmt(b['p05'])} | {rc.fmt(b['p50'])} | {rc.fmt(b['p95'])} |"
              for b in result["bands"]]
    lines += ["", "## Ordering robustness", "", "| output | pair (calibrated order) | share kept |", "|---|---|---|"]
    lines += [f"| {o['variable']} | {o['point_order']} | {o['share_kept']:.3f}{' **<0.95**' if o['share_kept'] < 0.95 else ''} |"
              for o in result["ordering"]]
    if result["failures"]:
        lines += ["", "## Failed cases", ""] + [f"- {f['case_id']}: {f['error']}" for f in result["failures"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work-dir", required=True)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--inputs", default=None, help="apsim_gtap_fill_inputs.json; default: analyst baseline")
    p.add_argument("--baseline", default=str(rc.DEFAULT_BASELINE))
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--seed", type=int, default=20261010)
    p.add_argument("--low", type=float, default=0.5)
    p.add_argument("--high", type=float, default=1.5)
    p.add_argument("--chunk", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", "0")))
    p.add_argument("--n-chunks", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_COUNT", "1")))
    p.add_argument("--aggregate", action="store_true")
    args = p.parse_args(argv)

    spec = {"n": args.n, "seed": args.seed, "low": args.low, "high": args.high,
            "inputs": args.inputs or str(args.baseline)}
    work = Path(args.work_dir)
    if args.aggregate:
        result = aggregate(work, Path(args.out_dir or work / "report"), spec)
        print(f"[apsim_gtap_ssa] {result['n_complete_draws']} complete draws; {len(result['failures'])} failed cases; "
              f"{len(result['gate_failures'])} gate failures")
        return 0
    adapter = rc.build_registry(True).get("apsim_gtap")
    inputs = scenario_inputs(Path(args.inputs) if args.inputs else None, Path(args.baseline))
    out = run_chunk(adapter, design(args.n, args.seed, args.low, args.high), inputs, args.chunk, args.n_chunks, work)
    print(f"[apsim_gtap_ssa] chunk {args.chunk}/{args.n_chunks} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
