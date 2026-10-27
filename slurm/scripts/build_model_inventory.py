#!/usr/bin/env python3
"""Emit the model inventory tables (static and run-specific).

Static inventory (from the registry + ``src/models/implementation_info.py``):
one row per adapter with status, platform, default implementation mode,
calibration sources, key equations, limitations and licence notes.

Run-specific inventory (``--run-id`` with ``--state-dir`` or
``--from-report-dir``): the static rows joined with the coverage ledger
(``src/interface/coverage.py``) so each model also shows the scenarios it
completed, the implementation mode actually used (with its evidence) and
the skip class in the scenarios where it did not contribute. This is the
table reviewers asked for ("mark which models ran, and full vs simplified").

Outputs under ``--out-dir`` (default ``docs/revision``):

* ``model_inventory.{json,md,tex}`` (static)
* ``model_inventory_<run_id>.{json,md,tex}`` (run-specific, when a run is given)

``--update-readme`` rewrites the block between ``<!-- inventory:start -->``
and ``<!-- inventory:end -->`` in ``README.md`` with the static tables
grouped by commodity system (the README sync test checks they match).

Usage::

    python slurm/scripts/build_model_inventory.py
    python slurm/scripts/build_model_inventory.py --run-id 20260504_222710 \
        --from-report-dir data/20260504_222710
    python slurm/scripts/build_model_inventory.py --update-readme
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import get_project_root, logger, state_dir  # noqa: E402
from src.interface.coverage import (  # noqa: E402
    CoverageCell,
    canonical_scenario_order,
    ledger_from_report_csv,
    ledger_from_state_dir,
)
from src.models.registry import build_default_registry, default_config_dir  # noqa: E402

SYSTEM_TITLES = OrderedDict([
    ("water", "Water"),
    ("oil", "Oil"),
    ("lng", "LNG"),
    ("helium_semiconductors", "Helium & Semiconductors"),
    ("fertilizer_agriculture", "Fertilizer & Agriculture"),
    ("shipping", "Shipping"),
    ("macroeconomic", "Macroeconomic / General Equilibrium"),
    ("energy_systems", "Energy systems (long-run)"),
])
SCENARIO_SHORT = {
    "swift_contained": "A", "prolonged_contained": "B", "swift_escalated": "C",
    "prolonged_escalated": "D", "infrastructure_collapse": "E",
}
README_START = "<!-- inventory:start -->"
README_END = "<!-- inventory:end -->"


def static_inventory() -> list[dict[str, Any]]:
    registry = build_default_registry(default_config_dir())
    return registry.inventory()


# ---------------------------------------------------------------------------
# Run-specific join
# ---------------------------------------------------------------------------


def join_with_ledger(rows: list[dict[str, Any]], cells: list[CoverageCell]) -> list[dict[str, Any]]:
    scenarios = canonical_scenario_order(c.scenario_id for c in cells)
    by_model: dict[str, list[CoverageCell]] = {}
    for c in cells:
        by_model.setdefault(c.model_id, []).append(c)
    out = []
    for r in rows:
        mcells = sorted(by_model.get(r["model_id"], []), key=lambda c: scenarios.index(c.scenario_id) if c.scenario_id in scenarios else 99)
        ran = [c.scenario_id for c in mcells if c.contributed]
        modes_used = sorted({(c.implementation_mode or "unknown", c.implementation_mode_evidence) for c in mcells if c.contributed})
        not_run = {c.scenario_id: c.skip_class for c in mcells if not c.contributed}
        stale = [c.scenario_id for c in mcells if c.stale_upstream]
        rr = dict(r)
        rr.update({
            "scenarios": scenarios,
            "ran_in_scenarios": ran,
            "ran_in_scenarios_short": "".join(SCENARIO_SHORT.get(s, s[:1].upper()) for s in ran) or "-",
            "implementation_used": [{"mode": m, "evidence": e} for m, e in modes_used],
            "skip_class_by_scenario": not_run,
            "stale_upstream_scenarios": stale,
            "n_scenarios_completed": len(ran),
        })
        out.append(rr)
    return out


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _md(s: Any) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _tex(s: Any) -> str:
    return (
        str(s).replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("&", "\\&")
        .replace("%", "\\%").replace("#", "\\#").replace("{", "\\{").replace("}", "\\}")
        .replace("^", "\\^{}").replace("~", "\\~{}").replace("<", "\\textless{}").replace(">", "\\textgreater{}")
    )


def _join(items: list[str], sep: str = "; ") -> str:
    return sep.join(items) if items else ""


def readme_tables(rows: list[dict[str, Any]]) -> str:
    """Markdown tables grouped by commodity system for README.md."""
    lines: list[str] = []
    for system, title in SYSTEM_TITLES.items():
        srows = [r for r in rows if r["commodity_system"] == system]
        if not srows:
            continue
        lines += [f"### {title}", "", "| Model | Adapter | Status | Notes |", "|---|---|---|---|"]
        for r in srows:
            notes = r["platform"]
            if r["limitations"]:
                notes += f". {r['limitations'][0]}"
            lines.append(f"| {_md(r['display_name'])} | `{r['adapter_path']}` | {_md(r['status_label'])} | {_md(notes)} |")
        lines.append("")
    # Summary counts by status label.
    counts: dict[str, list[str]] = {}
    for r in rows:
        counts.setdefault(r["status_label"], []).append(r["model_id"])
    lines += ["### Summary", ""]
    for label, ids in sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"- **{label} ({len(ids)}):** " + ", ".join(f"`{i}`" for i in sorted(ids)))
    lines += ["", "Stubs do not break the pipeline: the executor catches `NotImplementedError`, marks the run as `SKIPPED`, and continues with the remaining models. The coverage ledger (`slurm/scripts/build_coverage_ledger.py`) records why every (scenario, model) cell did or did not contribute, and the run-specific inventory (`slurm/scripts/build_model_inventory.py --run-id ...`) records which implementation mode each completed cell used.", ""]
    return "\n".join(lines)


def render_static_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# Model inventory (static)", "", "Generated by `slurm/scripts/build_model_inventory.py` from `src/models/implementation_info.py`.", ""]
    lines += ["| Model | id | System | Level | Status | Default mode | Platform | Calibration sources | Key equations | Limitations | Licence |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| " + " | ".join([
            _md(r["display_name"]), f"`{r['model_id']}`", r["commodity_system"], r["analytical_level"],
            _md(r["status_label"]), r["mode_when_executed"], _md(r["platform"]),
            _md(_join(r["calibration_sources"])), _md(_join(r["key_equations"])), _md(_join(r["limitations"])),
            _md(r["license_notes"]),
        ]) + " |")
    lines.append("")
    return "\n".join(lines)


def render_run_markdown(rows: list[dict[str, Any]], run_id: str) -> str:
    lines = [f"# Run-specific model inventory for run `{run_id}`", "",
             "Columns: *Ran in* lists the scenarios (A–E) in which the model completed; *Implementation used* is the mode actually recorded for those cells (evidence: recorded marker, output marker, or the adapter's declared default); *Not run* gives the skip class per scenario where the model did not contribute.", ""]
    lines += ["| Model | id | System | Status (available) | Ran in | Implementation used | Not run (scenario: reason) | Calibration sources | Key equations | Limitations |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        used = "; ".join(f"{u['mode']} ({u['evidence']})" for u in r["implementation_used"]) or "-"
        not_run = "; ".join(f"{SCENARIO_SHORT.get(s, s)}: {k}" for s, k in r["skip_class_by_scenario"].items()) or "-"
        lines.append("| " + " | ".join([
            _md(r["display_name"]), f"`{r['model_id']}`", r["commodity_system"], _md(r["status_label"]),
            r["ran_in_scenarios_short"], _md(used), _md(not_run),
            _md(_join(r["calibration_sources"])), _md(_join(r["key_equations"])), _md(_join(r["limitations"])),
        ]) + " |")
    lines.append("")
    return "\n".join(lines)


def render_latex(rows: list[dict[str, Any]], run_id: str | None = None) -> str:
    run_specific = run_id is not None and rows and "ran_in_scenarios_short" in rows[0]
    caption = (
        f"Run-specific model inventory for run {_tex(run_id)}: implementation used, scenarios completed, and reasons for non-contribution."
        if run_specific else "Model inventory: implementation status, platform, calibration sources, key equations and limitations."
    )
    if run_specific:
        cols = "p{2.6cm}p{1.5cm}p{2.0cm}p{0.9cm}p{2.4cm}p{2.6cm}p{3.2cm}"
        header = "Model & System & Status & Ran in & Implementation used & Not run & Key equations / limitations \\\\"
    else:
        cols = "p{2.8cm}p{1.6cm}p{2.3cm}p{2.4cm}p{3.2cm}p{3.4cm}"
        header = "Model & System & Status & Platform & Calibration sources & Key equations / limitations \\\\"
    out = [
        "% Generated by slurm/scripts/build_model_inventory.py; do not edit by hand.",
        "\\begin{longtable}{" + cols + "}",
        f"\\caption{{{caption}}}\\label{{tab:model_inventory{'_run' if run_specific else ''}}}\\\\",
        "\\toprule", header, "\\midrule", "\\endfirsthead",
        "\\toprule", header, "\\midrule", "\\endhead", "\\bottomrule", "\\endfoot",
    ]
    for r in rows:
        eq = _tex(_join(r["key_equations"]))
        lim = _tex(_join(r["limitations"]))
        eql = (eq + (" \\textit{Limitations: }" + lim if lim else "")) if eq or lim else ""
        if run_specific:
            used = _tex("; ".join(f"{u['mode']} ({u['evidence']})" for u in r["implementation_used"]) or "-")
            not_run = _tex("; ".join(f"{SCENARIO_SHORT.get(s, s)}: {k}" for s, k in r["skip_class_by_scenario"].items()) or "-")
            out.append(" & ".join([_tex(r["display_name"]), _tex(r["commodity_system"]), _tex(r["status_label"]),
                                   _tex(r["ran_in_scenarios_short"]), used, not_run, eql]) + " \\\\")
        else:
            out.append(" & ".join([_tex(r["display_name"]), _tex(r["commodity_system"]), _tex(r["status_label"]),
                                   _tex(r["platform"]), _tex(_join(r["calibration_sources"])), eql]) + " \\\\")
    out += ["\\end{longtable}", ""]
    return "\n".join(out)


def update_readme(readme_path: Path, tables_md: str) -> bool:
    text = readme_path.read_text(encoding="utf-8")
    if README_START not in text or README_END not in text:
        raise RuntimeError(f"{readme_path} lacks {README_START} / {README_END} markers")
    pattern = re.compile(re.escape(README_START) + r".*?" + re.escape(README_END), re.DOTALL)
    new_block = f"{README_START}\n{tables_md.rstrip()}\n{README_END}"
    new_text = pattern.sub(lambda _m: new_block, text, count=1)
    changed = new_text != text
    if changed:
        readme_path.write_text(new_text, encoding="utf-8")
    return changed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", default=None)
    p.add_argument("--state-dir", default=None)
    p.add_argument("--outputs-root", default=None)
    p.add_argument("--from-report-dir", default=None)
    p.add_argument("--out-dir", default="docs/revision")
    p.add_argument("--update-readme", action="store_true")
    args = p.parse_args(argv)

    root = get_project_root()
    rows = static_inventory()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model_inventory.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "model_inventory.md").write_text(render_static_markdown(rows), encoding="utf-8")
    (out_dir / "model_inventory.tex").write_text(render_latex(rows), encoding="utf-8")
    logger.info(f"wrote static inventory ({len(rows)} adapters) to {out_dir}")

    if args.run_id:
        if args.from_report_dir:
            cells = ledger_from_report_csv(args.run_id, Path(args.from_report_dir) / "csv")
        else:
            sdir = Path(args.state_dir) if args.state_dir else state_dir()
            outputs_root = Path(args.outputs_root) if args.outputs_root else root / "data" / "outputs"
            cells = ledger_from_state_dir(args.run_id, sdir, outputs_root)
        joined = join_with_ledger(rows, cells)
        base = out_dir / f"model_inventory_{args.run_id}"
        base.with_suffix(".json").write_text(json.dumps(joined, indent=2), encoding="utf-8")
        base.with_suffix(".md").write_text(render_run_markdown(joined, args.run_id), encoding="utf-8")
        base.with_suffix(".tex").write_text(render_latex(joined, args.run_id), encoding="utf-8")
        n_full = sum(1 for r in joined if any(u["mode"] == "full_upstream" for u in r["implementation_used"]))
        n_red = sum(1 for r in joined if any(u["mode"] == "analytical_reduction" for u in r["implementation_used"]))
        n_ing = sum(1 for r in joined if any(u["mode"] == "published_output_ingestion" for u in r["implementation_used"]))
        logger.info(
            f"run {args.run_id}: {sum(1 for r in joined if r['n_scenarios_completed'])} models contributed; "
            f"full upstream {n_full}, analytical reduction {n_red}, published-output ingestion {n_ing}"
        )

    if args.update_readme:
        changed = update_readme(root / "README.md", readme_tables(rows))
        logger.info("README.md inventory block " + ("updated" if changed else "already up to date"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
