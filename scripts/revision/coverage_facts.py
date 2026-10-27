#!/usr/bin/env python3
"""Coverage facts for the Section 1 wording items, derived from a coverage ledger.

Turns the per-cell coverage ledger (``slurm/scripts/build_coverage_ledger.py``)
into the specific statements the manuscript needs:

* for each model of interest, the scenarios in which it completed, was
  skipped or failed (with the skip class), or has no surviving record;
* whether the water models (``cwatm``, ``weap_mena``, ``sahysmod``) ran under
  the infrastructure-collapse scenario and whether any macro CGE under that
  scenario lists ``cwatm`` among its upstream sources (the water forwarding
  rule fires only there);
* which scenarios the helium and fertilizer upstream models completed in, so
  the text can say exactly where the helium and fertilizer linkages were
  model-computed rather than LLM-extracted.

Usage::

    python scripts/revision/coverage_facts.py --ledger data/reports/<run_id>/coverage/coverage_ledger.csv \
        --run-id 20260504_222710 --out-dir docs/revision
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SCENARIO_ORDER = ["swift_contained", "prolonged_contained", "swift_escalated", "prolonged_escalated", "infrastructure_collapse"]
SCENARIO_LETTER = dict(zip(SCENARIO_ORDER, "ABCDE"))
DEFAULT_MODELS = ["world_helium_model", "argonne_abm", "simrlfab", "world_fertilizer", "apsim", "cwatm", "weap_mena",
                  "sahysmod", "lngst", "energy_flux_lng_profits", "nems", "mam", "poles_jrc", "fed_oil", "pycge", "mpsge_jl", "nrel"]
WATER_MODELS = ["cwatm", "weap_mena", "sahysmod"]
MACRO_CGES = ["pycge", "mpsge_jl", "opencge"]
TAIL_RISK = "infrastructure_collapse"


def load_ledger(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sources(cell: dict[str, str]) -> list[dict[str, Any]]:
    """Parse the ledger's ``upstream_sources`` column.

    Entries look like ``poles_jrc`` or ``cwatm(not run)``; the suffix marks an
    override whose source model has no surviving completed record in this
    run (tier collision or stale output from another run).
    """
    raw = cell.get("upstream_sources") or ""
    out: list[dict[str, Any]] = []
    for token in (t.strip() for t in raw.split(";") if t.strip()):
        name, _, rest = token.partition("(")
        out.append({"model_id": name.strip(), "ran_this_run": "not run" not in rest})
    return out


def model_facts(cells: list[dict[str, str]], model_id: str) -> dict[str, Any]:
    by_scenario = {c["scenario_id"]: c for c in cells if c["model_id"] == model_id}
    completed, skipped, failed, missing = [], [], [], []
    detail: dict[str, dict[str, Any]] = {}
    for sid in SCENARIO_ORDER:
        c = by_scenario.get(sid)
        if c is None:
            missing.append(sid)
            detail[sid] = {"exec_status": "absent", "skip_class": "absent"}
            continue
        status = (c.get("exec_status") or "").lower()
        detail[sid] = {"exec_status": status, "skip_class": c.get("skip_class"), "implementation_mode": c.get("implementation_mode") or None,
                       "upstream_sources": _sources(c), "error_message": (c.get("error_message") or "")[:160]}
        if status == "completed":
            completed.append(sid)
        elif status == "skipped":
            skipped.append(sid)
        elif status == "failed":
            failed.append(sid)
        else:
            missing.append(sid)
    letters = lambda ids: "".join(SCENARIO_LETTER.get(s, "?") for s in ids) or "-"  # noqa: E731
    modes = sorted({d["implementation_mode"] for d in detail.values() if d.get("implementation_mode")})
    statement = (
        f"`{model_id}` completed in {letters(completed)}"
        + (f" ({', '.join(modes)})" if modes else "")
        + (f"; skipped in {letters(skipped)}" if skipped else "")
        + (f"; failed in {letters(failed)}" if failed else "")
        + (f"; no surviving record in {letters(missing)}" if missing else "")
        + "."
    )
    return {"model_id": model_id, "completed": completed, "skipped": skipped, "failed": failed, "no_record": missing,
            "implementation_modes": modes, "detail": detail, "statement": statement}


def water_linkage_facts(cells: list[dict[str, str]]) -> dict[str, Any]:
    tail = [c for c in cells if c["scenario_id"] == TAIL_RISK]
    water_status = {m: next(((c.get("exec_status") or "").lower() for c in tail if c["model_id"] == m), "absent") for m in WATER_MODELS}
    cge_sources = {m: next((_sources(c) for c in tail if c["model_id"] == m), []) for m in MACRO_CGES}
    cge_status = {m: next(((c.get("exec_status") or "").lower() for c in tail if c["model_id"] == m), "absent") for m in MACRO_CGES}
    evidence = {c["model_id"]: c.get("upstream_evidence") for c in tail if c["model_id"] in MACRO_CGES}
    water_fed = {m: any(s["model_id"] in WATER_MODELS and s["ran_this_run"] for s in src) for m, src in cge_sources.items()}
    water_fed_unconfirmed = {m: any(s["model_id"] in WATER_MODELS and not s["ran_this_run"] for s in src) for m, src in cge_sources.items()}
    any_water_model_ran = any(s == "completed" for s in water_status.values())
    if any(water_fed.values()):
        statement = ("Under the infrastructure-collapse scenario the macro CGEs that list a water model among their upstream "
                     f"sources are: {', '.join(m for m, v in water_fed.items() if v)}; their water shock was model-computed.")
    elif any(water_fed_unconfirmed.values()):
        statement = ("Under the infrastructure-collapse scenario the macro CGEs "
                     f"{', '.join(m for m, v in water_fed_unconfirmed.items() if v)} carry a water override record, but the water "
                     "model it cites has no surviving completed record for this run (tier collision or a stale output from an "
                     "earlier run). The water shock was model-derived, but its run provenance cannot be confirmed from the saved "
                     "records; recover data/outputs before citing it.")
    elif any_water_model_ran:
        statement = ("Under the infrastructure-collapse scenario a water model completed "
                     f"({', '.join(m for m, s in water_status.items() if s == 'completed')}) but no macro CGE record lists it as an "
                     "upstream source, so the macro water shock there should be treated as LLM-extracted unless the override "
                     "audit file shows otherwise.")
    else:
        statement = ("Under the infrastructure-collapse scenario no water model has a completed record in this ledger, so the "
                     "macro water shock there was LLM-extracted (or the record was lost); mark E macro results accordingly.")
    return {"scenario": TAIL_RISK, "water_model_status": water_status, "macro_cge_status": cge_status,
            "macro_cge_upstream_sources": cge_sources, "macro_cge_upstream_evidence": evidence,
            "macro_cge_water_fed": water_fed, "macro_cge_water_fed_unconfirmed": water_fed_unconfirmed, "statement": statement}


def build_facts(cells: list[dict[str, str]], run_id: str, models: list[str] | None = None) -> dict[str, Any]:
    models = models or DEFAULT_MODELS
    present = {c["model_id"] for c in cells}
    facts = [model_facts(cells, m) for m in models if m in present or True]
    helium = model_facts(cells, "world_helium_model")
    fert = model_facts(cells, "world_fertilizer")
    letters = lambda ids: "".join(SCENARIO_LETTER.get(s, "?") for s in ids) or "none"  # noqa: E731
    linkage = {
        "helium": f"The helium linkage (world_helium_model -> argonne_abm / simrlfab / macro) was model-computed in scenarios {letters(helium['completed'])}.",
        "fertilizer": f"The fertilizer linkage (world_fertilizer -> apsim / macro) was model-computed in scenarios {letters(fert['completed'])}.",
    }
    n_missing = sum(1 for c in cells if (c.get("skip_class") or "") in ("record_missing", "record_overwritten"))
    caveat = (f"{n_missing} of {len(cells)} cells in this ledger have no surviving record (skip class record_missing / "
              "record_overwritten); statements about those cells describe the saved record, not the cluster's data/outputs copy. "
              "Rebuild the ledger after scripts/revision/recover_run_from_outputs.py to replace them."
              if n_missing else "Every cell in this ledger carries an execution record.")
    return {"run_id": run_id, "cells": len(cells), "models": facts, "water_linkage": water_linkage_facts(cells),
            "linkage_statements": linkage, "caveat": caveat}


def render_markdown(f: dict[str, Any]) -> str:
    lines = [f"# Coverage facts for run `{f['run_id']}`", "", f["caveat"], "",
             "Scenario letters: " + ", ".join(f"{v} = {k}" for k, v in SCENARIO_LETTER.items()) + ".", "",
             "## Per model", ""]
    for m in f["models"]:
        lines.append(f"- {m['statement']}")
    lines += ["", "## Helium and fertilizer linkages", "", f"- {f['linkage_statements']['helium']}", f"- {f['linkage_statements']['fertilizer']}",
              "", "## Water linkage under the tail-risk scenario", "", f["water_linkage"]["statement"], "",
              "| model | status under E | upstream sources |", "|---|---|---|"]
    wl = f["water_linkage"]
    for m, s in wl["water_model_status"].items():
        lines.append(f"| {m} | {s} | |")
    for m, s in wl["macro_cge_status"].items():
        srcs = wl["macro_cge_upstream_sources"].get(m) or []
        rendered = ", ".join(x["model_id"] + ("" if x["ran_this_run"] else " (not run)") for x in srcs)
        lines.append(f"| {m} | {s} | {rendered or '-'} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ledger", required=True, help="coverage_ledger.csv from build_coverage_ledger.py")
    p.add_argument("--run-id", default=None)
    p.add_argument("--models", default=None, help="Comma-separated model ids (default: the Section 1 set).")
    p.add_argument("--out-dir", default="docs/revision")
    args = p.parse_args(argv)
    cells = load_ledger(Path(args.ledger))
    run_id = args.run_id or Path(args.ledger).resolve().parent.parent.name
    facts = build_facts(cells, run_id, [m.strip() for m in args.models.split(",")] if args.models else None)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"coverage_facts_{run_id}.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    (out / f"coverage_facts_{run_id}.md").write_text(render_markdown(facts), encoding="utf-8")
    print("\n".join(m["statement"] for m in facts["models"]))
    print(facts["water_linkage"]["statement"])
    print(f"wrote {out / ('coverage_facts_' + run_id + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
