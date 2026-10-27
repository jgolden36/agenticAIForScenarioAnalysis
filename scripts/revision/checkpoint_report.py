#!/usr/bin/env python3
"""Document how the three analyst checkpoints operated in batch runs.

Reads each run's saved state (``<run_id>_scenarios.json`` for
``scenarios_validated``, ``<run_id>_params_*.json`` for the per-cell
``validation_status``, ``<run_id>_synthesis.json`` for
``synthesis_validated``) and writes ``docs/revision/checkpoints_in_batch_mode.md``
so the manuscript can scope its "never run unattended" claim to what was
actually recorded.

Usage::

    python scripts/revision/checkpoint_report.py --run-id 20260504_222710 \
        [--run-id weekly_20260315 ...] [--state-dir data/pipeline_state] [--out docs/revision/checkpoints_in_batch_mode.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.synthesis.run_health import assess_run, load_run_inputs, render_checkpoint_markdown  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", action="append", required=True)
    p.add_argument("--state-dir", default="data/pipeline_state")
    p.add_argument("--reports-root", default="data/reports")
    p.add_argument("--out", default="docs/revision/checkpoints_in_batch_mode.md")
    args = p.parse_args(argv)

    assessments = []
    for run_id in args.run_id:
        inputs = load_run_inputs(run_id, Path(args.state_dir), Path(args.reports_root) / run_id)
        assessments.append(assess_run(run_id, **inputs))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_checkpoint_markdown(assessments), encoding="utf-8")
    print(f"wrote {out} ({len(assessments)} run(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
