#!/usr/bin/env python3
"""Merge re-executed cells into a copy of an earlier run's state, and check them.

Run 20260504_222710 lost per-cell records to the tier-file collision, and the
July batches then overwrote ``data/outputs``, so those records cannot be
recovered. The cells can be re-executed from the run's saved parameter records
under a separate run id with no LLM call. This script:

* copies the original run's state files to ``--out-state-dir``, leaving the
  originals untouched, and adds a ``<run_id>_model_refilled_<scenario>_<model>.json``
  record for every cell the original run has no record of;
* checks reproducibility: for cells present in both runs, compares every
  numeric output between the original record and the re-execution;
* checks consistency with what the original run actually used: compares each
  ``identity`` forwarding override recorded in ``<run_id>_macro_overrides.json``
  with the re-executed source model's output.

Point coverage tools at ``--out-state-dir``. Do not point the fidelity audit
there: the original synthesis only saw the original records.

Usage::

    python scripts/revision/merge_refilled_cells.py --run-id 20260504_222710 \
        --fill-run-id fill_may_20260504_222710 --state-dir data/pipeline_state \
        --out-state-dir data/pipeline_state_may_filled --report-dir docs/revision/runs/20260504_222710_filled
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.synthesis.fidelity import flatten_numeric  # noqa: E402

_REL_TOL = 1e-6


def load_records(state_dir: Path, run_id: str) -> dict[tuple[str, str], dict[str, Any]]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("scenario_id") and rec.get("model_id"):
            records[(rec["scenario_id"], rec["model_id"])] = rec
    return records


def compare_outputs(original: dict[str, Any], refilled: dict[str, Any]) -> dict[str, Any]:
    """Numeric differences between two output dicts, ignoring private keys."""
    a = {k: v for k, v in flatten_numeric(original or {}).items() if not k.startswith("_")}
    b = {k: v for k, v in flatten_numeric(refilled or {}).items() if not k.startswith("_")}
    shared = sorted(set(a) & set(b))
    diffs = [{"key": k, "original": a[k], "refilled": b[k]} for k in shared
             if not math.isclose(a[k], b[k], rel_tol=_REL_TOL, abs_tol=1e-9)]
    return {"shared": len(shared), "different": diffs, "only_original": sorted(set(a) - set(b)), "only_refilled": sorted(set(b) - set(a))}


def check_overrides(overrides: dict[str, Any], fill: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Compare forwarded values the original run used with the re-executed source outputs."""
    counts: Counter[str] = Counter()
    mismatches: list[dict[str, Any]] = []
    for scenario, by_model in overrides.items():
        if not isinstance(by_model, dict) or scenario.startswith("_"):
            continue
        for model, recs in by_model.items():
            for r in recs if isinstance(recs, list) else []:
                if r.get("transform") != "identity" or not isinstance(r.get("computed_value"), (int, float)):
                    counts["not_checked_transform"] += 1
                    continue
                source = fill.get((scenario, r.get("source_model_id")))
                if not source or source.get("status") != "completed":
                    counts["not_checked_source_not_completed"] += 1
                    continue
                value = flatten_numeric(source.get("outputs") or {}).get(r.get("source_field"))
                if value is None:
                    counts["not_checked_field_absent"] += 1
                elif math.isclose(value, r["computed_value"], rel_tol=_REL_TOL, abs_tol=1e-9):
                    counts["match"] += 1
                else:
                    counts["mismatch"] += 1
                    mismatches.append({"scenario": scenario, "model": model, "name": r.get("name"), "source": r.get("source_model_id"),
                                       "field": r.get("source_field"), "recorded": r["computed_value"], "refilled": value})
    return {"counts": dict(counts), "mismatches": mismatches}


def merge(run_id: str, fill_run_id: str, state_dir: Path, out_state_dir: Path,
          fill_state_dir: Path | None = None, note: str | None = None) -> dict[str, Any]:
    """``fill_state_dir`` (default ``state_dir``) holds the re-executed records;
    ``note`` replaces the default ``refilled_note`` (e.g. for a model the
    original run never had, as opposed to a lost record)."""
    original = load_records(state_dir, run_id)
    fill = load_records(fill_state_dir or state_dir, fill_run_id)
    out_state_dir.mkdir(parents=True, exist_ok=True)
    for path in state_dir.glob(f"{run_id}_*.json"):
        shutil.copy2(path, out_state_dir / path.name)
    manifests = state_dir / "manifests"
    if manifests.is_dir():
        (out_state_dir / "manifests").mkdir(exist_ok=True)
        for path in manifests.glob(f"{run_id}_*"):
            shutil.copy2(path, out_state_dir / "manifests" / path.name)

    added: list[dict[str, Any]] = []
    for (scenario, model), rec in sorted(fill.items()):
        if (scenario, model) in original:
            continue
        rec = {**rec, "refilled_from_run": fill_run_id,
               "refilled_note": note or f"Re-executed from {run_id}'s saved parameters; original record lost."}
        (out_state_dir / f"{run_id}_model_refilled_{scenario}_{model}.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
        added.append({"scenario": scenario, "model": model, "status": rec.get("status"), "implementation_mode": rec.get("implementation_mode")})

    repro: list[dict[str, Any]] = []
    for key in sorted(set(original) & set(fill)):
        a, b = original[key], fill[key]
        if a.get("status") == "completed" and b.get("status") == "completed":
            repro.append({"scenario": key[0], "model": key[1], **compare_outputs(a.get("outputs") or {}, b.get("outputs") or {})})
    status_changes = [{"scenario": k[0], "model": k[1], "original": original[k].get("status"), "refilled": fill[k].get("status")}
                      for k in sorted(set(original) & set(fill)) if original[k].get("status") != fill[k].get("status")]

    overrides_path = state_dir / f"{run_id}_macro_overrides.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    return {"run_id": run_id, "fill_run_id": fill_run_id, "added": added, "added_by_status": dict(Counter(a["status"] for a in added)),
            "reproducibility": repro, "status_changes": status_changes, "override_check": check_overrides(overrides, fill)}


def render(result: dict[str, Any]) -> str:
    repro = result["reproducibility"]
    differing = [r for r in repro if r["different"]]
    oc = result["override_check"]
    lines = [f"# Re-executed cells for run `{result['run_id']}`", "",
             f"Re-executed under `{result['fill_run_id']}` from the original run's saved parameters, with no LLM call and on current adapter code. "
             "The original synthesis saw none of the added cells.", "",
             f"## Added cells: {len(result['added'])}", "", f"By status: {result['added_by_status']}", "",
             "| scenario | model | status | implementation |", "|---|---|---|---|"]
    lines += [f"| {a['scenario']} | {a['model']} | {a['status']} | {a['implementation_mode']} |" for a in result["added"]]
    lines += ["", "## Reproducibility against surviving records", "",
              f"{len(repro)} cells completed in both runs; {len(repro) - len(differing)} reproduce every shared numeric output, {len(differing)} differ.", ""]
    if differing:
        lines += ["| scenario | model | shared | differing | example |", "|---|---|---|---|---|"]
        for r in differing:
            d = r["different"][0]
            lines.append(f"| {r['scenario']} | {r['model']} | {r['shared']} | {len(r['different'])} | {d['key']}: {d['original']} -> {d['refilled']} |")
        lines.append("")
    if result["status_changes"]:
        lines += ["Status changed between runs:", "", "| scenario | model | original | re-executed |", "|---|---|---|---|"]
        lines += [f"| {c['scenario']} | {c['model']} | {c['original']} | {c['refilled']} |" for c in result["status_changes"]]
        lines.append("")
    lines += ["## Forwarded values the original macro models used", "", f"Identity-transform overrides: {oc['counts']}", ""]
    if oc["mismatches"]:
        lines += ["| scenario | macro model | input | source | recorded | re-executed |", "|---|---|---|---|---|---|"]
        lines += [f"| {m['scenario']} | {m['model']} | {m['name']} | {m['source']}.{m['field']} | {m['recorded']} | {m['refilled']} |" for m in oc["mismatches"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", required=True)
    p.add_argument("--fill-run-id", required=True)
    p.add_argument("--state-dir", default="data/pipeline_state")
    p.add_argument("--out-state-dir", required=True)
    p.add_argument("--report-dir", required=True)
    args = p.parse_args(argv)

    result = merge(args.run_id, args.fill_run_id, Path(args.state_dir), Path(args.out_state_dir))
    report = Path(args.report_dir)
    report.mkdir(parents=True, exist_ok=True)
    (report / "refilled_cells.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (report / "refilled_cells.md").write_text(render(result), encoding="utf-8")
    print(f"added {len(result['added'])} cells {result['added_by_status']}; overrides {result['override_check']['counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
