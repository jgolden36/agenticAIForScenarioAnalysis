#!/usr/bin/env python3
"""Regenerate every revision artefact under docs/revision from a saved run.

One command for the rebuttal: builds the coverage ledger, run-specific
model inventory, synthesis fidelity audit, anchor-only comparison,
checkpoint report, coverage facts, pycge replay, effort metrics, software
versions, model licenses, the deterministic analyst baseline (optional,
``--baseline``) and its comparison with the LLM run.

Each step calls the generator's ``main()`` in-process; a failing step is
reported and the others still run.

Usage::

    python scripts/revision/build_all.py --run-id 20260504_222710 --report-dir data/20260504_222710 \
        [--state-dir data/pipeline_state] [--baseline configs/baselines/hormuz_2026_analyst.yaml] \
        [--baseline-run-id baseline_analyst] [--out-dir docs/revision]
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _step(name: str, fn: Callable[[], Any], results: list[dict[str, Any]]) -> None:
    try:
        rc = fn()
        results.append({"step": name, "ok": rc in (0, None), "return": rc})
    except Exception as exc:  # noqa: BLE001 - keep going, report at the end
        results.append({"step": name, "ok": False, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", required=True)
    p.add_argument("--report-dir", required=True, help="Report directory of the LLM run (csv/, synthesis.json).")
    p.add_argument("--state-dir", default="data/pipeline_state")
    p.add_argument("--baseline", default=None, help="Baseline YAML; when given, the deterministic baseline is (re)run.")
    p.add_argument("--baseline-run-id", default="baseline_analyst")
    p.add_argument("--baseline-output-root", default=None, help="Default: repository root.")
    p.add_argument("--out-dir", default="docs/revision")
    p.add_argument("--pip-freeze", default=None)
    args = p.parse_args(argv)

    repo = Path(__file__).resolve().parents[2]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_dir = Path(args.report_dir)
    state_dir = Path(args.state_dir)
    has_state = any(state_dir.glob(f"{args.run_id}_*.json")) if state_dir.exists() else False
    source_args = ["--run-id", args.run_id] + (["--state-dir", str(state_dir)] if has_state else ["--from-report-dir", str(report_dir)])
    results: list[dict[str, Any]] = []

    from slurm.scripts.build_coverage_ledger import main as ledger_main
    from slurm.scripts.build_model_inventory import main as inventory_main
    from slurm.scripts.run_fidelity_audit import main as fidelity_main
    from scripts.revision.anchor_comparison import main as anchor_main
    from scripts.revision.checkpoint_report import main as checkpoint_main
    from scripts.revision.coverage_facts import main as facts_main
    from scripts.revision.replay_pycge_scenario_a import main as replay_main
    from scripts.revision.effort_metrics import main as effort_main
    from scripts.revision.software_versions import main as versions_main
    from scripts.revision.model_licenses import main as licenses_main

    ledger_dir = out / "coverage" / args.run_id
    _step("coverage_ledger", lambda: ledger_main(source_args + ["--out-dir", str(ledger_dir)]), results)
    _step("model_inventory", lambda: inventory_main(source_args + ["--out-dir", str(out)]), results)
    _step("fidelity_audit", lambda: fidelity_main(source_args + ["--out-dir", str(out / "fidelity" / args.run_id)]), results)
    _step("anchor_comparison", lambda: anchor_main(["--report-dir", str(report_dir), "--run-id", args.run_id, "--out-dir", str(out)]), results)
    _step("checkpoint_report", lambda: checkpoint_main(["--run-id", args.run_id, "--state-dir", str(state_dir),
                                                        "--reports-root", str(report_dir.parent), "--out", str(out / "checkpoints_in_batch_mode.md")]), results)
    ledger_csv = ledger_dir / "coverage_ledger.csv"
    _step("coverage_facts", lambda: facts_main(["--ledger", str(ledger_csv), "--run-id", args.run_id, "--out-dir", str(out)]), results)
    _step("pycge_replay", lambda: replay_main(["--report-dir", str(report_dir), "--out-dir", str(out)]), results)
    _step("effort_metrics", lambda: effort_main(["--out-dir", str(out)]), results)
    versions_args = ["--run-id", args.run_id, "--state-dir", str(state_dir), "--out-dir", str(out)]
    if args.pip_freeze:
        versions_args += ["--pip-freeze", args.pip_freeze]
    _step("software_versions", lambda: versions_main(versions_args), results)
    _step("model_licenses", lambda: licenses_main(["--out-dir", str(out)]), results)

    if args.baseline:
        from slurm.scripts.run_deterministic_baseline import main as baseline_main
        from scripts.revision.compare_runs import main as compare_main

        root = Path(args.baseline_output_root) if args.baseline_output_root else repo
        _step("deterministic_baseline", lambda: baseline_main(["--baseline", args.baseline, "--run-id", args.baseline_run_id,
                                                               "--output-root", str(root)]), results)
        baseline_report = root / "data" / "reports" / args.baseline_run_id
        _step("compare_runs", lambda: compare_main(["--a", str(report_dir), "--b", str(baseline_report), "--label-a", f"llm_{args.run_id}",
                                                    "--label-b", args.baseline_run_id, "--out-dir", str(out)]), results)
        _step("baseline_coverage_ledger", lambda: ledger_main(["--run-id", args.baseline_run_id, "--state-dir", str(root / "data" / "pipeline_state"),
                                                               "--out-dir", str(out / "coverage" / args.baseline_run_id), "--no-figure"]), results)

        def _copy_baseline_summary() -> int:
            # data/reports is gitignored; keep the small, citable parts of the
            # baseline run next to the comparison it feeds.
            import shutil

            dest = out / "baseline" / args.baseline_run_id
            dest.mkdir(parents=True, exist_ok=True)
            for rel in ("summary.json", "baseline_run.json", "fidelity.json", "synthesis.md",
                        "csv/model_status.csv", "csv/quantitative_results.csv", "csv/synthesis_outcomes.csv", "csv/consistency_flags.csv"):
                src = baseline_report / rel
                if src.exists():
                    shutil.copy2(src, dest / src.name)
            return 0

        _step("copy_baseline_summary", _copy_baseline_summary, results)

    (out / "build_all_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    for r in results:
        print(f"{'ok ' if r['ok'] else 'FAIL'} {r['step']}" + (f": {r.get('error')}" if r.get("error") else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
