#!/usr/bin/env python3
"""Numeric diff of two pipeline runs (LLM-driven vs deterministic baseline).

Joins the two runs' ``csv/quantitative_results.csv`` on
``(scenario_id, model_id, output_key)`` and classifies every numeric cell
as identical, within tolerance, or different, keeping the input echoes
(``_inputs.*``, ``_applied_shocks.*``, ``_upstream_overrides*``) in a
separate "inputs" group. Where the recorded inputs of a (scenario, model)
cell are identical across runs the outputs must be identical too (the
adapters are deterministic); where they differ, the output difference is
the contribution of whoever wrote the parameters. Also compares the per
cell execution status from ``csv/model_status.csv``.

Usage::

    python scripts/revision/compare_runs.py --a data/20260504_222710 --b data/reports/baseline_analyst \
        --label-a llm_20260504 --label-b analyst_baseline --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

INPUT_PREFIXES = ("_inputs.", "_applied_shocks.", "_upstream_overrides", "_params.", "_input_")


def resolve_report_dir(spec: str, repo_root: Path | None = None) -> Path:
    """A path, or a run id looked up under data/reports/<id> then data/<id>."""
    p = Path(spec)
    if p.exists():
        return p
    root = repo_root or Path(__file__).resolve().parents[2]
    for cand in (root / "data" / "reports" / spec, root / "data" / spec):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"no report directory for {spec!r}")


def load_quantitative(report_dir: Path) -> dict[tuple[str, str, str], float]:
    out: dict[tuple[str, str, str], float] = {}
    path = report_dir / "csv" / "quantitative_results.csv"
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("is_numeric") or "").lower() != "true":
                continue
            try:
                v = float(r.get("value_numeric") or "")
            except ValueError:
                continue
            if math.isnan(v):
                continue
            out[(r["scenario_id"], r["model_id"], r["output_key"])] = v
    return out


def load_status(report_dir: Path) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    path = report_dir / "csv" / "model_status.csv"
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(r["scenario_id"], r["model_id"])] = (r.get("status") or "").lower()
    return out


def _rel_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b))
    if denom == 0:
        return 0.0
    return abs(a - b) / denom * 100.0


def classify(a: float | None, b: float | None, tolerance_pct: float) -> str:
    if a is None:
        return "only_in_b"
    if b is None:
        return "only_in_a"
    if a == b or (math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)):
        return "identical"
    if _rel_diff(a, b) <= tolerance_pct:
        return "within_tolerance"
    return "differs"


def compare(dir_a: Path, dir_b: Path, *, label_a: str, label_b: str, tolerance_pct: float = 0.5) -> dict[str, Any]:
    qa, qb = load_quantitative(dir_a), load_quantitative(dir_b)
    sa, sb = load_status(dir_a), load_status(dir_b)
    keys = sorted(set(qa) | set(qb))
    rows: list[dict[str, Any]] = []
    for sid, mid, key in keys:
        a, b = qa.get((sid, mid, key)), qb.get((sid, mid, key))
        cat = classify(a, b, tolerance_pct)
        group = "inputs" if key.startswith(INPUT_PREFIXES) else "outputs"
        rows.append({
            "scenario_id": sid, "model_id": mid, "output_key": key, "group": group,
            f"value_{label_a}": a, f"value_{label_b}": b,
            "abs_diff": (None if a is None or b is None else round(b - a, 10)),
            "rel_diff_pct": (None if a is None or b is None else round(_rel_diff(a, b), 4)),
            "category": cat,
        })

    # Cells whose recorded inputs are identical must have identical outputs.
    inputs_identical: dict[tuple[str, str], bool] = {}
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_cell[(r["scenario_id"], r["model_id"])].append(r)
    cell_rows: list[dict[str, Any]] = []
    for (sid, mid), rs in sorted(by_cell.items()):
        inp = [r for r in rs if r["group"] == "inputs"]
        outp = [r for r in rs if r["group"] == "outputs"]
        same_inputs = bool(inp) and all(r["category"] == "identical" for r in inp)
        inputs_identical[(sid, mid)] = same_inputs
        out_cats = Counter(r["category"] for r in outp)
        cell_rows.append({
            "scenario_id": sid, "model_id": mid,
            f"status_{label_a}": sa.get((sid, mid), "absent"), f"status_{label_b}": sb.get((sid, mid), "absent"),
            "n_input_keys": len(inp), "inputs_identical": same_inputs if inp else None,
            "n_output_keys": len(outp), **{f"outputs_{c}": out_cats.get(c, 0) for c in ("identical", "within_tolerance", "differs", "only_in_a", "only_in_b")},
            "max_rel_diff_pct": max((r["rel_diff_pct"] or 0.0) for r in outp) if outp else None,
        })
    violations = [c for c in cell_rows if c["inputs_identical"] and (c["outputs_differs"] or c["outputs_within_tolerance"])]

    status_pairs = Counter()
    for cell in sorted(set(sa) | set(sb)):
        status_pairs[(sa.get(cell, "absent"), sb.get(cell, "absent"))] += 1

    out_rows = [r for r in rows if r["group"] == "outputs"]
    summary = {
        "label_a": label_a, "label_b": label_b, "dir_a": str(dir_a), "dir_b": str(dir_b),
        "tolerance_pct": tolerance_pct,
        "output_keys": len(out_rows),
        "output_categories": dict(Counter(r["category"] for r in out_rows)),
        "input_keys": len(rows) - len(out_rows),
        "input_categories": dict(Counter(r["category"] for r in rows if r["group"] == "inputs")),
        "cells_compared": len(cell_rows),
        "cells_with_identical_inputs": sum(1 for v in inputs_identical.values() if v),
        "determinism_violations": [(c["scenario_id"], c["model_id"]) for c in violations],
        "status_pairs": {f"{a}->{b}": n for (a, b), n in sorted(status_pairs.items())},
        "largest_output_differences": sorted(
            (r for r in out_rows if r["category"] == "differs"), key=lambda r: -(r["rel_diff_pct"] or 0)
        )[:25],
    }
    return {"summary": summary, "rows": rows, "cells": cell_rows}


def render_markdown(result: dict[str, Any]) -> str:
    s = result["summary"]
    a, b = s["label_a"], s["label_b"]
    lines = [f"# Run comparison: `{a}` vs `{b}`", "",
             f"Sources: `{s['dir_a']}` and `{s['dir_b']}`. Tolerance for 'within_tolerance': {s['tolerance_pct']} pct relative.", "",
             "## Outputs", "", f"- Numeric output keys compared: **{s['output_keys']}**",
             f"- Categories: {s['output_categories']}", "",
             "## Inputs recorded by the adapters", "", f"- Input echo keys compared: **{s['input_keys']}**",
             f"- Categories: {s['input_categories']}", "",
             "## Determinism check", "",
             f"- Cells with identical recorded inputs in both runs: **{s['cells_with_identical_inputs']}** of {s['cells_compared']}",
             f"- Cells where identical inputs gave different outputs: **{len(s['determinism_violations'])}** "
             + (f"({', '.join('/'.join(v) for v in s['determinism_violations'])})" if s["determinism_violations"] else "(none)"), "",
             "## Execution status pairs (a -> b)", "", "| pair | cells |", "|---|---|"]
    for pair, n in s["status_pairs"].items():
        lines.append(f"| {pair} | {n} |")
    lines += ["", "## Largest output differences", "",
              f"| scenario | model | key | {a} | {b} | rel diff pct |", "|---|---|---|---|---|---|"]
    for r in s["largest_output_differences"]:
        lines.append(f"| {r['scenario_id']} | {r['model_id']} | {r['output_key']} | {r[f'value_{a}']} | {r[f'value_{b}']} | {r['rel_diff_pct']} |")
    lines += ["", "## Per cell", "",
              f"| scenario | model | status {a} | status {b} | inputs identical | output keys | identical | within tol | differs | only {a} | only {b} | max rel diff pct |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in result["cells"]:
        lines.append(
            f"| {c['scenario_id']} | {c['model_id']} | {c[f'status_{a}']} | {c[f'status_{b}']} | {c['inputs_identical']} | "
            f"{c['n_output_keys']} | {c['outputs_identical']} | {c['outputs_within_tolerance']} | {c['outputs_differs']} | "
            f"{c['outputs_only_in_a']} | {c['outputs_only_in_b']} | {c['max_rel_diff_pct']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(result: dict[str, Any], out_dir: Path, stem: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"csv": out_dir / f"{stem}.csv", "cells_csv": out_dir / f"{stem}_cells.csv",
             "md": out_dir / f"{stem}.md", "json": out_dir / f"{stem}.json"}
    for key, rows in (("csv", result["rows"]), ("cells_csv", result["cells"])):
        with open(paths[key], "w", newline="", encoding="utf-8") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    paths["md"].write_text(render_markdown(result), encoding="utf-8")
    paths["json"].write_text(json.dumps(result["summary"], indent=2, default=str), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--a", required=True, help="Report dir or run id of run A (e.g. the LLM run).")
    p.add_argument("--b", required=True, help="Report dir or run id of run B (e.g. the deterministic baseline).")
    p.add_argument("--label-a", default=None)
    p.add_argument("--label-b", default=None)
    p.add_argument("--tolerance-pct", type=float, default=0.5)
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)
    dir_a, dir_b = resolve_report_dir(args.a), resolve_report_dir(args.b)
    label_a = args.label_a or dir_a.name
    label_b = args.label_b or dir_b.name
    result = compare(dir_a, dir_b, label_a=label_a, label_b=label_b, tolerance_pct=args.tolerance_pct)
    paths = write_outputs(result, Path(args.out_dir), f"compare_{label_a}_vs_{label_b}")
    print(json.dumps({**{k: v for k, v in result["summary"].items() if k != "largest_output_differences"},
                      "files": {k: str(v) for k, v in paths.items()}}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
