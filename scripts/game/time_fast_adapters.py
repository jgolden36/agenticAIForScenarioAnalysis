#!/usr/bin/env python3
"""Time every adapter the war game could call in-round, through the ModelAdapter contract.

No LLM, no LangGraph graph, no forwarding: ``validate_inputs -> translate_inputs -> execute``
per adapter, with the analyst-authored parameters for one scenario from
``configs/baselines/hormuz_2026_analyst.yaml``. The result says which adapters run with no
external binary, licence or config (the game's Tier 1 candidates), how long each takes, and
which ones need parameters the baseline does not carry.

    python scripts/game/time_fast_adapters.py                       # swift_contained, Markdown table
    python scripts/game/time_fast_adapters.py --scenario prolonged_escalated --repeat 20
    python scripts/game/time_fast_adapters.py --out docs/game/fast_adapter_timings.md
"""
from __future__ import annotations

import argparse
import logging
import platform
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slurm" / "scripts"))

from run_deterministic_baseline import baseline_parameter_sets, load_baseline  # noqa: E402
from src.models.registry import build_default_registry  # noqa: E402


def time_cell(adapter, params, repeat):
    """``(status, seconds_per_call, note)`` for one (adapter, params) cell."""
    t0 = time.perf_counter()
    v = adapter.validate_inputs(params)
    if not v.valid:
        return "invalid", time.perf_counter() - t0, "; ".join(v.errors)
    try:
        out = None
        for _ in range(repeat):
            out = adapter.execute(adapter.translate_inputs(params))
    except NotImplementedError as e:
        return "not implemented", (time.perf_counter() - t0) / repeat, str(e).splitlines()[0][:140]
    except Exception as e:  # noqa: BLE001 -- report, never crash the table
        return "error", (time.perf_counter() - t0) / repeat, f"{type(e).__name__}: {e}"[:140]
    dt = (time.perf_counter() - t0) / repeat
    mode = (out.metadata or {}).get("mode") or (out.outputs or {}).get("_execution_mode") or adapter.implementation_info.mode_when_executed.value
    heads = [k for k, x in (out.outputs or {}).items() if isinstance(x, (int, float)) and not isinstance(x, bool) and not k.startswith("_")]
    return "ok", dt, f"mode={mode}; " + ", ".join(f"{k}={out.outputs[k]:.3g}" for k in heads[:4])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", default=str(ROOT / "configs" / "baselines" / "hormuz_2026_analyst.yaml"))
    ap.add_argument("--scenario", default="swift_contained")
    ap.add_argument("--repeat", type=int, default=5, help="executions per adapter; the table reports the mean")
    ap.add_argument("--with-config", action="store_true", help="load configs/model_configs (real paths may need binaries)")
    ap.add_argument("--out", default="", help="write the Markdown table here as well as to stdout")
    args = ap.parse_args(argv)
    logging.disable(logging.WARNING)

    baseline = load_baseline(args.baseline)
    registry = build_default_registry(config_dir=(ROOT / "configs" / "model_configs") if args.with_config else None)
    cells = baseline_parameter_sets(baseline, scenario_ids=[args.scenario])
    rows = []
    for _sid, mid, params in cells:
        adapter = registry.get(mid)
        if adapter is None:
            rows.append((mid, "", "not registered", 0.0, ""))
            continue
        status, dt, note = time_cell(adapter, params, max(1, args.repeat))
        rows.append((mid, adapter.commodity_system.value, status, dt, note))
    rows.sort(key=lambda r: (r[2] != "ok", r[1], r[0]))

    lines = [f"# Adapter timings without the LLM or the graph ({args.scenario})", "",
             f"Generated {date.today().isoformat()} by `scripts/game/time_fast_adapters.py` on Python "
             f"{platform.python_version()}, {'with' if args.with_config else 'without'} `configs/model_configs`; "
             f"mean of {args.repeat} executions per adapter; parameters from `{Path(args.baseline).name}`.", "",
             "| Model | System | Status | ms per call | Note |", "|---|---|---|---:|---|"]
    for mid, system, status, dt, note in rows:
        lines.append(f"| `{mid}` | {system} | {status} | {dt * 1000:.2f} | {note} |")
    ok = [r for r in rows if r[2] == "ok"]
    lines += ["", f"{len(ok)} of {len(rows)} adapters ran; total wall time for every runnable adapter in sequence: "
              f"{sum(r[3] for r in ok) * 1000:.1f} ms."]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
