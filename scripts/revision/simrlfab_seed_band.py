"""Seed band for SimRLFab cells: is a scenario difference larger than simulation noise?

SimRLFab hardcodes SEED=10, so a pipeline run gives one draw per scenario.
Because the discrete-event simulation is path-sensitive, a tiny change in
machine MTBF can move the KPIs by more than the shock itself would. This
script re-runs each SimRLFab cell of a finished run with the inputs that cell
actually used (episodes, MTBF/MTOL/MTOG overrides from the state record)
over a list of seeds, together with a paired control that is identical
except that the gas-shortfall overrides are removed (upstream MTBF 1000 /
MTOL 200 on every machine). The paired difference shocked - control, with
its standard error over seeds, is the estimate of the helium/neon effect.

It reads state records only and writes to ``--out-dir``; it changes no run.

Usage (on a compute node; TensorFlow needs AVX)::

    python scripts/revision/simrlfab_seed_band.py --run-id supp_full_20260504_222710 \
        --seeds 10-19 --out-dir docs/revision/runs/supp_full_20260504_222710
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KPIS = ("machines_working", "machines_broken", "finished_orders", "order_waiting_time")
# SimRLFab defaults (initialize_env.extend_production_parameters).
BASELINE_MTBF, BASELINE_MTOL = 1000.0, 200.0


def parse_seeds(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def load_cells(state_dir: Path, run_id: str) -> list[dict]:
    """SimRLFab cells of ``run_id`` with the driver inputs they used."""
    cells = []
    for f in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("model_id") != "simrlfab" or rec.get("status") != "completed":
            continue
        out = rec.get("outputs") or {}
        ao = out.get("applied_overrides") or {}
        md = rec.get("metadata") or {}
        cells.append({
            "scenario_id": rec.get("scenario_id"),
            "episodes": int(md.get("episodes_requested", 50)),
            "timesteps": int(md.get("timesteps_per_episode", 100)),
            "agent_type": md.get("agent_type", "FIFO"),
            "mtbf": {str(k): float(v) for k, v in (ao.get("machine_mtbf_overrides") or {}).items()},
            "mtol": {str(k): float(v) for k, v in (ao.get("machine_mtol_overrides") or {}).items()},
            "mtog": ao.get("mtog_per_source"),
            "recorded": {k: out.get(k) for k in KPIS},
            "helium_supply_reduction_pct": next(
                (o.get("computed_value") for o in out.get("_upstream_overrides") or []
                 if o.get("name") == "helium_supply_reduction_pct"), None),
        })
    return cells


#: Arms re-run per cell. ``full`` is the recorded input; ``control`` drops every
#: gas-shortfall override; ``helium_only`` / ``neon_only`` keep the overrides
#: on the helium- or neon-affected machines only (SimRLFabConfig lists).
ARMS = ("full", "control", "helium_only", "neon_only")


def driver_config(cell: dict, seed: int, arm: str | bool = "full",
                  helium_machines=(0, 1, 2), neon_machines=(3, 4)) -> dict:
    if arm is True:
        arm = "control"
    elif arm is False:
        arm = "full"
    keep = {
        "full": None,
        "control": set(),
        "helium_only": {str(i) for i in helium_machines},
        "neon_only": {str(i) for i in neon_machines},
    }[arm]

    def pick(d: dict, default: float) -> dict:
        # Entries equal to SimRLFab's own default are dropped so equivalent
        # configurations share one key (and one set of runs).
        return {k: v for k, v in d.items()
                if (keep is None or k in keep) and abs(float(v) - default) > 1e-9}

    return {
        "scenario_id": cell["scenario_id"],
        "episodes": cell["episodes"],
        "timesteps_per_episode": cell["timesteps"],
        "agent_type": cell["agent_type"],
        "agent_config_path": None,
        "seed": seed,
        "simrlfab_overrides": {
            "machine_mtbf_overrides": pick(cell["mtbf"], BASELINE_MTBF),
            "machine_mtol_overrides": pick(cell["mtol"], BASELINE_MTOL),
            "mtog_per_source": cell["mtog"],
        },
    }


def config_key(cfg: dict) -> str:
    c = {k: v for k, v in cfg.items() if k != "scenario_id"}
    return json.dumps(c, sort_keys=True)


def run_driver(cfg: dict, python: str, repo: Path, driver: Path, timeout: int) -> dict:
    from src.models.helium.simrlfab import SimRLFabAdapter

    with tempfile.TemporaryDirectory(prefix="simrlfab_band_") as td:
        inp, outp = Path(td) / "inputs.json", Path(td) / "outputs.json"
        inp.write_text(json.dumps(cfg), encoding="utf-8")
        proc = subprocess.run(
            [python, str(driver), "--input", str(inp), "--output", str(outp), "--simrlfab-path", str(repo)],
            capture_output=True, text=True, timeout=timeout,
        )
        if not outp.exists():
            return {"_error": f"exit {proc.returncode}: {proc.stderr[-400:]}"}
        raw = json.loads(outp.read_text(encoding="utf-8"))
    if raw.get("status") != "ok":
        return {"_error": raw.get("error") or "driver status not ok"}
    parsed = SimRLFabAdapter().parse_outputs(raw).outputs
    return {k: parsed.get(k) for k in KPIS}


def _mean_sd(vals: list[float]) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    return statistics.fmean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


def _overrides_desc(cfg: dict) -> str:
    o = cfg["simrlfab_overrides"]
    if not o["machine_mtbf_overrides"] and not o["machine_mtol_overrides"]:
        return "none"
    parts = []
    for k in sorted(set(o["machine_mtbf_overrides"]) | set(o["machine_mtol_overrides"]), key=int):
        parts.append(f"m{k}:{o['machine_mtbf_overrides'].get(k, BASELINE_MTBF):g}/{o['machine_mtol_overrides'].get(k, BASELINE_MTOL):g}")
    return " ".join(parts)


def summarise(cells: list[dict], draws: dict[str, dict[int, dict]], seeds: list[int],
              helium_machines=(0, 1, 2), neon_machines=(3, 4)) -> list[dict]:
    """One row per (cell, arm, KPI): the arm's paired difference against control.

    Arms whose configuration equals another arm's are still reported (the
    draws are shared), so every scenario has the same rows.
    """
    rows = []
    for cell in cells:
        c_cfg = driver_config(cell, 0, "control", helium_machines, neon_machines)
        c_key = config_key(c_cfg)
        for arm in ("full", "helium_only", "neon_only"):
            a_cfg = driver_config(cell, 0, arm, helium_machines, neon_machines)
            s_key = config_key(a_cfg)
            for kpi in KPIS:
                shocked = [draws[s_key][sd].get(kpi) for sd in seeds if sd in draws.get(s_key, {})]
                control = [draws[c_key][sd].get(kpi) for sd in seeds if sd in draws.get(c_key, {})]
                pairs = [(draws[s_key][sd].get(kpi), draws[c_key][sd].get(kpi)) for sd in seeds
                         if sd in draws.get(s_key, {}) and sd in draws.get(c_key, {})]
                diffs = [a - b for a, b in pairs if a is not None and b is not None]
                sm, ssd = _mean_sd([v for v in shocked if v is not None])
                cm, csd = _mean_sd([v for v in control if v is not None])
                dm, dsd = _mean_sd(diffs)
                se = dsd / math.sqrt(len(diffs)) if diffs and dsd is not None else None
                rows.append({
                    "scenario_id": cell["scenario_id"], "arm": arm, "kpi": kpi,
                    "overrides": _overrides_desc(a_cfg),
                    "helium_supply_reduction_pct": cell["helium_supply_reduction_pct"],
                    "episodes": cell["episodes"], "n_seeds": len(diffs),
                    "recorded_seed10": cell["recorded"].get(kpi) if arm == "full" else None,
                    "shocked_mean": sm, "shocked_sd": ssd, "control_mean": cm, "control_sd": csd,
                    "paired_diff_mean": dm, "paired_diff_sd": dsd, "paired_diff_se": se,
                    "diff_exceeds_2se": (abs(dm) > 2 * se) if (dm is not None and se)
                    else (dm not in (None, 0.0) and se == 0.0),
                })
    return rows


def _fmt(v, nd=3):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def write_outputs(rows: list[dict], draws_long: list[dict], out_dir: Path, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "simrlfab_seed_band.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out_dir / "simrlfab_seed_band_draws.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(draws_long[0].keys()))
        w.writeheader()
        w.writerows(draws_long)
    (out_dir / "simrlfab_seed_band.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2), encoding="utf-8")
    lines = [
        f"# SimRLFab seed band: {meta['run_id']}",
        "",
        f"Seeds {meta['seeds'][0]}-{meta['seeds'][-1]} ({len(meta['seeds'])}). Each scenario's recorded inputs "
        "(episodes, MTBF/MTOL/MTOG) are re-run per seed (`full`), and with only the helium-machine overrides "
        f"(`helium_only`, machines {meta.get('helium_machines')}) or only the neon-machine overrides (`neon_only`, "
        f"machines {meta.get('neon_machines')}). Each arm is paired by seed with a control that drops every "
        "gas-shortfall override (SimRLFab defaults MTBF 1000 / MTOL 200). Effect = arm - control, mean and SE over "
        "seeds. Helium enters from world_helium_model via upstream forwarding; neon status is LLM-extracted. "
        "`Recorded` is the pipeline run's value (upstream seed 10). Overrides are `machine:MTBF/MTOL`.",
        "",
        "| Scenario | He gap % | Episodes | Arm | Overrides | KPI | Recorded | Arm mean ± sd | Control mean ± sd | Effect ± SE | > 2 SE |",
        "|---|---:|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['scenario_id']} | {_fmt(r['helium_supply_reduction_pct'], 2)} | {r['episodes']} | {r['arm']} | "
            f"{r['overrides']} | {r['kpi']} | {_fmt(r['recorded_seed10'])} | "
            f"{_fmt(r['shocked_mean'])} ± {_fmt(r['shocked_sd'])} | "
            f"{_fmt(r['control_mean'])} ± {_fmt(r['control_sd'])} | {_fmt(r['paired_diff_mean'])} ± {_fmt(r['paired_diff_se'])} | "
            f"{_fmt(r['diff_exceeds_2se'])} |"
        )
    if meta.get("errors"):
        lines += ["", "Driver errors:", ""] + [f"- {e}" for e in meta["errors"]]
    (out_dir / "simrlfab_seed_band.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--state-dir", default=str(ROOT / "data" / "pipeline_state"))
    ap.add_argument("--seeds", default="10-19")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--python", default=None, help="SimRLFab interpreter (default: simrlfab.yaml python_executable)")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args(argv)

    from src.models.registry import _build_simrlfab_adapter

    adapter = _build_simrlfab_adapter(ROOT / "configs" / "model_configs")
    if adapter is None or adapter._sim_config is None:
        print("[band] no SimRLFab config; nothing to do", file=sys.stderr)
        return 1
    cfg = adapter._sim_config
    python = args.python or cfg.python_executable
    repo, driver = Path(cfg.simrlfab_repo_path), Path(cfg.driver_script)

    seeds = parse_seeds(args.seeds)
    cells = load_cells(Path(args.state_dir), args.run_id)
    if not cells:
        print(f"[band] no completed simrlfab records for {args.run_id}", file=sys.stderr)
        return 1

    he_m, ne_m = tuple(cfg.helium_affected_machines), tuple(cfg.neon_affected_machines)
    unique: dict[str, dict] = {}
    for cell in cells:
        for arm in ARMS:
            c = driver_config(cell, 0, arm, he_m, ne_m)
            unique.setdefault(config_key(c), {**c, "_label": f"{cell['scenario_id']}/{arm}"})
    print(f"[band] {len(cells)} cells, {len(unique)} distinct configs x {len(seeds)} seeds")

    draws: dict[str, dict[int, dict]] = {}
    draws_long, errors = [], []
    for key, base in unique.items():
        for sd in seeds:
            c = {k: v for k, v in base.items() if k != "_label"}
            c["seed"] = sd
            res = run_driver(c, python, repo, driver, args.timeout)
            if "_error" in res:
                errors.append(f"{base['_label']} seed {sd}: {res['_error']}")
                print(f"[band] {base['_label']} seed {sd}: ERROR {res['_error'][:200]}")
                continue
            draws.setdefault(key, {})[sd] = res
            draws_long.append({"config": base["_label"], "episodes": c["episodes"], "seed": sd, **res})
            print(f"[band] {base['_label']} seed {sd}: " + ", ".join(f"{k}={_fmt(v)}" for k, v in res.items()))

    rows = summarise(cells, draws, seeds, he_m, ne_m)
    meta = {"run_id": args.run_id, "seeds": seeds, "python": python, "repo": str(repo), "errors": errors,
            "helium_machines": list(he_m), "neon_machines": list(ne_m)}
    write_outputs(rows, draws_long, Path(args.out_dir), meta)
    print(f"[band] wrote {args.out_dir}/simrlfab_seed_band.{{md,csv,json}}")
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
