#!/usr/bin/env python3
"""Post-hoc numeric fidelity audit of a run's synthesis (Reviewer 2, point 4).

For every synthesized outcome the audit checks whether the value the LLM
wrote equals (exactly, at the printed precision, or after a x100 / /100
unit change) a number produced by the model it cites, repairs malformed
source ids, audits every numeric token in the narrative prose against the
cited models' outputs and override records, and reports provenance
completeness. See ``src/synthesis/fidelity.py`` for the rules.

Evidence sources (one of):

* ``--state-dir`` (default ``data/pipeline_state``): ``<run_id>_synthesis.json``
  and ``<run_id>_model_*.json``.
* ``--from-report-dir data/reports/<run_id>``: ``synthesis.json`` plus the
  Stage 5 CSVs (``csv/model_status.csv``, ``csv/quantitative_results.csv``,
  ``csv/raw/``). Works on the artefacts committed under ``data/<run_id>/``.

Weekly briefs can be audited with ``--brief data/news/<date>/brief.json
--articles data/news/<date>/articles.json`` (repeatable pairs).

Writes ``fidelity.{json,md}`` to ``--out-dir`` (default
``data/reports/<run_id>``) and copies the Markdown to ``--docs-dir`` when given.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import get_project_root, get_run_id, logger, state_dir  # noqa: E402
from src.synthesis.fidelity import (  # noqa: E402
    audit_brief,
    audit_run,
    flag_candidates_from_synthesis,
    model_outputs_from_report_csv,
    model_outputs_from_state,
    render_markdown,
)


def _known_ids() -> list[str]:
    try:
        from src.parameters.model_specs import ALL_MODEL_SPECS

        return list(ALL_MODEL_SPECS)
    except Exception:  # noqa: BLE001
        return []


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", default=None)
    p.add_argument("--state-dir", default=None)
    p.add_argument("--from-report-dir", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--brief", action="append", default=[], help="Weekly brief.json (repeatable; pair with --articles).")
    p.add_argument("--articles", action="append", default=[], help="articles.json matching each --brief.")
    args = p.parse_args(argv)

    run_id = args.run_id or get_run_id()
    root = get_project_root()
    known = _known_ids()

    if args.from_report_dir:
        report_dir = Path(args.from_report_dir)
        synthesis = _load_json(report_dir / "synthesis.json")
        outputs = model_outputs_from_report_csv(report_dir / "csv")
        evidence = f"report dir {report_dir}"
    else:
        sdir = Path(args.state_dir) if args.state_dir else state_dir()
        synthesis = _load_json(sdir / f"{run_id}_synthesis.json")
        outputs = model_outputs_from_state(sdir, run_id)
        evidence = f"state dir {sdir}"
    # Models known from the run but absent from the spec list (e.g. renamed ids).
    for by_model in outputs.values():
        for mid in by_model:
            if mid not in known:
                known.append(mid)

    report = audit_run(
        run_id,
        synthesis.get("synthesis_results") or [],
        outputs,
        known,
        extra_candidates_by_scenario_model=flag_candidates_from_synthesis(synthesis),
    )
    out_dir = Path(args.out_dir) if args.out_dir else root / "data" / "reports" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict()
    payload["evidence"] = evidence

    if args.brief:
        briefs = []
        for i, bpath in enumerate(args.brief):
            apath = args.articles[i] if i < len(args.articles) else None
            brief = _load_json(Path(bpath))
            articles = _load_json(Path(apath)) if apath else []
            if isinstance(articles, dict):
                articles = articles.get("articles", [])
            briefs.append(audit_brief(brief, articles))
        payload["weekly_briefs"] = briefs

    (out_dir / "fidelity.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md = render_markdown(report)
    if args.brief:
        md += "\n## Weekly briefs\n\n| week | indicators | matched to sources | rate |\n|---|---|---|---|\n"
        for b in payload["weekly_briefs"]:
            md += f"| {b['week_start']} | {b['indicators']} | {b['matched']} | {b['match_rate']} |\n"
    (out_dir / "fidelity.md").write_text(md, encoding="utf-8")
    if args.docs_dir:
        docs = Path(args.docs_dir)
        docs.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_dir / "fidelity.md", docs / f"fidelity_{run_id}.md")
        shutil.copy2(out_dir / "fidelity.json", docs / f"fidelity_{run_id}.json")

    s = report.summary
    logger.info(
        f"fidelity audit ({evidence}): {s['numeric_outcomes']} numeric outcomes, strict match rate "
        f"{s['strict_match_rate']}, any-match rate {s['value_match_rate']}, prose tokens matched "
        f"{s['prose_matched_tokens']}/{s['prose_numeric_tokens']}, sources repaired {s['source_ids_canonicalized']}"
    )
    logger.info(f"wrote {out_dir / 'fidelity.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
