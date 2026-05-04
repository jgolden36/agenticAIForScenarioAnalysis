#!/usr/bin/env python3
"""SLURM stage 5 — Quantitative CSV + qualitative narrative export.

This script runs *after* Module 4 synthesis and produces two
families of human-friendly artefacts that complement the existing
``synthesis.json`` / per-scenario Markdown reports:

1. **Quantitative CSVs** under ``data/reports/<run_id>/csv/``
   - ``model_status.csv`` — one row per (scenario, model) with status,
     runtime, error message, and resource class. Useful for triage.
   - ``synthesis_outcomes.csv`` — flattened version of
     ``synthesis.synthesis_results`` (scenario × time horizon × scope ×
     variable → value, source model, narrative). The canonical
     "headline numbers" table for the run.
   - ``quantitative_results.csv`` — every scalar key from every
     completed model output, flattened to one row per
     (scenario, model, key). Numeric values cast to float when
     possible; everything else preserved as a string.
   - ``raw/<scenario>/<model>__scalars.csv`` — per-model wide table of
     scalar outputs (one row).
   - ``raw/<scenario>/<model>__<series>.csv`` — per-model long-form
     table for any output value that is a list of dicts (e.g.
     ``yearly_results``, ``segmented_results`` from
     ``energy_flux_gas_power``).
   - ``regional_outcomes_native.csv`` — every distributional record
     extracted from completed models (one row per
     scenario × model × output_key × native_region × value_label),
     gated by ``configs/distributional_outputs.yaml``.
   - ``regional_outcomes_unified.csv`` — same data rolled up to the
     unified region taxonomy via ``configs/region_crosswalk.yaml``.
   - ``sectoral_outcomes.csv`` — flattened sectoral records (PyCGE,
     MIRAGRODEP regional_sectoral, OG-Core sectoral paths).
   - ``synthesis_distributions.csv`` — long-form view of every
     ``regional_distribution`` and ``sectoral_distribution`` attached
     to a ``SynthesizedOutcome`` by Module 4.

2. **Qualitative narratives** under ``data/reports/<run_id>/qualitative/``
   - ``<scenario>.md`` — per-scenario qualitative report describing
     each model's outputs in plain English. When an LLM is reachable
     (vLLM sidecar / Anthropic / OpenAI per the usual
     ``PIPELINE_LLM_*`` env vars) we ask it for a short narrative
     paragraph per (scenario, model). When the LLM is unavailable we
     fall back to a deterministic template that lists the key numbers
     without interpretation. This keeps the script useful in offline
     reruns where no LLM provider is configured.
   - ``cross_scenario.md`` — one model-by-model section comparing how
     each model behaved across the four scenarios.
   - ``user_executive_summary.md`` — a **second** LLM inference pass
     (fresh client instance) that reads ``cross_scenario.md`` and writes
     an overview for the principal user / decision-maker. Disabled when
     ``--no-llm`` is set, when ``HORMUZ_EXPORT_EXEC_SUMMARY_LLM=0``, or
     when no provider is reachable — in those cases a short stub file
     points readers at ``cross_scenario.md``.

The script is idempotent: rerunning it overwrites the export folder
without touching any pipeline state. It is safe to invoke on a
historical ``HORMUZ_RUN_ID`` as a standalone CLI:

    python slurm/scripts/export_results.py --run-id 20260423_125906

Auto-disables LLM narratives with ``--no-llm`` (or by leaving
``PIPELINE_LLM_PROVIDER`` unset and not running a vLLM sidecar). A
failed LLM call for a given (scenario, model) just falls back to the
deterministic template; one bad model never aborts the export.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import traceback
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slurm.scripts.stage_utils import (  # noqa: E402
    get_project_root,
    get_run_id,
    log_slurm_context,
    logger,
    resolve_llm_kwargs,
    state_dir,
)


# --------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------


def reports_root(run_id: str) -> Path:
    return get_project_root() / "data" / "reports" / run_id


def csv_root(run_id: str) -> Path:
    d = reports_root(run_id) / "csv"
    d.mkdir(parents=True, exist_ok=True)
    (d / "raw").mkdir(parents=True, exist_ok=True)
    return d


def qualitative_root(run_id: str) -> Path:
    d = reports_root(run_id) / "qualitative"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------
# Loading run artefacts
# --------------------------------------------------------------------


def load_model_results(run_id: str) -> list[dict]:
    pattern = str(state_dir() / f"{run_id}_model_*.json")
    out: list[dict] = []
    for p in sorted(glob.glob(pattern)):
        try:
            with open(p) as f:
                out.append(json.load(f))
        except Exception as exc:
            logger.warning(f"could not read {p}: {exc}")
    return out


def load_synthesis(run_id: str) -> dict | None:
    """Prefer the report copy; fall back to the pipeline-state copy."""
    for cand in (
        reports_root(run_id) / "synthesis.json",
        state_dir() / f"{run_id}_synthesis.json",
    ):
        if cand.exists():
            try:
                with open(cand) as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"could not parse {cand}: {exc}")
    return None


def load_scenarios(run_id: str) -> list[dict]:
    """Best-effort scenario narratives so qualitative reports get labels."""
    p = state_dir() / f"{run_id}_scenarios.json"
    if not p.exists():
        return []
    try:
        with open(p) as f:
            data = json.load(f)
        return data.get("scenario_narratives", []) or []
    except Exception as exc:
        logger.warning(f"could not parse {p}: {exc}")
        return []


# --------------------------------------------------------------------
# CSV writers
# --------------------------------------------------------------------


def _is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None


def _coerce_value(v: Any) -> Any:
    """Best-effort cast to float for CSV; return original on failure."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return v
    return v


def _flatten_outputs_scalars(outputs: dict) -> dict[str, Any]:
    """Pick out the top-level scalar keys from a model output dict.

    Nested dicts get one level of dotted-key flattening for scalar
    leaves; lists and deeper nesting are left for the long-form CSVs.
    """
    flat: dict[str, Any] = {}
    for k, v in outputs.items():
        if _is_scalar(v):
            flat[k] = v
        elif isinstance(v, dict):
            for kk, vv in v.items():
                if _is_scalar(vv):
                    flat[f"{k}.{kk}"] = vv
    return flat


def _list_of_dicts_keys(values: list[Any]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for entry in values:
        if not isinstance(entry, dict):
            continue
        for k in entry.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return keys


def write_csv(path: Path, header: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_model_status_csv(run_id: str, model_results: list[dict]) -> Path:
    out = csv_root(run_id) / "model_status.csv"
    header = [
        "scenario_id",
        "model_id",
        "status",
        "resource_class",
        "node",
        "slurm_job_id",
        "task_id",
        "runtime_seconds",
        "started_at",
        "completed_at",
        "error_message",
    ]
    rows = [{k: r.get(k) for k in header} for r in model_results]
    write_csv(out, header, rows)
    logger.info(f"wrote {out}  ({len(rows)} rows)")
    return out


def write_synthesis_outcomes_csv(run_id: str, synthesis: dict | None) -> Path | None:
    if not synthesis:
        return None
    rows = synthesis.get("synthesis_results") or []
    if not rows:
        return None
    out = csv_root(run_id) / "synthesis_outcomes.csv"
    header = [
        "scenario_id",
        "time_horizon",
        "outcome_scope",
        "outcome_variable",
        "value",
        "source_model_id",
        "narrative_summary",
    ]
    write_csv(out, header, rows)
    logger.info(f"wrote {out}  ({len(rows)} rows)")
    return out


def write_consistency_flags_csv(run_id: str, synthesis: dict | None) -> Path | None:
    if not synthesis:
        return None
    flags = synthesis.get("consistency_flags") or []
    if not flags:
        return None
    out = csv_root(run_id) / "consistency_flags.csv"
    header_seen: list[str] = []
    seen: set[str] = set()
    for f in flags:
        for k in f.keys():
            if k not in seen:
                seen.add(k)
                header_seen.append(k)
    write_csv(out, header_seen, flags)
    logger.info(f"wrote {out}  ({len(flags)} rows)")
    return out


def _try_extract_regional(model_id: str, outputs: dict):
    """Best-effort import of the regional extractor.

    Returns a tuple ``(records, dispersion)`` of lists. When the
    distributional spec / crosswalk YAML is absent or the optional
    ``yaml`` package is missing, returns ``([], [])`` so the export
    falls back to today's behaviour.
    """
    try:
        from src.synthesis.regional import (  # noqa: WPS433
            dispersion_metrics,
            extract_regional_records,
        )
    except Exception as exc:
        logger.debug(f"regional extractor unavailable: {exc}")
        return [], []
    try:
        records = extract_regional_records(model_id, outputs or {})
        metrics = dispersion_metrics(records) if records else []
        return records, metrics
    except Exception as exc:
        logger.warning(f"regional extraction failed for {model_id}: {exc}")
        return [], []


def write_regional_outcomes_csvs(
    run_id: str, model_results: list[dict]
) -> tuple[Path | None, Path | None, dict[str, list]]:
    """Write the native and unified regional CSVs.

    Also returns the per-(scenario, model) dispersion metrics so the
    qualitative narrative pass can surface them in the LLM prompt.

    Returns ``(native_path, unified_path, dispersion_by_scenario_model)``.
    """
    try:
        from src.synthesis.regional import aggregate_to_unified  # noqa: WPS433
    except Exception as exc:
        logger.debug(f"regional aggregation unavailable: {exc}")
        return None, None, {}

    native_rows: list[dict] = []
    unified_rows: list[dict] = []
    dispersion_by_key: dict[str, list] = {}

    for r in model_results:
        if r.get("status") != "completed":
            continue
        scenario = r.get("scenario_id") or "unknown_scenario"
        model = r.get("model_id") or "unknown_model"
        outputs = r.get("outputs") or {}
        records, metrics = _try_extract_regional(model, outputs)
        if not records:
            continue
        for rec in records:
            native_rows.append({
                "scenario_id": scenario,
                "model_id": rec.model_id,
                "output_key": rec.output_key,
                "native_region": rec.native_region,
                "unified_region": rec.unified_region,
                "sector": rec.sector or "",
                "value_label": rec.value_label,
                "value": rec.value,
            })
        unified = aggregate_to_unified(records)
        for (model_id, output_key, value_label), region_vals in unified.items():
            for unified_region, value in region_vals.items():
                unified_rows.append({
                    "scenario_id": scenario,
                    "model_id": model_id,
                    "output_key": output_key,
                    "unified_region": unified_region,
                    "value_label": value_label,
                    "value": value,
                })
        if metrics:
            dispersion_by_key[f"{scenario}::{model}"] = metrics

    native_path = unified_path = None
    if native_rows:
        native_path = csv_root(run_id) / "regional_outcomes_native.csv"
        write_csv(
            native_path,
            ["scenario_id", "model_id", "output_key", "native_region",
             "unified_region", "sector", "value_label", "value"],
            native_rows,
        )
        logger.info(f"wrote {native_path}  ({len(native_rows)} rows)")
    if unified_rows:
        unified_path = csv_root(run_id) / "regional_outcomes_unified.csv"
        write_csv(
            unified_path,
            ["scenario_id", "model_id", "output_key",
             "unified_region", "value_label", "value"],
            unified_rows,
        )
        logger.info(f"wrote {unified_path}  ({len(unified_rows)} rows)")
    return native_path, unified_path, dispersion_by_key


def write_sectoral_outcomes_csv(
    run_id: str, model_results: list[dict]
) -> Path | None:
    sectoral_rows: list[dict] = []
    for r in model_results:
        if r.get("status") != "completed":
            continue
        scenario = r.get("scenario_id") or "unknown_scenario"
        model = r.get("model_id") or "unknown_model"
        outputs = r.get("outputs") or {}
        records, _ = _try_extract_regional(model, outputs)
        for rec in records:
            if not rec.sector:
                continue
            sectoral_rows.append({
                "scenario_id": scenario,
                "model_id": rec.model_id,
                "output_key": rec.output_key,
                "sector": rec.sector,
                "native_region": rec.native_region,
                "unified_region": rec.unified_region,
                "value_label": rec.value_label,
                "value": rec.value,
            })
    if not sectoral_rows:
        return None
    out = csv_root(run_id) / "sectoral_outcomes.csv"
    write_csv(
        out,
        ["scenario_id", "model_id", "output_key", "sector",
         "native_region", "unified_region", "value_label", "value"],
        sectoral_rows,
    )
    logger.info(f"wrote {out}  ({len(sectoral_rows)} rows)")
    return out


def write_synthesis_distributions_csv(
    run_id: str, synthesis: dict | None
) -> Path | None:
    """Flatten ``regional_distribution`` and ``sectoral_distribution`` from
    every ``SynthesizedOutcome`` in the synthesis report.

    The synthesizer pre-populates these dicts from upstream model
    outputs; this CSV is the analyst-friendly cross-tab of those
    distributions, indexed by scenario × time-horizon × scope × variable.
    """
    if not synthesis:
        return None
    rows: list[dict] = []
    for scen in synthesis.get("scenarios") or []:
        scenario_id = scen.get("scenario_id") or scen.get("id") or "unknown"
        for section in scen.get("sections") or []:
            time_horizon = section.get("time_horizon") or "unknown"
            outcome_scope = section.get("outcome_scope") or "unknown"
            for outcome in section.get("outcomes") or []:
                regional = outcome.get("regional_distribution") or {}
                sectoral = outcome.get("sectoral_distribution") or {}
                if not regional and not sectoral:
                    continue
                base = {
                    "scenario_id": scenario_id,
                    "time_horizon": time_horizon,
                    "outcome_scope": outcome_scope,
                    "outcome_variable": outcome.get("variable", ""),
                    "source_model_id": outcome.get("source_model_id", ""),
                    "distribution_note": outcome.get("distribution_note", ""),
                }
                for region, value in regional.items():
                    rows.append({
                        **base,
                        "dimension": "regional",
                        "key": region,
                        "value": value,
                    })
                for sector, value in sectoral.items():
                    rows.append({
                        **base,
                        "dimension": "sectoral",
                        "key": sector,
                        "value": value,
                    })
    if not rows:
        return None
    out = csv_root(run_id) / "synthesis_distributions.csv"
    write_csv(
        out,
        ["scenario_id", "time_horizon", "outcome_scope", "outcome_variable",
         "source_model_id", "dimension", "key", "value", "distribution_note"],
        rows,
    )
    logger.info(f"wrote {out}  ({len(rows)} rows)")
    return out


def write_quantitative_results_csv(
    run_id: str, model_results: list[dict]
) -> Path:
    """Long-form table of every scalar output across every completed model."""
    out = csv_root(run_id) / "quantitative_results.csv"
    header = [
        "scenario_id",
        "model_id",
        "output_key",
        "value_numeric",
        "value_raw",
        "is_numeric",
    ]
    rows: list[dict] = []
    for r in model_results:
        if r.get("status") != "completed":
            continue
        outputs = r.get("outputs") or {}
        scalars = _flatten_outputs_scalars(outputs)
        for k, v in scalars.items():
            coerced = _coerce_value(v)
            is_num = isinstance(coerced, (int, float)) and not isinstance(coerced, bool)
            rows.append({
                "scenario_id": r.get("scenario_id"),
                "model_id": r.get("model_id"),
                "output_key": k,
                "value_numeric": coerced if is_num else "",
                "value_raw": v,
                "is_numeric": "true" if is_num else "false",
            })
    write_csv(out, header, rows)
    logger.info(f"wrote {out}  ({len(rows)} rows)")
    return out


def write_per_model_raw_csvs(run_id: str, model_results: list[dict]) -> int:
    """One scalar CSV + one CSV per series per (scenario, model).

    Series detection covers three shapes:

    * ``list[dict]`` — long-form rows (e.g. ``yearly_results`` from
      ``energy_flux_gas_power``). Written verbatim.
    * ``list[int|float]`` — bare numeric path (e.g.
      ``brent_price_path_usd_per_bbl`` from ``poles_jrc``). Written
      with a ``period,value`` schema so Stage 6 can plot it as a real
      time series.
    * ``dict[str -> int|float]`` whose keys look like time labels
      (years, year ranges, "year_1"/"y1"/"month_3", or pure ints) —
      written with ``period,value`` so e.g. ``gdp_pct_change_path``
      keyed by 2026..2050 reaches Stage 6 too.

    Underscore-prefixed keys are skipped — they are adapter
    bookkeeping (``_upstream_overrides``, ``_calibration_sources``,
    ``_inputs``) rather than analytical outputs.

    Returns the number of CSV files written.
    """
    written = 0
    base = csv_root(run_id) / "raw"
    for r in model_results:
        if r.get("status") != "completed":
            continue
        scenario = r.get("scenario_id") or "unknown_scenario"
        model = r.get("model_id") or "unknown_model"
        outputs = r.get("outputs") or {}
        if not outputs:
            continue

        scen_dir = base / scenario
        scen_dir.mkdir(parents=True, exist_ok=True)

        scalars = _flatten_outputs_scalars(outputs)
        if scalars:
            scalar_path = scen_dir / f"{model}__scalars.csv"
            write_csv(scalar_path, list(scalars.keys()), [scalars])
            written += 1

        for key, value in outputs.items():
            if not isinstance(key, str) or key.startswith("_"):
                continue
            if isinstance(value, list) and value and all(isinstance(e, dict) for e in value):
                cols = _list_of_dicts_keys(value)
                if not cols:
                    continue
                long_path = scen_dir / f"{model}__{key}.csv"
                write_csv(long_path, cols, value)
                written += 1
            elif (
                isinstance(value, list)
                and value
                and all(isinstance(e, (int, float)) and not isinstance(e, bool) for e in value)
            ):
                rows = [{"period": i, "value": float(v)} for i, v in enumerate(value)]
                long_path = scen_dir / f"{model}__{key}__series.csv"
                write_csv(long_path, ["period", "value"], rows)
                written += 1
            elif (
                isinstance(value, dict)
                and value
                and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in value.values()
                )
                and _looks_like_time_keyed_dict(value)
            ):
                rows = [
                    {"period": str(k), "value": float(v)}
                    for k, v in value.items()
                ]
                long_path = scen_dir / f"{model}__{key}__series.csv"
                write_csv(long_path, ["period", "value"], rows)
                written += 1
    logger.info(f"wrote {written} per-model raw CSV file(s) under {base}")
    return written


_TIME_KEY_HINTS = ("year", "yr", "y", "period", "month", "mo", "step", "horizon", "t")


def _looks_like_time_keyed_dict(d: dict) -> bool:
    """Heuristic: does a ``dict[str, number]`` look like a time series?

    True when every key parses as an int (e.g. 2026, 2030, 1, 5) or
    starts with a recognised time-axis hint (e.g. ``year_1``, ``y2030``,
    ``month_3``). Otherwise False — sectoral / categorical dicts like
    ``{"agriculture": -0.1, "industry": -0.2}`` are not time series.
    """
    if not d:
        return False
    int_like = 0
    hinted = 0
    for k in d.keys():
        s = str(k).strip().lower()
        try:
            int(s)
            int_like += 1
            continue
        except ValueError:
            pass
        for h in _TIME_KEY_HINTS:
            if s.startswith(h) or s.startswith(h + "_") or s.startswith(h + "-"):
                hinted += 1
                break
    n = len(d)
    # All keys must look time-like; we don't want to misclassify a
    # mixed dict.
    return (int_like + hinted) == n


# --------------------------------------------------------------------
# Qualitative narrative generation
# --------------------------------------------------------------------


_QUAL_PROMPT = """You are a domain analyst summarising quantitative model output \
for a chokepoint-crisis scenario report.

Scenario: {scenario_label} ({scenario_id})
Scenario description (narrative excerpt):
{scenario_brief}

Model: {model_id}
Model commodity system: {commodity_system}
Quantitative outputs (JSON):
{outputs_json}

Regional dispersion summary (pre-computed from the same outputs, rolled up to the \
unified region taxonomy {{US, CHN, IND, EU, MENA_GCC, MENA_OTHER, SSA, LAC, ROW, GLOBAL}}):
{regional_summary}

Write 2-4 short paragraphs (plain prose, no headers, no bullet points, no JSON, \
no fences) explaining what these numbers imply for the {scenario_label} scenario. \
Cover:
  - the headline magnitudes the model produced;
  - what they likely mean for the corresponding commodity system;
  - **regional / sectoral asymmetries**: when the regional dispersion summary above is \
non-empty, explicitly call out which regions or sectors are hit hardest and which are \
relatively insulated, and (where possible) explain why the scenario assumptions drive \
that pattern;
  - any caveats a reader should keep in mind (e.g. analytical-MVP outputs should be read \
as order-of-magnitude indicators).

Do not invent numbers that are not in the JSON or the regional dispersion summary. If \
outputs are sparse, say so.
"""

_EXEC_SUMMARY_PROMPT = """You are briefing a senior decision-maker who did not execute \
the modelling pipeline. They need a readable overview of what the domain models imply \
when taken together.

Below is Markdown that reorganises qualitative narratives **by model**, with each model's \
paragraphs repeated under every scenario in which that model produced output. Treat this \
as the only evidence base — do not invent quantitative claims or causal mechanisms that \
are not supported by the text.

Run ID: `{run_id}`

--- begin source material ---

{model_summaries_md}

--- end source material ---

Write an executive summary for the main user using **Markdown** with exactly these \
top-level sections (use `##` headings, no `#` title):

## Overview
## How scenarios differ (what shifts across the narrative set)
## Robust vs scenario-sensitive signals across models
## Risks, caveats, and limits of what was simulated
## What to read or verify next

Keep the tone concise and operational (roughly 600–900 words total unless the source \
material is very sparse). If the source is empty or nearly empty, say so honestly and \
avoid filler.
"""


def _llm_available() -> bool:
    """Heuristic: an LLM is reachable if a base URL or a cloud key is set."""
    if os.environ.get("PIPELINE_LLM_BASE_URL"):
        return True
    provider = (os.environ.get("PIPELINE_LLM_PROVIDER") or "").lower()
    if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        return True
    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        return True
    if provider == "bedrock":
        return True
    return False


def _try_get_llm():
    """Best-effort LLM construction using the same env precedence as
    other stages. Returns None on any failure so the caller falls back
    to deterministic templates without crashing the export."""
    try:
        from src.common.llm import get_llm  # noqa: WPS433
        from src.pipeline.config import PipelineConfig

        try:
            from slurm.scripts.stage_utils import get_pipeline_config_path  # noqa: WPS433
            import yaml  # noqa: WPS433

            cfg_path = get_pipeline_config_path()
            if cfg_path.exists():
                with open(cfg_path) as f:
                    raw = yaml.safe_load(f) or {}
                config = PipelineConfig(**raw)
            else:
                config = PipelineConfig()
        except Exception:
            config = PipelineConfig()

        kwargs = resolve_llm_kwargs(config)
        return get_llm(**kwargs)
    except Exception as exc:
        logger.warning(f"LLM unavailable for qualitative export: {exc}")
        return None


def _try_get_llm_exec_summary():
    """Construct a **fresh** LLM client for the executive-summary pass.

    Intentionally separate from :func:`_try_get_llm` so this stage performs a distinct
    inference round (new chat completion chain) after per-model narratives are written.
    Uses the same ``PIPELINE_LLM_*`` / YAML resolution path as the rest of the pipeline.
    """
    return _try_get_llm()


def _llm_exec_summary(
    llm, run_id: str, model_summaries_md: str
) -> str | None:
    """Single completion for the user-facing executive overview."""
    try:
        from langchain_core.prompts import PromptTemplate  # noqa: WPS433

        prompt = PromptTemplate.from_template(_EXEC_SUMMARY_PROMPT)
        chain = prompt | llm
        msg = chain.invoke({"run_id": run_id, "model_summaries_md": model_summaries_md})
        text = getattr(msg, "content", None) or str(msg)
        return text.strip()
    except Exception as exc:
        logger.warning(f"LLM executive summary generation failed: {exc}")
        return None


def write_user_executive_summary(
    run_id: str,
    exec_summary_llm_enabled: bool,
) -> None:
    """Write ``qualitative/user_executive_summary.md`` from ``cross_scenario.md``.

    This runs **after** :func:`write_qualitative_reports` so the cross-model Markdown
    artefact already exists on disk.
    """
    qual_dir = qualitative_root(run_id)
    cross_path = qual_dir / "cross_scenario.md"
    out_path = qual_dir / "user_executive_summary.md"

    if not cross_path.is_file():
        logger.warning(
            f"No {cross_path.name} found; skipping user executive summary."
        )
        stub = (
            "# Executive overview\n\n"
            f"`{cross_path.name}` was not found for run `{run_id}`. "
            "Regenerate Stage 5 export after qualitative narratives exist.\n"
        )
        out_path.write_text(stub, encoding="utf-8")
        logger.info(f"wrote {out_path} (stub — missing cross_scenario)")
        return

    bundle = cross_path.read_text(encoding="utf-8")
    try:
        from src.common.context_budget import (  # noqa: WPS433
            get_prompt_budget_tokens,
            truncate_to_budget,
        )

        budget = max(1024, int(get_prompt_budget_tokens() * 85 / 100))
        bundle = truncate_to_budget(bundle, budget)
    except Exception:
        if len(bundle) > 120_000:
            bundle = bundle[:120_000] + "\n\n... [truncated for prompt]\n"

    if not exec_summary_llm_enabled or not _llm_available():
        stub = (
            "# Executive overview\n\n"
            "An LLM-generated executive summary was not produced "
            "(export used `--no-llm` / `--no-exec-summary`, "
            "`HORMUZ_EXPORT_EXEC_SUMMARY_LLM=0`, "
            "or no LLM provider is configured). "
            "See [`cross_scenario.md`](cross_scenario.md) for model-by-model narratives "
            "across scenarios.\n"
        )
        out_path.write_text(stub, encoding="utf-8")
        logger.info(f"wrote {out_path} (stub — LLM disabled or unavailable)")
        return

    llm = _try_get_llm_exec_summary()
    if llm is None:
        stub = (
            "# Executive overview\n\n"
            "The executive-summary LLM client could not be initialised. "
            "See [`cross_scenario.md`](cross_scenario.md).\n"
        )
        out_path.write_text(stub, encoding="utf-8")
        logger.info(f"wrote {out_path} (stub — LLM init failed)")
        return

    body = _llm_exec_summary(llm, run_id, bundle)
    if not body:
        stub = (
            "# Executive overview\n\n"
            "The executive-summary LLM call did not return usable text. "
            "See [`cross_scenario.md`](cross_scenario.md).\n"
        )
        out_path.write_text(stub, encoding="utf-8")
        logger.info(f"wrote {out_path} (stub — empty LLM response)")
        return

    header = (
        f"<!-- Run `{run_id}` — generated by a dedicated executive-summary LLM pass "
        f"after per-model qualitative narratives. Source: cross_scenario.md -->\n\n"
    )
    out_path.write_text(header + body + "\n", encoding="utf-8")
    logger.info(f"wrote {out_path}")


def _commodity_system_for(model_id: str) -> str:
    """Best-effort lookup so the prompt has a hint of context.

    Falls back to ``"unknown"`` rather than throwing if the registry
    can't be built (e.g. missing optional dependencies on a thin
    standalone-export environment).
    """
    try:
        from src.models.registry import build_default_registry  # noqa: WPS433

        reg = build_default_registry()
        adapter = reg.get(model_id)
        if adapter is not None:
            return adapter.commodity_system.value
    except Exception:
        pass
    return "unknown"


def _scenario_brief(narrative: dict | None) -> str:
    if not narrative:
        return "(scenario narrative unavailable)"
    text = narrative.get("narrative") or ""
    if len(text) > 1500:
        text = text[: 1500].rsplit(" ", 1)[0] + "..."
    return text or "(scenario narrative unavailable)"


def _regional_summary_for(model_id: str, outputs: dict) -> str:
    """Build the per-(scenario, model) regional dispersion summary that
    is interpolated into the qualitative LLM prompt. Falls back to the
    sentinel ``"(no regional dispersion detected for this model)"`` when
    no records / no spec.
    """
    try:
        from src.synthesis.regional import (  # noqa: WPS433
            dispersion_metrics,
            extract_regional_records,
            render_dispersion_summary,
        )
    except Exception:
        return "(regional extractor unavailable in this environment)"
    try:
        records = extract_regional_records(model_id, outputs or {})
        if not records:
            return "(no regional dispersion detected for this model)"
        return render_dispersion_summary(dispersion_metrics(records))
    except Exception as exc:
        return f"(regional summary unavailable: {exc})"


def _deterministic_qualitative(
    model_id: str,
    outputs: dict,
    commodity_system: str,
) -> str:
    """Plain-English fallback when no LLM is available.

    Lists scalar outputs in a single short paragraph; mentions the
    presence of any time series without inventing interpretation.
    """
    scalars = _flatten_outputs_scalars(outputs)
    series_keys = [
        k for k, v in outputs.items()
        if isinstance(v, list) and v and all(isinstance(e, dict) for e in v)
    ]
    parts: list[str] = []
    parts.append(
        f"Model `{model_id}` (commodity system: {commodity_system}) reported "
        f"{len(scalars)} scalar output(s) and {len(series_keys)} time-series block(s) "
        f"under this scenario."
    )
    if scalars:
        sample = list(scalars.items())[:8]
        kvs = ", ".join(f"{k} = {v}" for k, v in sample)
        more = "" if len(scalars) <= 8 else f" (and {len(scalars) - 8} more)"
        parts.append(f"Headline scalars: {kvs}{more}.")
    if series_keys:
        parts.append(
            "Time-series outputs available: "
            + ", ".join(f"`{k}`" for k in series_keys)
            + ". See the corresponding CSV under csv/raw/ for the full table."
        )
    regional = _regional_summary_for(model_id, outputs)
    if regional and not regional.startswith("("):
        parts.append("Regional dispersion (unified taxonomy):\n" + regional)
    parts.append(
        "Qualitative narrative auto-generated without an LLM; values are "
        "reported verbatim from the model and have not been interpreted."
    )
    return "\n\n".join(parts)


def _llm_qualitative(llm, prompt_vars: dict[str, Any]) -> str | None:
    """Invoke the LLM with a short, opinion-light prompt. Returns None
    on any failure so the caller can fall back to the deterministic
    template."""
    try:
        from langchain_core.prompts import PromptTemplate  # noqa: WPS433

        prompt = PromptTemplate.from_template(_QUAL_PROMPT)
        chain = prompt | llm
        msg = chain.invoke(prompt_vars)
        text = getattr(msg, "content", None) or str(msg)
        return text.strip()
    except Exception as exc:
        logger.warning(
            f"LLM qualitative generation failed for "
            f"{prompt_vars.get('scenario_id')}/{prompt_vars.get('model_id')}: {exc}"
        )
        return None


def write_qualitative_reports(
    run_id: str,
    model_results: list[dict],
    scenarios: list[dict],
    use_llm: bool,
) -> dict[str, Any]:
    """Per-scenario qualitative Markdown plus a cross-scenario index.

    Returns a small summary dict with counts (used by the caller for
    logging / W&B).
    """
    qual_dir = qualitative_root(run_id)

    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for r in model_results:
        if r.get("status") == "completed" and r.get("outputs"):
            by_scenario[r.get("scenario_id") or "unknown"].append(r)

    scenario_meta = {n.get("scenario_id"): n for n in scenarios}

    llm = _try_get_llm() if use_llm and _llm_available() else None
    if use_llm and llm is None:
        logger.info(
            "Qualitative export: no LLM available; using deterministic templates."
        )

    cross_sections: dict[str, list[str]] = defaultdict(list)
    counts: dict[str, int] = {"scenarios": 0, "model_sections": 0, "llm_used": 0}

    for scenario_id, results in sorted(by_scenario.items()):
        narrative = scenario_meta.get(scenario_id)
        label = (narrative or {}).get("label") or scenario_id
        scenario_brief = _scenario_brief(narrative)

        lines: list[str] = []
        lines.append(f"# Qualitative model output narratives — {label}")
        lines.append("")
        lines.append(f"_Run ID: `{run_id}` · scenario: `{scenario_id}`_")
        lines.append("")
        if narrative:
            lines.append("> " + scenario_brief.replace("\n", "\n> "))
            lines.append("")
        lines.append(
            f"Below: one section per model with at least one completed output "
            f"({len(results)} model(s) total). Quantitative tables for the same "
            f"results live under `csv/raw/{scenario_id}/`."
        )
        lines.append("")

        for r in sorted(results, key=lambda x: x.get("model_id") or ""):
            model_id = r.get("model_id") or "unknown_model"
            outputs = r.get("outputs") or {}
            commodity_system = _commodity_system_for(model_id)

            outputs_json = json.dumps(outputs, indent=2, default=str)
            # Cap the JSON we send to the LLM so per-(scenario, model)
            # narrative calls stay safely under the served context
            # window. Long series are well-served by the corresponding
            # CSV anyway. Token-budgeted via src.common.context_budget
            # rather than char-counted so the cap tracks the actual
            # served context window (see slurm/jobs/*.job for the
            # PIPELINE_LLM_PROMPT_BUDGET_TOKENS export). Half of the
            # full prompt budget is reserved here because the prompt
            # also carries the scenario brief, regional summary, and
            # template overhead.
            try:
                from src.common.context_budget import (  # noqa: WPS433
                    get_prompt_budget_tokens,
                    truncate_to_budget,
                )
                qual_prompt_budget = max(512, get_prompt_budget_tokens() // 2)
                outputs_json = truncate_to_budget(outputs_json, qual_prompt_budget)
            except Exception:
                # Belt-and-braces char fallback if the import fails on
                # a thin standalone-export environment without tiktoken.
                if len(outputs_json) > 6000:
                    outputs_json = outputs_json[:6000] + "\n... [truncated for prompt]"

            regional_summary = _regional_summary_for(model_id, outputs)

            narrative_text: str | None = None
            if llm is not None:
                narrative_text = _llm_qualitative(
                    llm,
                    {
                        "scenario_label": label,
                        "scenario_id": scenario_id,
                        "scenario_brief": scenario_brief,
                        "model_id": model_id,
                        "commodity_system": commodity_system,
                        "outputs_json": outputs_json,
                        "regional_summary": regional_summary,
                    },
                )
                if narrative_text:
                    counts["llm_used"] += 1

            if not narrative_text:
                narrative_text = _deterministic_qualitative(
                    model_id, outputs, commodity_system
                )

            section = [
                f"## `{model_id}`  _(commodity: {commodity_system})_",
                "",
                narrative_text,
                "",
            ]
            lines.extend(section)
            counts["model_sections"] += 1

            cross_sections[model_id].append(
                f"### {label} (`{scenario_id}`)\n\n{narrative_text}\n"
            )

        out_path = qual_dir / f"{scenario_id}.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"wrote {out_path}")
        counts["scenarios"] += 1

    cross_path = qual_dir / "cross_scenario.md"
    cross_lines: list[str] = [
        f"# Cross-scenario qualitative comparison — run `{run_id}`",
        "",
        "Each section below collects one model's qualitative narrative across "
        "every scenario in which it produced output. Use this to spot models "
        "whose behaviour is robust to scenario assumptions versus those that "
        "swing widely.",
        "",
    ]
    for model_id in sorted(cross_sections.keys()):
        cross_lines.append(f"## `{model_id}`")
        cross_lines.append("")
        cross_lines.extend(cross_sections[model_id])
        cross_lines.append("")
    cross_path.write_text("\n".join(cross_lines), encoding="utf-8")
    logger.info(f"wrote {cross_path}")

    return counts


# --------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-id",
        default=None,
        help="Pipeline run ID (default: $HORMUZ_RUN_ID or current UTC timestamp).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the LLM qualitative pass; use deterministic templates only.",
    )
    parser.add_argument(
        "--no-exec-summary",
        action="store_true",
        help="Skip the second LLM pass that writes user_executive_summary.md.",
    )
    args = parser.parse_args(argv)

    log_slurm_context()
    run_id = args.run_id or get_run_id()
    use_llm = not args.no_llm
    exec_summary_env = os.environ.get("HORMUZ_EXPORT_EXEC_SUMMARY_LLM", "1")
    exec_summary_llm_enabled = (
        use_llm
        and not args.no_exec_summary
        and exec_summary_env == "1"
    )

    logger.info(f"=== Stage 5: Quantitative + qualitative export (run_id={run_id}) ===")

    model_results = load_model_results(run_id)
    if not model_results:
        logger.warning(
            f"No model_*.json files for run_id={run_id} under {state_dir()}. "
            f"Nothing to export."
        )
        return 0

    synthesis = load_synthesis(run_id)
    scenarios = load_scenarios(run_id)

    completed = sum(1 for r in model_results if r.get("status") == "completed")
    skipped = sum(1 for r in model_results if r.get("status") == "skipped")
    failed = sum(1 for r in model_results if r.get("status") == "failed")
    logger.info(
        f"Loaded {len(model_results)} model results "
        f"({completed} completed, {skipped} skipped, {failed} failed); "
        f"synthesis={'yes' if synthesis else 'no'}; "
        f"scenarios={len(scenarios)}"
    )

    # Quantitative CSVs (always; no external deps required).
    try:
        write_model_status_csv(run_id, model_results)
        write_synthesis_outcomes_csv(run_id, synthesis)
        write_consistency_flags_csv(run_id, synthesis)
        write_quantitative_results_csv(run_id, model_results)
        write_per_model_raw_csvs(run_id, model_results)
        # Distributional CSVs: silently skipped when no spec/crosswalk
        # YAML is present or no model produced regional output.
        write_regional_outcomes_csvs(run_id, model_results)
        write_sectoral_outcomes_csv(run_id, model_results)
        write_synthesis_distributions_csv(run_id, synthesis)
    except Exception:
        logger.error("CSV export failed:\n" + traceback.format_exc())
        return 1

    # Qualitative narratives (best-effort; falls back to templates).
    try:
        counts = write_qualitative_reports(
            run_id, model_results, scenarios, use_llm=use_llm
        )
        logger.info(
            f"Qualitative export: {counts['scenarios']} scenario file(s), "
            f"{counts['model_sections']} model section(s), "
            f"LLM-generated: {counts['llm_used']}."
        )
        try:
            write_user_executive_summary(run_id, exec_summary_llm_enabled)
        except Exception:
            logger.error(
                "User executive summary failed:\n" + traceback.format_exc()
            )
    except Exception:
        logger.error("Qualitative export failed:\n" + traceback.format_exc())
        # CSVs already written; do not fail the stage.
        return 0

    logger.info(
        f"Export complete. Artefacts under: {reports_root(run_id)} "
        f"(csv/, qualitative/)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
