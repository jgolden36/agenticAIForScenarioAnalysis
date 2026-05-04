#!/usr/bin/env python3
"""SLURM entry point for Stage 4b: Output Validation.

Walks every ``<run_id>_model_*.json`` file under
``data/pipeline_state/`` and applies the conservative per-output
sanity rules from ``configs/validation_rules.yaml``. Writes:

  data/pipeline_state/<run_id>_validation.json
  data/reports/<run_id>/validation.json
  data/reports/<run_id>/validation.md

The stage is best-effort: a non-zero exit does not propagate up
through the SLURM driver because Stage 4 (synthesis) owns the
canonical exit code. Operators read the validation report.

Exit codes:
  0 — validation completed; rule violations may still be present
      (they are reported, not exception-raising).
  1 — internal error (e.g. could not read state files).
  2 — completed but found at least one ERROR-severity finding, AND
      ``HORMUZ_VALIDATION_FAIL_ON_ERROR=1`` was set. Default behaviour
      is exit 0 even with errors so the driver continues into Stage 5.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (
    get_project_root,
    get_run_id,
    log_slurm_context,
    logger,
    save_state,
    state_dir,
)

from src.synthesis.validation import (
    DEFAULT_RULES_PATH,
    render_validation_markdown,
    validate_outputs,
)


def collect_model_results(run_id: str) -> list[dict]:
    """Gather all ``<run_id>_model_*.json`` files from the state dir."""
    pattern = str(state_dir() / f"{run_id}_model_*.json")
    results: list[dict] = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                results.append(json.load(f))
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.warning(f"Could not read model result {path}: {exc}")
    return results


def reports_dir(run_id: str) -> Path:
    d = get_project_root() / "data" / "reports" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--run-id",
        default=None,
        help="Pipeline run id (defaults to $HORMUZ_RUN_ID).",
    )
    p.add_argument(
        "--rules",
        default=None,
        help=(
            "Path to validation rules YAML "
            f"(defaults to {DEFAULT_RULES_PATH})."
        ),
    )
    p.add_argument(
        "--fail-on-error",
        action="store_true",
        help=(
            "Exit 2 when at least one ERROR-severity finding is "
            "produced. Default is exit 0 regardless of findings."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    log_slurm_context()
    run_id = args.run_id or get_run_id()

    logger.info(f"=== Stage 4b: Output Validation (run_id={run_id}) ===")

    model_results = collect_model_results(run_id)
    logger.info(
        f"Collected {len(model_results)} model result file(s) "
        f"for validation."
    )
    if not model_results:
        logger.warning(
            "No model result files found; validation will be a no-op."
        )

    report = validate_outputs(
        model_results,
        run_id=run_id,
        rules_path=args.rules,
    )

    state_payload = report.to_dict()
    save_state(run_id, "validation", state_payload)

    out = reports_dir(run_id)
    with open(out / "validation.json", "w") as f:
        json.dump(state_payload, f, indent=2, default=str)
    with open(out / "validation.md", "w") as f:
        f.write(render_validation_markdown(report))

    logger.info(
        f"Validation complete: {len(report.errors)} error(s), "
        f"{len(report.warnings)} warning(s) across "
        f"{report.models_checked} completed model run(s); "
        f"{report.rules_evaluated} rule evaluation(s)."
    )
    if report.rule_hits:
        logger.info(f"Rule hit counts: {report.rule_hits}")
    logger.info(f"Validation report: {out / 'validation.md'}")

    fail_on_error = args.fail_on_error or os.environ.get(
        "HORMUZ_VALIDATION_FAIL_ON_ERROR", ""
    ).lower() in ("1", "true", "yes")
    if fail_on_error and report.errors:
        logger.error(
            f"HORMUZ_VALIDATION_FAIL_ON_ERROR set and "
            f"{len(report.errors)} error finding(s) present; exiting 2."
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
