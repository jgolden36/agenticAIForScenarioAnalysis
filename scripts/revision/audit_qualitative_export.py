#!/usr/bin/env python3
"""Numeric audit of the Stage 5 per-model commentary (Reviewer 2, point 4; Reviewer 1, point 4).

``src.synthesis.fidelity`` audits the Module 4 synthesis. The Stage 5 export
(``qualitative/<scenario>.md``) has its own LLM pass that writes one commentary
per (scenario, model) and is outside that audit. This script checks every number
in those sections against the same model's recorded outputs in that scenario.

Relations come from ``fidelity._prose_relation``. ``x100`` is listed separately
because it is ambiguous: it is correct for a fraction written as a percent and
wrong for a value that is already a percent, so those rows need reading. A token
with no relation is not proof of error, since a section may also quote scenario
assumptions such as "closed for 5 days".

Usage::

    python scripts/revision/audit_qualitative_export.py --run-id 20260504_222710 \
        --qualitative-dir data/20260504_222710/qualitative --state-dir data/pipeline_state_may_filled \
        --out-dir docs/revision/runs/20260504_222710_filled
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.synthesis.fidelity import (  # noqa: E402
    _NUMBER_RE,
    _decimals,
    _is_year_like,
    _prose_relation,
    _to_float,
    flatten_numeric,
    model_outputs_from_state,
)

_SECTION_RE = re.compile(r"^## `(?P<model>[^`]+)`.*$", re.MULTILINE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def split_sections(text: str) -> dict[str, str]:
    """Commentary per model from one scenario file."""
    matches = list(_SECTION_RE.finditer(text))
    sections = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m["model"]] = text[m.end():end].strip()
    return sections


def audit_section(text: str, outputs: dict[str, float]) -> list[dict[str, Any]]:
    """One row per numeric token: its first relation to any output of the model."""
    rows = []
    for sentence in _SENTENCE_RE.split(text):
        for m in _NUMBER_RE.finditer(sentence):
            token = m.group(0)
            value = _to_float(token)
            if value is None or _is_year_like(token, value):
                continue
            decimals = _decimals(token)
            # Prefer the most faithful reading across all outputs.
            relations = {_prose_relation(value, c, decimals) for c in outputs.values()} - {None}
            relation = next((r for r in ("exact", "sign_dropped", "multiplier_to_pct", "x100") if r in relations), "unmatched")
            rows.append({"token": token, "relation": relation, "sentence": sentence.strip()[:300]})
    return rows


def audit_export(qualitative_dir: Path, outputs_by_scenario: dict[str, dict[str, dict[str, Any] | None]]) -> list[dict[str, Any]]:
    rows = []
    for scenario, by_model in sorted(outputs_by_scenario.items()):
        path = qualitative_dir / f"{scenario}.md"
        if not path.exists():
            continue
        for model, text in split_sections(path.read_text(encoding="utf-8")).items():
            outputs = by_model.get(model)
            flat = flatten_numeric(outputs) if outputs else {}
            rows += [{"scenario_id": scenario, "model_id": model, **row} for row in audit_section(text, flat)]
    return rows


def render(run_id: str, rows: list[dict[str, Any]]) -> str:
    counts = Counter(r["relation"] for r in rows)
    total = len(rows)
    lines = [f"# Stage 5 commentary audit for run `{run_id}`", "",
             f"{total} numeric tokens across {len({(r['scenario_id'], r['model_id']) for r in rows})} sections: {dict(counts)}.", "",
             "`x100` is correct for a fraction written as a percent and wrong for a value already in percent, so each row needs reading. "
             "`unmatched` means the number equals no output of that model; it may be a scenario assumption rather than an error.", "",
             "## By model", "", "| model | tokens | exact | sign dropped | multiplier as pct | x100 | unmatched |", "|---|---|---|---|---|---|---|"]
    for model in sorted({r["model_id"] for r in rows}):
        c = Counter(r["relation"] for r in rows if r["model_id"] == model)
        lines.append(f"| {model} | {sum(c.values())} | {c['exact']} | {c['sign_dropped']} | {c['multiplier_to_pct']} | {c['x100']} | {c['unmatched']} |")
    lines += ["", "## Tokens restating a value x100", "", "| scenario | model | token | sentence |", "|---|---|---|---|"]
    for r in rows:
        if r["relation"] == "x100":
            lines.append(f"| {r['scenario_id']} | {r['model_id']} | {r['token']} | {r['sentence'].replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-id", required=True)
    p.add_argument("--qualitative-dir", type=Path, required=True)
    p.add_argument("--state-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args(argv)

    rows = audit_export(args.qualitative_dir, model_outputs_from_state(args.state_dir, args.run_id))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"qualitative_audit_{args.run_id}"
    with (args.out_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["scenario_id", "model_id", "token", "relation", "sentence"])
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / f"{stem}.json").write_text(json.dumps({"run_id": args.run_id, "counts": Counter(r["relation"] for r in rows), "rows": rows}, indent=2), encoding="utf-8")
    (args.out_dir / f"{stem}.md").write_text(render(args.run_id, rows), encoding="utf-8")
    print(f"{len(rows)} tokens: {dict(Counter(r['relation'] for r in rows))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
