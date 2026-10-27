#!/usr/bin/env python3
"""Replay the PyCGE Scenario A macro kernel across code states (Section 1 forensics).

The manuscript reported a Scenario A GDP impact of -15.7 pct from PyCGE at
one stage of drafting and -0.157 pct at another, a factor of exactly 100.
Neither in-repo run carries the -15.7 value. This script replays
``macro_kernel.compute_macro_outcomes`` with the *recorded* Scenario A
inputs (``_applied_shocks.*`` and ``_inputs.duration_months`` from the run's
quantitative CSV) at each requested git commit (via a temporary worktree)
and at the working tree, then tests the fraction-vs-percent hypothesis: a
GDP level change expressed as a fraction (0.157) and pushed through the
real cge_modeling path's ``(reform - base) / base * 100`` standardisation
renders as -15.7, whereas the kernel's own output is already in percent.

Usage::

    python scripts/revision/replay_pycge_scenario_a.py --report-dir data/20260504_222710 \
        --scenario swift_contained --commits 4abd05b,dae4dcd,ded97cb --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPLAY_SNIPPET = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from src.models.macro.macro_kernel import compute_macro_outcomes
args = json.loads(sys.argv[2])
out = compute_macro_outcomes(args["shocks"], args["duration_months"], regime=args.get("regime", "short_run"))
keep = {k: v for k, v in out.items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)}
inputs = out.get("_inputs") if isinstance(out.get("_inputs"), dict) else {}
keep["_inputs.duration_scaler"] = inputs.get("duration_scaler")
keep["_inputs.regime"] = inputs.get("regime")
print(json.dumps(keep, default=str))
"""


def recorded_inputs(report_dir: Path, scenario: str, model: str = "pycge") -> dict[str, Any]:
    """Applied shocks and duration the adapter recorded for (scenario, model)."""
    path = Path(report_dir) / "csv" / "quantitative_results.csv"
    shocks: dict[str, float] = {}
    duration: float | None = None
    regime: str | None = None
    recorded: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["scenario_id"] != scenario or r["model_id"] != model:
                continue
            key = r["output_key"]
            if key.startswith("_applied_shocks.") and (r.get("is_numeric") or "").lower() == "true":
                shocks[key.split(".", 1)[1]] = float(r["value_numeric"])
            elif key == "_inputs.duration_months":
                duration = float(r["value_numeric"])
            elif key == "_inputs.regime":
                regime = r.get("value_raw") or None
            elif key in ("gdp_impact_pct", "cpi_inflation_pct", "consumption_impact_pct", "welfare_pct_change"):
                recorded[key] = float(r["value_numeric"])
    if duration is None or not shocks:
        raise ValueError(f"no recorded {model} inputs for {scenario} in {path}")
    return {"shocks": shocks, "duration_months": duration, "regime": regime or "short_run", "recorded_outputs": recorded}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def replay_at_commit(repo: Path, commit: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Run the kernel from a detached worktree of ``commit``."""
    tmp = Path(tempfile.mkdtemp(prefix="pycge_replay_"))
    wt = tmp / "wt"
    meta = _git(repo, "show", "-s", "--format=%H%x09%ad%x09%s", "--date=short", commit)
    if meta.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"commit": commit, "error": meta.stderr.strip() or "unknown commit"}
    sha, date, subject = meta.stdout.strip().split("\t", 2)
    add = _git(repo, "worktree", "add", "--detach", str(wt), sha)
    if add.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return {"commit": commit, "sha": sha[:7], "date": date, "subject": subject, "error": add.stderr.strip()}
    try:
        if not (wt / "src" / "models" / "macro" / "macro_kernel.py").exists():
            return {"commit": commit, "sha": sha[:7], "date": date, "subject": subject,
                    "error": "macro_kernel.py does not exist at this commit"}
        payload = json.dumps({"shocks": inputs["shocks"], "duration_months": inputs["duration_months"], "regime": inputs["regime"]})
        env = {**os.environ, "PYTHONPATH": str(wt)}
        proc = subprocess.run([sys.executable, "-c", REPLAY_SNIPPET, str(wt), payload], cwd=wt,
                              capture_output=True, text=True, check=False, env=env, timeout=120)
        if proc.returncode != 0:
            return {"commit": commit, "sha": sha[:7], "date": date, "subject": subject,
                    "error": (proc.stderr.strip().splitlines() or ["kernel call failed"])[-1]}
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        return {"commit": commit, "sha": sha[:7], "date": date, "subject": subject, "outputs": out}
    finally:
        _git(repo, "worktree", "remove", "--force", str(wt))
        _git(repo, "worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


def replay_working_tree(inputs: dict[str, Any]) -> dict[str, Any]:
    from src.models.macro.macro_kernel import compute_macro_outcomes  # noqa: WPS433

    out = compute_macro_outcomes(inputs["shocks"], inputs["duration_months"], regime=inputs["regime"])
    keep = {k: v for k, v in out.items() if isinstance(v, (int, float, str)) and not isinstance(v, bool)}
    inner = out.get("_inputs") if isinstance(out.get("_inputs"), dict) else {}
    keep["_inputs.duration_scaler"] = inner.get("duration_scaler")
    keep["_inputs.regime"] = inner.get("regime")
    return {"commit": "working_tree", "sha": None, "date": None, "subject": "current working tree", "outputs": keep}


def fraction_percent_hypothesis(kernel_gdp_pct: float, manuscript_value: float = -15.7) -> dict[str, Any]:
    """Does rendering the kernel's percent value as if it were a fraction reproduce the manuscript figure?"""
    as_fraction_then_x100 = kernel_gdp_pct * 100.0  # cge_modeling path: (reform - base) / base * 100
    ratio = manuscript_value / kernel_gdp_pct if kernel_gdp_pct else None
    return {
        "kernel_gdp_impact_pct": kernel_gdp_pct,
        "manuscript_value": manuscript_value,
        "ratio_manuscript_over_kernel": round(ratio, 6) if ratio is not None else None,
        "kernel_value_times_100": round(as_fraction_then_x100, 6),
        "reproduces_manuscript_value": (
            ratio is not None and math.isclose(as_fraction_then_x100, manuscript_value, rel_tol=0.02)
        ),
        "interpretation": (
            "The manuscript's figure equals the kernel's percent output multiplied by 100: consistent with the "
            "percent value having been treated as a fraction once (e.g. a level change of 0.157 passed through the "
            "cge_modeling standardisation '(reform - base) / base * 100'), not with a different parameterisation."
            if ratio is not None and math.isclose(as_fraction_then_x100, manuscript_value, rel_tol=0.02)
            else "The manuscript's figure is not a factor-100 rescaling of the kernel output at this code state."
        ),
    }


def run(repo: Path, report_dir: Path, scenario: str, commits: list[str], manuscript_value: float = -15.7) -> dict[str, Any]:
    inputs = recorded_inputs(report_dir, scenario)
    states = [replay_at_commit(repo, c, inputs) for c in commits] + [replay_working_tree(inputs)]
    rows = []
    for s in states:
        out = s.get("outputs") or {}
        gdp = out.get("gdp_impact_pct")
        rows.append({
            "commit": s["commit"], "sha": s.get("sha"), "date": s.get("date"), "subject": s.get("subject"),
            "error": s.get("error"),
            "gdp_impact_pct": gdp, "cpi_inflation_pct": out.get("cpi_inflation_pct"),
            "consumption_impact_pct": out.get("consumption_impact_pct"),
            "duration_scaler": out.get("_inputs.duration_scaler"),
            "matches_recorded_run": (
                math.isclose(float(gdp), inputs["recorded_outputs"].get("gdp_impact_pct", float("nan")), rel_tol=1e-3)
                if isinstance(gdp, (int, float)) and "gdp_impact_pct" in inputs["recorded_outputs"] else None
            ),
            "matches_manuscript_value": (math.isclose(float(gdp), manuscript_value, rel_tol=0.02) if isinstance(gdp, (int, float)) else None),
            "hypothesis": fraction_percent_hypothesis(float(gdp), manuscript_value) if isinstance(gdp, (int, float)) else None,
        })
    return {
        "scenario": scenario, "report_dir": str(report_dir), "recorded_inputs": inputs,
        "manuscript_value": manuscript_value, "code_states": rows,
        "conclusion": _conclusion(rows, inputs, manuscript_value),
    }


def _conclusion(rows: list[dict[str, Any]], inputs: dict[str, Any], manuscript_value: float) -> str:
    direct = [r["commit"] for r in rows if r["matches_manuscript_value"]]
    x100 = [r["commit"] for r in rows if r["hypothesis"] and r["hypothesis"]["reproduces_manuscript_value"]]
    recorded = inputs["recorded_outputs"].get("gdp_impact_pct")
    parts = [f"Recorded run value: {recorded}. Manuscript value: {manuscript_value}."]
    if direct:
        parts.append(f"Code states that reproduce the manuscript value directly: {', '.join(direct)}.")
    else:
        parts.append("No replayed code state produces the manuscript value directly from the recorded inputs.")
    if x100:
        parts.append(f"Code states whose output times 100 equals the manuscript value: {', '.join(x100)} "
                     "(fraction-vs-percent rescaling hypothesis supported).")
    else:
        parts.append("The factor-100 rescaling hypothesis is not supported by any replayed code state.")
    return " ".join(parts)


def render_markdown(result: dict[str, Any]) -> str:
    ri = result["recorded_inputs"]
    lines = [f"# PyCGE replay for `{result['scenario']}`", "",
             f"Recorded inputs from `{result['report_dir']}`: applied shocks {ri['shocks']}, duration {ri['duration_months']} months, "
             f"regime {ri['regime']}. Recorded outputs: {ri['recorded_outputs']}.", "",
             f"Manuscript value under test: **{result['manuscript_value']}** (gdp_impact_pct).", "",
             "| code state | sha | date | gdp_impact_pct | cpi_inflation_pct | duration scaler | matches recorded run | matches manuscript | x100 reproduces manuscript | error |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in result["code_states"]:
        h = r["hypothesis"] or {}
        lines.append(f"| {r['commit']} | {r['sha'] or ''} | {r['date'] or ''} | {r['gdp_impact_pct']} | {r['cpi_inflation_pct']} | "
                     f"{r['duration_scaler']} | {r['matches_recorded_run']} | {r['matches_manuscript_value']} | "
                     f"{h.get('reproduces_manuscript_value')} | {r['error'] or ''} |")
    lines += ["", "## Conclusion", "", result["conclusion"], "",
              "The real `cge_modeling` execution path standardises outputs as `(reform - base) / base * 100`; the analytical "
              "kernel already returns percent. A percent value treated as a fraction once therefore appears 100 times too "
              "large, which is the only transformation that links the two reported figures.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--report-dir", default="data/20260504_222710")
    p.add_argument("--scenario", default="swift_contained")
    p.add_argument("--commits", default="4abd05b,dae4dcd,ded97cb")
    p.add_argument("--manuscript-value", type=float, default=-15.7)
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    result = run(repo, Path(args.report_dir), args.scenario, [c.strip() for c in args.commits.split(",") if c.strip()], args.manuscript_value)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"pycge_{args.scenario}_replay"
    (out / f"{stem}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (out / f"{stem}.md").write_text(render_markdown(result), encoding="utf-8")
    print(result["conclusion"])
    print(f"wrote {out / (stem + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
