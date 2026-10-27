#!/usr/bin/env python3
"""Build the per-cell coverage ledger for a pipeline run.

Answers "which models ran under which scenarios, and why not otherwise"
with one record per (scenario, model) cell. See
``src/interface/coverage.py`` for the classification rules.

Two evidence sources:

* ``--state-dir`` (default ``data/pipeline_state``): full evidence from
  ``<run_id>_params_*.json``, ``manifests/``, ``<run_id>_model_*.json``
  and ``data/outputs/`` (``--outputs-root``).
* ``--from-report-dir data/reports/<run_id>``: partial evidence from the
  Stage 5 CSVs (``csv/model_status.csv`` + ``csv/consistency_flags.csv``)
  when state files are no longer available.

Writes ``coverage_ledger.{csv,json,md,tex}`` and ``coverage_map.png`` to
``--out-dir`` (default ``data/reports/<run_id>/coverage``) and, when
``--docs-dir`` is given, copies the Markdown / LaTeX / PNG there for the
manuscript.

Usage::

    python slurm/scripts/build_coverage_ledger.py --run-id 20260504_222710
    python slurm/scripts/build_coverage_ledger.py --run-id 20260504_222710 \
        --from-report-dir data/20260504_222710 --docs-dir docs/revision
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import get_project_root, get_run_id, logger, state_dir  # noqa: E402
from src.interface.coverage import (  # noqa: E402
    ledger_from_report_csv,
    ledger_from_state_dir,
    summarize,
    write_all,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", default=None)
    p.add_argument("--state-dir", default=None, help="Defaults to data/pipeline_state.")
    p.add_argument("--outputs-root", default=None, help="Defaults to data/outputs.")
    p.add_argument("--from-report-dir", default=None, help="Build from <dir>/csv/*.csv instead of state files.")
    p.add_argument("--out-dir", default=None, help="Defaults to data/reports/<run_id>/coverage.")
    p.add_argument("--docs-dir", default=None, help="Also copy md/tex/png here (e.g. docs/revision).")
    p.add_argument("--no-figure", action="store_true")
    args = p.parse_args(argv)

    run_id = args.run_id or get_run_id()
    root = get_project_root()

    if args.from_report_dir:
        csv_dir = Path(args.from_report_dir) / "csv"
        cells = ledger_from_report_csv(run_id, csv_dir)
        logger.info(f"Coverage ledger from CSVs in {csv_dir}: {len(cells)} cells")
    else:
        sdir = Path(args.state_dir) if args.state_dir else state_dir()
        outputs_root = Path(args.outputs_root) if args.outputs_root else root / "data" / "outputs"
        cells = ledger_from_state_dir(run_id, sdir, outputs_root)
        logger.info(f"Coverage ledger from state dir {sdir}: {len(cells)} cells")

    out_dir = Path(args.out_dir) if args.out_dir else root / "data" / "reports" / run_id / "coverage"
    paths = write_all(cells, run_id, out_dir)
    summary = summarize(cells)
    logger.info(
        f"{summary['completed_cells']}/{summary['grid_cells']} cells completed; "
        f"skip classes: {summary['by_skip_class']}"
    )

    if not args.no_figure:
        try:
            from slurm.scripts.visualize_results import plot_coverage_map

            png = plot_coverage_map([c.to_dict() for c in cells], out_dir / "coverage_map.png", run_id=run_id)
            if png:
                paths["png"] = png
        except Exception as exc:  # noqa: BLE001 — figure is optional
            logger.warning(f"coverage_map.png not produced: {exc}")

    if args.docs_dir:
        docs = Path(args.docs_dir)
        docs.mkdir(parents=True, exist_ok=True)
        for key in ("md", "tex", "png", "csv"):
            src = paths.get(key)
            if src and src.exists():
                shutil.copy2(src, docs / f"coverage_ledger_{run_id}{src.suffix if key != 'png' else '.png'}")
        logger.info(f"Copied ledger artefacts to {docs}")

    for k, v in paths.items():
        logger.info(f"wrote {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
