"""Numeric fidelity audit of synthesis output against model outputs.

Module 4 hands the LLM a textual listing of every completed model's
outputs and asks for a structured ``ScopedSynthesis`` whose outcomes carry
``value`` (a string) and ``source_model_id``. Nothing in that flow
*verifies* that the string the LLM wrote back equals a number a model
produced. This module provides that check, both post hoc (over a saved
run) and inline (as a validator in ``synthesize_by_section``):

* :func:`canonicalize_model_id` repairs malformed source ids
  (``mpse_jl`` -> ``mpsge_jl``) and records that it did so.
* :func:`parse_value` extracts the numeric content of an outcome value
  string, including ``"{nrel: 126.39}"`` style per-model dicts.
* :func:`match_number` classifies a number against a model's outputs as
  ``exact``, ``rounded`` (within the printed precision), ``unit_scaled``
  (x100 or /100), ``matched_other_key`` (equals a different output of the
  same model), ``derived_arithmetic`` (difference or ratio of two
  outputs) or ``unmatched``.
* :func:`audit_prose` does the same for every numeric token in the
  narrative text of an outcome, against the cited models' outputs and
  their upstream-override records.
* :func:`audit_run` assembles a :class:`FidelityReport` (match rates,
  categorized failures, provenance completeness) for a whole run.
* :func:`audit_brief` checks a weekly brief's ``observed_indicators``
  against the fetched articles / EIA series.

The audit never changes a number. Inline, the validator either flags
mismatches as ``ConsistencyFlag`` records or drops the mismatched
outcomes (``on_mismatch: block``) so an unverifiable number never reaches
the report.
"""

from __future__ import annotations

import csv
import difflib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

# Order matters: later entries are "worse". The outcome-level category is
# the worst category among its parsed numbers.
CATEGORY_ORDER = (
    "non_numeric",
    "exact",
    "rounded",
    "unit_scaled",
    "matched_other_key",
    "derived_arithmetic",
    "source_unknown",
    "source_not_run",
    "unmatched",
)
MATCHED_CATEGORIES = {"exact", "rounded", "unit_scaled", "matched_other_key", "derived_arithmetic"}
STRICT_MATCHED_CATEGORIES = {"exact", "rounded", "unit_scaled"}
MISMATCH_CATEGORIES = {"source_unknown", "source_not_run", "unmatched"}

_NUMBER_RE = re.compile(r"(?<![A-Za-z_\d.])[-+−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?")
_LABELLED_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_\- ]*?)\s*[:=]\s*([-+−]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?)")
_PAREN_LABEL_RE = re.compile(r"\s*\(([A-Za-z_][A-Za-z0-9_\-]*)\)")
_YEAR_MIN, _YEAR_MAX = 1900, 2100
_MAX_PAIRWISE_SCALARS = 120


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", "").replace("−", "-"))
    except (TypeError, ValueError):
        return None


def _decimals(token: str) -> int:
    t = token.replace(",", "")
    if "e" in t.lower():
        return 6
    if "." in t:
        return len(t.split(".")[1])
    return 0


def _is_year_like(token: str, value: float) -> bool:
    return "." not in token and value.is_integer() and _YEAR_MIN <= value <= _YEAR_MAX and len(token.strip("-+")) == 4


def close_within_printed_precision(printed: float, candidate: float, decimals: int) -> bool:
    """True when ``candidate`` rounds to ``printed`` at the printed precision."""
    if not (math.isfinite(printed) and math.isfinite(candidate)):
        return False
    if math.isclose(printed, candidate, rel_tol=1e-9, abs_tol=1e-12):
        return True
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    return abs(printed - round(candidate, decimals)) <= tol or abs(printed - candidate) <= tol


def flatten_numeric(outputs: dict[str, Any], prefix: str = "") -> dict[str, float]:
    """``dotted.path -> float`` for every numeric leaf (lists get ``[i]``)."""
    flat: dict[str, float] = {}

    def _walk(obj: Any, path: str) -> None:
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            if math.isfinite(float(obj)):
                flat[path] = float(obj)
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{path}.{k}" if path else str(k))
            return
        if isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                _walk(v, f"{path}[{i}]")
            return
        if isinstance(obj, str):
            v = _to_float(obj) if _NUMBER_RE.fullmatch(obj.strip()) else None
            if v is not None:
                flat[path] = v

    _walk(outputs, prefix)
    return flat


# ---------------------------------------------------------------------------
# Source-id canonicalisation
# ---------------------------------------------------------------------------


def split_source_ids(raw: Any) -> list[str]:
    """Split a source string like ``"pycge, mpsge_jl"`` into parts."""
    if raw is None:
        return []
    text = str(raw).strip().strip("`'\"")
    if not text:
        return []
    parts = re.split(r"\s*(?:,|;|/|\band\b|&|\+)\s*", text)
    return [p.strip().strip("`'\"") for p in parts if p.strip()]


def canonicalize_model_id(raw: str, known_ids: Iterable[str]) -> tuple[str | None, str]:
    """Return ``(canonical_id, method)``; method is exact | normalized | fuzzy | none."""
    known = list(known_ids)
    if raw in known:
        return raw, "exact"
    norm = re.sub(r"[^a-z0-9]", "", raw.lower())
    by_norm = {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in known}
    if norm in by_norm:
        return by_norm[norm], "normalized"
    # Common LLM slips: dropped characters, swapped separators.
    candidates = difflib.get_close_matches(raw.lower(), [k.lower() for k in known], n=1, cutoff=0.72)
    if candidates:
        for k in known:
            if k.lower() == candidates[0]:
                return k, "fuzzy"
    candidates = difflib.get_close_matches(norm, list(by_norm), n=1, cutoff=0.72)
    if candidates:
        return by_norm[candidates[0]], "fuzzy"
    return None, "none"


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------


@dataclass
class ParsedNumber:
    value: float
    token: str
    decimals: int
    label: str | None = None  # e.g. the model id in "{nrel: 126.39}"


def parse_value(value: Any) -> list[ParsedNumber]:
    """Extract numbers (with optional labels) from an outcome ``value``."""
    if value is None:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [ParsedNumber(float(value), repr(value), 6 if isinstance(value, float) else 0)]
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            for p in parse_value(v):
                p.label = str(k)
                out.append(p)
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.extend(parse_value(v))
        return out
    text = str(value).strip()
    if not text:
        return []
    labelled = _LABELLED_RE.findall(text) if ("{" in text or ":" in text or "=" in text) else []
    out: list[ParsedNumber] = []
    if labelled:
        for label, token in labelled:
            v = _to_float(token)
            if v is None:
                continue
            out.append(ParsedNumber(v, token, _decimals(token), label.strip()))
        if out:
            return out
    for m in _NUMBER_RE.finditer(text):
        token = m.group(0)
        v = _to_float(token)
        if v is None:
            continue
        # "1.1869 (mpsge_jl)" style: a model label in parentheses right
        # after the number names the source for that number.
        label = None
        trailing = _PAREN_LABEL_RE.match(text, m.end())
        if trailing:
            label = trailing.group(1)
        out.append(ParsedNumber(v, token, _decimals(token), label))
    return out


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@dataclass
class NumberMatch:
    value: float
    token: str
    category: str
    matched_key: str | None = None
    matched_value: float | None = None
    relation: str | None = None
    source_model_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def match_number(
    number: ParsedNumber,
    variable: str | None,
    flat_outputs: dict[str, float],
) -> NumberMatch:
    """Classify ``number`` against one model's flattened outputs."""
    v, d = number.value, number.decimals
    # 1. The named variable itself.
    if variable:
        for key in (variable, f"{variable}[0]", f"{variable}.value"):
            if key in flat_outputs:
                cand = flat_outputs[key]
                if math.isclose(v, cand, rel_tol=1e-9, abs_tol=1e-12):
                    return NumberMatch(v, number.token, "exact", key, cand)
                if close_within_printed_precision(v, cand, d):
                    return NumberMatch(v, number.token, "rounded", key, cand, "rounded")
                for factor, rel in ((100.0, "x100"), (0.01, "/100")):
                    if close_within_printed_precision(v, cand * factor, d):
                        return NumberMatch(v, number.token, "unit_scaled", key, cand, rel)
        # Prefix match: variable names a dict/list whose leaves include v.
        for key, cand in flat_outputs.items():
            if key.startswith(variable + ".") or key.startswith(variable + "["):
                if close_within_printed_precision(v, cand, d):
                    cat = "exact" if math.isclose(v, cand, rel_tol=1e-9, abs_tol=1e-12) else "rounded"
                    return NumberMatch(v, number.token, cat, key, cand)
    # 2. Any other key of the same model.
    for key, cand in flat_outputs.items():
        if close_within_printed_precision(v, cand, d):
            return NumberMatch(v, number.token, "matched_other_key", key, cand)
    for key, cand in flat_outputs.items():
        for factor, rel in ((100.0, "x100"), (0.01, "/100")):
            if cand != 0 and close_within_printed_precision(v, cand * factor, d):
                return NumberMatch(v, number.token, "unit_scaled", key, cand, rel)
    # 3. Simple arithmetic of two scalars (bounded).
    scalars = [(k, c) for k, c in flat_outputs.items() if "[" not in k]
    if len(scalars) <= _MAX_PAIRWISE_SCALARS:
        for i, (ka, a) in enumerate(scalars):
            if close_within_printed_precision(v, abs(a), d) and a < 0:
                return NumberMatch(v, number.token, "derived_arithmetic", ka, a, "abs")
            for kb, b in scalars[i + 1:]:
                if close_within_printed_precision(v, a - b, d):
                    return NumberMatch(v, number.token, "derived_arithmetic", f"{ka} - {kb}", a - b, "difference")
                if close_within_printed_precision(v, b - a, d):
                    return NumberMatch(v, number.token, "derived_arithmetic", f"{kb} - {ka}", b - a, "difference")
                if b != 0 and close_within_printed_precision(v, (a / b - 1.0) * 100.0, d):
                    return NumberMatch(v, number.token, "derived_arithmetic", f"({ka} / {kb} - 1) x 100", (a / b - 1.0) * 100.0, "pct_change")
    return NumberMatch(v, number.token, "unmatched")


def worst_category(categories: Iterable[str]) -> str:
    cats = list(categories)
    if not cats:
        return "non_numeric"
    return max(cats, key=CATEGORY_ORDER.index)


# ---------------------------------------------------------------------------
# Outcome-level audit
# ---------------------------------------------------------------------------


@dataclass
class OutcomeAudit:
    scenario_id: str
    variable: str
    source_model_id_raw: str
    source_model_ids: list[str]
    source_canonicalization: dict[str, str]
    value_raw: Any
    category: str
    number_matches: list[NumberMatch]
    prose_tokens: int = 0
    prose_matched: int = 0
    prose_unmatched: list[str] = field(default_factory=list)
    prose_relations: dict[str, int] = field(default_factory=dict)
    chain_complete: bool = False
    time_horizon: str = ""
    outcome_scope: str = ""

    @property
    def is_numeric(self) -> bool:
        return self.category != "non_numeric"

    @property
    def matched(self) -> bool:
        return self.category in MATCHED_CATEGORIES

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_numeric"] = self.is_numeric
        d["matched"] = self.matched
        return d


def _override_candidates(outputs: dict[str, Any]) -> dict[str, float]:
    """Numbers quoted from upstream-override records (llm value, computed, deviation)."""
    cands: dict[str, float] = {}
    for i, rec in enumerate(outputs.get("_upstream_overrides") or []):
        if not isinstance(rec, dict):
            continue
        for key in ("llm_value", "computed_value", "deviation_pct", "cross_source_deviation_pct"):
            v = rec.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cands[f"_upstream_overrides[{i}].{key}"] = float(v)
    return cands


def _prose_relation(v: float, c: float, d: int) -> str | None:
    """How a prose token ``v`` restates a candidate value ``c`` (or None)."""
    if close_within_printed_precision(v, c, d):
        return "exact"
    # Prose routinely drops the sign ("GDP declines by 0.04%").
    if close_within_printed_precision(abs(v), abs(c), d):
        return "sign_dropped"
    if c != 0 and close_within_printed_precision(abs(v), abs(c) * 100.0, d):
        return "x100"
    # A multiplier near 1 restated as a percent change ("18.69% higher" for 1.1869).
    if 0.2 < c < 5.0 and close_within_printed_precision(abs(v), abs(c - 1.0) * 100.0, d):
        return "multiplier_to_pct"
    return None


def audit_prose(
    texts: Iterable[str],
    candidate_pools: list[dict[str, float]],
    own_numbers: Iterable[float] = (),
) -> tuple[int, int, list[str], dict[str, int]]:
    """Count numeric tokens in prose and how many restate a candidate value.

    Returns ``(total, matched, unmatched_tokens, relation_counts)``; a token
    is matched when it equals a candidate exactly, at the printed precision,
    with the sign dropped, after a x100 unit change, or as the percent form
    of a multiplier. Four-digit years are ignored.
    """
    total = 0
    matched = 0
    unmatched: list[str] = []
    relations: Counter = Counter()
    own = list(own_numbers)
    for text in texts:
        if not text:
            continue
        for m in _NUMBER_RE.finditer(str(text)):
            token = m.group(0)
            v = _to_float(token)
            if v is None or _is_year_like(token, v):
                continue
            d = _decimals(token)
            total += 1
            relation: str | None = None
            for o in own:
                relation = _prose_relation(v, o, d)
                if relation:
                    break
            if relation is None:
                for pool in candidate_pools:
                    for c in pool.values():
                        relation = _prose_relation(v, c, d)
                        if relation:
                            break
                    if relation:
                        break
            if relation:
                matched += 1
                relations[relation] += 1
            else:
                unmatched.append(token)
    return total, matched, unmatched, dict(relations)


def audit_outcome(
    outcome: dict[str, Any],
    model_outputs: dict[str, dict[str, Any] | None],
    known_ids: Iterable[str],
    *,
    extra_candidates: dict[str, float] | None = None,
) -> OutcomeAudit:
    """Audit one synthesized outcome.

    Args:
        outcome: dict with ``scenario_id``, ``outcome_variable`` (or
            ``variable``), ``value``, ``source_model_id`` and optional prose
            fields (``narrative_summary`` / ``narrative``, ``reliability_note``,
            ``distribution_note``, ``uncertainty_note``).
        model_outputs: ``model_id -> outputs dict`` for models that completed
            in this scenario; ``None`` (or absent) means the model did not run.
        known_ids: every model id the pipeline knows (for canonicalisation).
    """
    known = list(known_ids)
    variable = str(outcome.get("outcome_variable") or outcome.get("variable") or "")
    raw_source = str(outcome.get("source_model_id") or "")
    canon: dict[str, str] = {}
    sources: list[str] = []
    for part in split_source_ids(raw_source):
        cid, method = canonicalize_model_id(part, known)
        if cid is not None:
            if method != "exact":
                canon[part] = cid
            sources.append(cid)
        else:
            canon[part] = ""
    sources = list(dict.fromkeys(sources))

    numbers = parse_value(outcome.get("value"))
    matches: list[NumberMatch] = []
    for n in numbers:
        targets = list(sources)
        if n.label:
            lid, _ = canonicalize_model_id(n.label, known)
            if lid is not None:
                targets = [lid] + [s for s in sources if s != lid]
        if not targets:
            matches.append(NumberMatch(n.value, n.token, "source_unknown"))
            continue
        best: NumberMatch | None = None
        for mid in targets:
            outputs = model_outputs.get(mid)
            if outputs is None:
                cand = NumberMatch(n.value, n.token, "source_not_run", source_model_id=mid)
            else:
                cand = match_number(n, variable, flatten_numeric(outputs))
                cand.source_model_id = mid
            if best is None or CATEGORY_ORDER.index(cand.category) < CATEGORY_ORDER.index(best.category):
                best = cand
            if best.category == "exact":
                break
        matches.append(best)  # type: ignore[arg-type]

    category = worst_category(m.category for m in matches) if matches else "non_numeric"
    if not numbers and not sources and raw_source:
        category = "non_numeric"

    pools = [flatten_numeric(model_outputs[s]) for s in sources if model_outputs.get(s) is not None]
    pools += [_override_candidates(model_outputs[s]) for s in sources if model_outputs.get(s) is not None]
    if extra_candidates:
        pools.append(dict(extra_candidates))
    prose_fields = ("narrative_summary", "narrative", "reliability_note", "distribution_note", "uncertainty_note")
    total, matched, unmatched, relations = audit_prose(
        [str(outcome.get(f) or "") for f in prose_fields], pools, own_numbers=[n.value for n in numbers]
    )
    chain_complete = bool(sources) and all(model_outputs.get(s) is not None for s in sources) and category in STRICT_MATCHED_CATEGORIES
    return OutcomeAudit(
        scenario_id=str(outcome.get("scenario_id") or ""),
        variable=variable,
        source_model_id_raw=raw_source,
        source_model_ids=sources,
        source_canonicalization=canon,
        value_raw=outcome.get("value"),
        category=category,
        number_matches=matches,
        prose_tokens=total,
        prose_matched=matched,
        prose_unmatched=unmatched,
        prose_relations=relations,
        chain_complete=chain_complete,
        time_horizon=str(outcome.get("time_horizon") or ""),
        outcome_scope=str(outcome.get("outcome_scope") or ""),
    )


# ---------------------------------------------------------------------------
# Run-level audit
# ---------------------------------------------------------------------------


@dataclass
class FidelityReport:
    run_id: str
    outcomes: list[OutcomeAudit]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "summary": self.summary, "outcomes": [o.to_dict() for o in self.outcomes]}


def summarize_audits(audits: list[OutcomeAudit]) -> dict[str, Any]:
    numeric = [a for a in audits if a.is_numeric]
    by_cat = Counter(a.category for a in audits)
    by_scenario: dict[str, dict[str, Any]] = {}
    for s in sorted({a.scenario_id for a in audits}):
        sa = [a for a in audits if a.scenario_id == s]
        sn = [a for a in sa if a.is_numeric]
        by_scenario[s] = {
            "outcomes": len(sa),
            "numeric": len(sn),
            "matched": sum(a.matched for a in sn),
            "strict_matched": sum(a.category in STRICT_MATCHED_CATEGORIES for a in sn),
            "by_category": dict(Counter(a.category for a in sa)),
        }
    prose_total = sum(a.prose_tokens for a in audits)
    prose_matched = sum(a.prose_matched for a in audits)
    prose_relations: Counter = Counter()
    for a in audits:
        prose_relations.update(a.prose_relations)
    return {
        "prose_relations": dict(prose_relations),
        "outcomes": len(audits),
        "numeric_outcomes": len(numeric),
        "matched": sum(a.matched for a in numeric),
        "strict_matched": sum(a.category in STRICT_MATCHED_CATEGORIES for a in numeric),
        "value_match_rate": round(sum(a.matched for a in numeric) / len(numeric), 4) if numeric else None,
        "strict_match_rate": round(sum(a.category in STRICT_MATCHED_CATEGORIES for a in numeric) / len(numeric), 4) if numeric else None,
        "by_category": dict(by_cat),
        "source_ids_canonicalized": sum(1 for a in audits if any(v for v in a.source_canonicalization.values())),
        "source_ids_unresolved": sum(1 for a in audits if any(v == "" for v in a.source_canonicalization.values())),
        "prose_numeric_tokens": prose_total,
        "prose_matched_tokens": prose_matched,
        "prose_match_rate": round(prose_matched / prose_total, 4) if prose_total else None,
        "provenance_complete": sum(a.chain_complete for a in numeric),
        "provenance_completeness_rate": round(sum(a.chain_complete for a in numeric) / len(numeric), 4) if numeric else None,
        "by_scenario": by_scenario,
    }


def audit_run(
    run_id: str,
    synthesis_results: list[dict[str, Any]],
    model_outputs_by_scenario: dict[str, dict[str, dict[str, Any] | None]],
    known_ids: Iterable[str],
    *,
    extra_candidates_by_scenario_model: dict[tuple[str, str], dict[str, float]] | None = None,
) -> FidelityReport:
    known = list(known_ids)
    extra = extra_candidates_by_scenario_model or {}
    audits: list[OutcomeAudit] = []
    for outcome in synthesis_results:
        sid = str(outcome.get("scenario_id") or "")
        outputs = model_outputs_by_scenario.get(sid, {})
        cands: dict[str, float] = {}
        for part in split_source_ids(outcome.get("source_model_id")):
            cid, _ = canonicalize_model_id(part, known)
            if cid:
                cands.update(extra.get((sid, cid), {}))
        audits.append(audit_outcome(outcome, outputs, known, extra_candidates=cands))
    return FidelityReport(run_id=run_id, outcomes=audits, summary=summarize_audits(audits))


# ---------------------------------------------------------------------------
# Section-level validator (inline use by synthesize_by_section)
# ---------------------------------------------------------------------------


def audit_section(
    scoped: Any,
    section_results: list[Any],
    known_ids: Iterable[str],
    scenario_id: str = "",
) -> list[OutcomeAudit]:
    """Audit a ``ScopedSynthesis`` against the ``ModelExecutionResult`` list it was built from."""
    model_outputs: dict[str, dict[str, Any] | None] = {}
    for r in section_results:
        status = getattr(r, "status", None)
        status_v = getattr(status, "value", status)
        model_outputs[r.model_id] = dict(r.outputs) if str(status_v) == "completed" else None
    audits = []
    for outcome in scoped.outcomes:
        audits.append(audit_outcome({
            "scenario_id": scenario_id,
            "variable": outcome.variable,
            "value": outcome.value,
            "source_model_id": outcome.source_model_id,
            "narrative": outcome.narrative,
            "reliability_note": outcome.reliability_note,
            "distribution_note": outcome.distribution_note,
            "uncertainty_note": outcome.uncertainty_note,
            "time_horizon": getattr(scoped.time_horizon, "value", scoped.time_horizon),
            "outcome_scope": getattr(scoped.outcome_scope, "value", scoped.outcome_scope),
        }, model_outputs, known_ids))
    return audits


def format_fidelity_feedback(mismatches: list[OutcomeAudit]) -> str:
    lines = [
        "The following outcomes in your previous answer could not be matched to any number in the model "
        "results above. Re-emit the section using ONLY values that appear verbatim in the model results, "
        "with the exact model id as source_model_id; drop any outcome you cannot source.",
    ]
    for a in mismatches:
        lines.append(f"- {a.variable}: value {a.value_raw!r} from source {a.source_model_id_raw!r} ({a.category})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Loaders for saved runs
# ---------------------------------------------------------------------------


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def model_outputs_from_state(state_dir: Path, run_id: str) -> dict[str, dict[str, dict[str, Any] | None]]:
    """``scenario -> model -> outputs (None if not completed)`` from state files."""
    out: dict[str, dict[str, dict[str, Any] | None]] = defaultdict(dict)
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sid, mid = str(rec.get("scenario_id")), str(rec.get("model_id"))
        if str(rec.get("status")).lower() == "completed":
            out[sid][mid] = rec.get("outputs") or {}
        else:
            out[sid].setdefault(mid, None)
    return dict(out)


def model_outputs_from_report_csv(csv_dir: Path) -> dict[str, dict[str, dict[str, Any] | None]]:
    """Reconstruct per-model outputs from Stage 5 CSVs (scalars + raw series/tables)."""
    out: dict[str, dict[str, dict[str, Any] | None]] = defaultdict(dict)
    for r in _read_csv(csv_dir / "model_status.csv"):
        sid, mid = r.get("scenario_id", ""), r.get("model_id", "")
        out[sid][mid] = {} if (r.get("status") or "").lower() == "completed" else None
    for r in _read_csv(csv_dir / "quantitative_results.csv"):
        if (r.get("is_numeric") or "").lower() != "true":
            continue
        sid, mid, key = r.get("scenario_id", ""), r.get("model_id", ""), r.get("output_key", "")
        v = _to_float(r.get("value_numeric") or "")
        if v is None:
            continue
        bucket = out[sid].get(mid)
        if bucket is None:
            bucket = {}
            out[sid][mid] = bucket
        bucket[key] = v
    raw_root = csv_dir / "raw"
    if raw_root.exists():
        for scenario_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
            sid = scenario_dir.name
            for path in sorted(scenario_dir.glob("*.csv")):
                stem = path.stem
                if "__" not in stem:
                    continue
                mid, _, rest = stem.partition("__")
                bucket = out[sid].get(mid)
                if bucket is None:
                    continue
                rows = _read_csv(path)
                if rest == "scalars":
                    continue
                if rest.endswith("__series"):
                    series = rest[: -len("__series")]
                    values = [_to_float(r.get("value", "")) for r in rows]
                    bucket[series] = [v for v in values if v is not None]
                else:
                    cols = rows[0].keys() if rows else []
                    label_col = next(iter(cols), None)
                    for r in rows:
                        label = r.get(label_col, "") if label_col else ""
                        for col, val in r.items():
                            v = _to_float(val or "")
                            if v is None:
                                continue
                            # The label column (e.g. a year) is itself a
                            # model output value; keep it addressable.
                            bucket[f"{rest}.{label}.{col}"] = v
    return dict(out)


def flag_candidates_from_synthesis(synthesis: dict[str, Any]) -> dict[tuple[str, str], dict[str, float]]:
    """Numbers quoted in consistency flags (thresholds, deviations) per (scenario, model)."""
    out: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for i, f in enumerate(synthesis.get("consistency_flags") or []):
        sid = str(f.get("scenario_id") or "")
        for mid_key in ("model_a_id", "model_b_id"):
            mid = str(f.get(mid_key) or "")
            for key in ("value_a", "value_b", "tolerance_pct", "deviation_pct"):
                v = f.get(key)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    out[(sid, mid)][f"flag[{i}].{key}"] = float(v)
                elif isinstance(v, str):
                    fv = _to_float(v)
                    if fv is not None:
                        out[(sid, mid)][f"flag[{i}].{key}"] = fv
    return dict(out)


# ---------------------------------------------------------------------------
# Weekly brief audit
# ---------------------------------------------------------------------------


def audit_brief(brief: dict[str, Any], articles: list[dict[str, Any]]) -> dict[str, Any]:
    """Match each observed indicator value in a weekly brief to the fetched sources."""
    haystack_numbers: list[float] = []
    for a in articles or []:
        for key in ("title", "description", "content"):
            text = a.get(key) or ""
            for m in _NUMBER_RE.finditer(str(text)):
                v = _to_float(m.group(0))
                if v is not None:
                    haystack_numbers.append(v)
        raw = a.get("raw")
        if isinstance(raw, (dict, list)):
            haystack_numbers.extend(flatten_numeric(raw if isinstance(raw, dict) else {"raw": raw}).values())
    results = []
    for ind in brief.get("observed_indicators") or []:
        v = ind.get("value")
        try:
            fv = float(v)
        except (TypeError, ValueError):
            results.append({"name": ind.get("name"), "value": v, "matched": False, "reason": "non_numeric"})
            continue
        d = 2 if not float(fv).is_integer() else 0
        hit = any(close_within_printed_precision(fv, h, d) for h in haystack_numbers)
        results.append({"name": ind.get("name"), "value": fv, "unit": ind.get("unit"), "source": ind.get("source"), "matched": hit})
    n = len(results)
    matched = sum(1 for r in results if r.get("matched"))
    return {
        "week_start": brief.get("week_start"),
        "indicators": n,
        "matched": matched,
        "match_rate": round(matched / n, 4) if n else None,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(report: FidelityReport) -> str:
    s = report.summary
    lines = [f"# Synthesis fidelity audit for run `{report.run_id}`", ""]
    lines += [
        f"- Synthesized outcomes: **{s['outcomes']}** ({s['numeric_outcomes']} numeric)",
        f"- Value match rate (any category): **{s['value_match_rate']}**; strict (exact / rounded / unit-scaled): **{s['strict_match_rate']}**",
        f"- Provenance-complete outcomes (sources ran, value strictly matched): **{s['provenance_complete']}** ({s['provenance_completeness_rate']})",
        f"- Prose numeric tokens matched: **{s['prose_matched_tokens']} / {s['prose_numeric_tokens']}** ({s['prose_match_rate']}); "
        f"how they restate the model value: {s.get('prose_relations')}",
        f"- Source ids repaired by canonicalisation: **{s['source_ids_canonicalized']}**; unresolved: **{s['source_ids_unresolved']}**",
        "",
        "## Outcomes by category",
        "",
        "| category | count | meaning |",
        "|---|---|---|",
    ]
    meaning = {
        "exact": "value equals the model output for the named variable",
        "rounded": "equals it at the printed precision",
        "unit_scaled": "equals it after a x100 or /100 unit change",
        "matched_other_key": "equals a different output of the cited model",
        "derived_arithmetic": "equals a difference, ratio or absolute value of two outputs",
        "source_unknown": "the cited source id could not be resolved to a model",
        "source_not_run": "the cited model did not complete in this scenario",
        "unmatched": "no model output matches the value",
        "non_numeric": "value carries no number",
    }
    for cat in CATEGORY_ORDER:
        if s["by_category"].get(cat):
            lines.append(f"| {cat} | {s['by_category'][cat]} | {meaning.get(cat, '')} |")
    lines += ["", "## By scenario", "", "| scenario | outcomes | numeric | matched | strict | categories |", "|---|---|---|---|---|---|"]
    for sid, info in s["by_scenario"].items():
        cats = ", ".join(f"{k}: {v}" for k, v in sorted(info["by_category"].items()))
        lines.append(f"| {sid} | {info['outcomes']} | {info['numeric']} | {info['matched']} | {info['strict_matched']} | {cats} |")
    problems = [a for a in report.outcomes if a.category in MISMATCH_CATEGORIES or a.source_canonicalization]
    if problems:
        lines += ["", "## Outcomes needing attention", "", "| scenario | variable | source (raw) | value | category | detail |", "|---|---|---|---|---|---|"]
        for a in problems[:200]:
            detail = []
            if a.source_canonicalization:
                detail.append("source id repaired: " + ", ".join(f"{k}->{v or '?'}" for k, v in a.source_canonicalization.items()))
            for m in a.number_matches:
                if m.category in MISMATCH_CATEGORIES:
                    detail.append(f"{m.token}: {m.category}")
            lines.append(f"| {a.scenario_id} | `{a.variable}` | `{a.source_model_id_raw}` | {str(a.value_raw)[:40]} | {a.category} | {'; '.join(detail)} |")
    unmatched_prose = [(a, t) for a in report.outcomes for t in a.prose_unmatched]
    if unmatched_prose:
        lines += ["", "## Numeric tokens in prose with no matching model output (first 100)", ""]
        for a, t in unmatched_prose[:100]:
            lines.append(f"- {a.scenario_id} / `{a.variable}` ({a.source_model_id_raw}): `{t}`")
    lines.append("")
    return "\n".join(lines)
