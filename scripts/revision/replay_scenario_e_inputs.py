#!/usr/bin/env python3
"""How much two extraction errors move Scenario E in the macro kernel (Reviewer 2, point 3).

In run ``20260504_222710`` the LLM wrote "30% of global helium supply" as
``qatar_helium_supply_loss_pct = 0.3`` and gave CWatM the status ``damaged``,
which is not in its vocabulary and is read as intact. This replays
``macro_kernel.compute_macro_outcomes`` with the recorded pycge inputs and with
those inputs corrected. No LLM call and no pipeline state is touched.

This is a sensitivity check on the analytical kernel, not a result to report as
a model run, and it covers pycge's kernel only. The corrected water shock assumes
``severely_damaged``, the status the scenario framework stipulates, with the
recorded 10% demand rise: ``(1.10 - 0.25) / 1.10 = 77.3%``.

Usage::

    python scripts/revision/replay_scenario_e_inputs.py --out-dir docs/revision/runs/20260504_222710_filled
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.models.macro.macro_kernel import compute_macro_outcomes  # noqa: E402

RECORDED = {"oil": 48.36, "lng": 40.0, "fertilizer": 30.321, "helium": 0.3}
DURATION_MONTHS = 5.0
RECORDED_GDP = -0.8636
WATER_AS_FORWARDED = 9.091
WATER_SEVERELY_DAMAGED = round((1.10 - 0.25) / 1.10 * 100.0, 3)
SCENARIO_D_GDP = -1.0575

CASES: tuple[tuple[str, dict[str, float]], ...] = (
    ("recorded inputs", {}),
    ("water as forwarded (9.091)", {"water": WATER_AS_FORWARDED}),
    ("helium corrected (30)", {"helium": 30.0}),
    ("helium corrected, water as forwarded", {"helium": 30.0, "water": WATER_AS_FORWARDED}),
    ("water severely_damaged (77.273)", {"water": WATER_SEVERELY_DAMAGED}),
    ("helium corrected, water severely_damaged", {"helium": 30.0, "water": WATER_SEVERELY_DAMAGED}),
)


def replay(regime: str = "short_run") -> list[dict[str, Any]]:
    rows = []
    for label, change in CASES:
        out = compute_macro_outcomes({**RECORDED, **change}, DURATION_MONTHS, regime=regime)
        rows.append({"case": label, "shocks": {**RECORDED, **change}, "gdp_impact_pct": out["gdp_impact_pct"],
                     "cpi_inflation_pct": out["cpi_inflation_pct"], "gdp_impact_pct_world_weighted": out.get("gdp_impact_pct_world_weighted")})
    return rows


def render(rows: list[dict[str, Any]]) -> str:
    lines = ["# Scenario E input replay (pycge macro kernel)", "",
             f"Sensitivity check only, not a model result. Run `20260504_222710` recorded E GDP {RECORDED_GDP} and D GDP {SCENARIO_D_GDP}.", "",
             "| case | GDP impact % | CPI inflation % | world-weighted GDP % |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} | {r['gdp_impact_pct']} | {r['cpi_inflation_pct']} | {r['gdp_impact_pct_world_weighted']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--regime", default="short_run")
    args = p.parse_args(argv)
    rows = replay(args.regime)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "scenario_e_input_replay.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (args.out_dir / "scenario_e_input_replay.md").write_text(render(rows), encoding="utf-8")
    print(render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
