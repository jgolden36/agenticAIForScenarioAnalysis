"""Coverage ledger: one record per (scenario, model) cell of a pipeline run.

Reviewers asked why the number of contributing models differs by
scenario and what the actual reason for every skipped cell was. The
pipeline already records most of the evidence, but scattered across
``<run_id>_params_*.json`` (Module 2), the Stage 3 manifests,
``<run_id>_model_*.json`` (Module 3) and ``data/outputs/`` (per-model
artefacts). This module joins them into a single ledger over the full
grid ``scenarios x ALL_MODEL_SPECS`` and classifies every cell:

``exec_status``
    ``completed`` / ``failed`` / ``skipped`` (a Module 3 record exists), or
    ``not_dispatched`` / ``no_record`` when it does not.

``skip_class``
    Why the cell did not contribute, derived from the recorded error
    message (``stub``, ``missing_config``, ``missing_data_or_binary``,
    ``runtime_or_license_missing``, ``validation_failed``, ``timeout``,
    ``runtime_error``) or from the surrounding bookkeeping
    (``parameter_extraction_failed``, ``parameter_extraction_missing``,
    ``not_in_manifest``, ``record_overwritten``, ``record_missing``).

``implementation_mode``
    Which implementation produced a completed cell (see
    :class:`src.common.types.ImplementationMode`).

``upstream_sources`` / ``stale_upstream``
    The upstream models whose outputs replaced this cell's LLM-extracted
    inputs, each flagged with whether that source completed *in this
    run* for the same scenario. A source that did not is evidence that a
    stale ``data/outputs`` entry leaked into the barrier (fixed in
    ``slurm/scripts/dispatch_models.py``, but historical runs predate it).

Two loaders are provided: :func:`ledger_from_state_dir` (full evidence,
needs the run's ``data/pipeline_state`` files) and
:func:`ledger_from_report_csv` (partial evidence from
``data/reports/<run_id>/csv/model_status.csv`` plus
``consistency_flags.csv`` only, for runs whose state files are gone).
No matplotlib here; the figure lives in ``slurm/scripts/visualize_results.py``.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.common.types import AnalyticalLevel, ImplementationMode, Scenario
from src.models.base import resolve_implementation_mode

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

EXEC_STATUSES = ("completed", "failed", "skipped", "not_dispatched", "no_record")

SKIP_CLASSES: tuple[str, ...] = (
    "completed",
    "validation_failed",
    "timeout",
    "runtime_error",
    "runtime_or_license_missing",
    "missing_data_or_binary",
    "missing_config",
    "stub",
    "not_implemented_other",
    "not_registered",
    "parameter_extraction_failed",
    "parameter_extraction_missing",
    "not_in_manifest",
    "record_overwritten",
    "record_missing",
)

# Letter codes used in the Markdown / LaTeX matrices (ASCII so the LaTeX
# fragment compiles without extra packages). Uppercase = completed (by
# implementation mode), lowercase = did not contribute.
CELL_CODES: dict[str, str] = {
    "completed/full_upstream": "F",
    "completed/published_output_ingestion": "I",
    "completed/analytical_reduction": "R",
    "completed/unknown": "U",
    "validation_failed": "v",
    "timeout": "t",
    "runtime_error": "x",
    "runtime_or_license_missing": "l",
    "missing_data_or_binary": "d",
    "missing_config": "c",
    "stub": "s",
    "not_implemented_other": "n",
    "not_registered": "g",
    "parameter_extraction_failed": "p",
    "parameter_extraction_missing": "q",
    "not_in_manifest": "m",
    "record_overwritten": "o",
    "record_missing": "-",
}

CELL_CODE_LEGEND: dict[str, str] = {
    "F": "completed, full upstream model",
    "I": "completed, published-output ingestion",
    "R": "completed, analytical reduction",
    "U": "completed, implementation mode not recorded",
    "v": "failed: input validation",
    "t": "failed: timeout",
    "x": "failed: runtime error",
    "l": "runtime or licence missing (JVM, GAMS, ...)",
    "d": "data, binary or model tree missing",
    "c": "adapter config (YAML) not provided",
    "s": "typed stub (no execute path)",
    "n": "not implemented (other)",
    "g": "model not in registry",
    "p": "parameter extraction failed",
    "q": "no parameter-extraction record",
    "m": "parameters extracted but cell not in any manifest",
    "o": "executed, but record overwritten before synthesis (tier collision)",
    "-": "no record anywhere",
}

_TIER_BY_LEVEL = {
    AnalyticalLevel.COMBAT: "commodity",
    AnalyticalLevel.COMMODITY: "commodity",
    AnalyticalLevel.COMMODITY_DOWNSTREAM: "commodity_downstream",
    AnalyticalLevel.SHORT_RUN_MACRO: "macro",
    AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC: "macro",
}

_NOT_IMPL_PREFIX = re.compile(r"^(model\s+)?not yet implemented:\s*", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_execution(status: str | None, error_message: str | None) -> str:
    """Map a Module 3 record's status + error message onto a skip class."""
    status_l = (status or "").strip().lower()
    msg = _NOT_IMPL_PREFIX.sub("", (error_message or "").strip())
    low = msg.lower()

    if status_l == "completed":
        return "completed"

    if status_l == "failed":
        if "validation failed" in low:
            return "validation_failed"
        if "timed out" in low or "timeout" in low:
            return "timeout"
        if "not found in registry" in low:
            return "not_registered"
        if re.search(r"\bjvm\b|\bjava\b|\bgams\b|licen[cs]e|modulenotfounderror|importerror|no module named", low):
            return "runtime_or_license_missing"
        if re.search(r"filenotfounderror|no such file|not found", low):
            return "missing_data_or_binary"
        return "runtime_error"

    if status_l == "skipped":
        if re.search(r"(requires|provide|supply|pass)\s+an?\s+\w*config\b|\w+config\s+in\s+configs/|\.yaml\b", low):
            return "missing_config"
        if re.search(r"\.execute(\(\))?\s+is\s+not\s+yet\s+implemented|adapter\s+is\s+a\s+stub|\bis a stub\b", low):
            return "stub"
        if re.search(r"\bgams\b|licen[cs]e|executable on path|\bjvm\b|\bjava\b", low):
            return "runtime_or_license_missing"
        if re.search(r"not found|no such file|\bvendor\b|baseline|directory|source tree", low):
            return "missing_data_or_binary"
        return "not_implemented_other"

    return "record_missing"


def classify_not_dispatched(
    param_status: str,
    in_manifest: bool | None,
    outputs_status_this_run: str | None,
) -> tuple[str, str]:
    """Classify a cell with no Module 3 record. Returns (exec_status, skip_class)."""
    if param_status == "failed":
        return "not_dispatched", "parameter_extraction_failed"
    if param_status == "missing":
        return "not_dispatched", "parameter_extraction_missing"
    if in_manifest is False:
        return "not_dispatched", "not_in_manifest"
    if outputs_status_this_run:
        return "no_record", "record_overwritten"
    return "no_record", "record_missing"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class UpstreamSource:
    source_model_id: str
    source_field: str | None
    target_name: str
    target_key: str | None
    source_ran_in_run: bool
    computed_value: Any = None
    llm_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CoverageCell:
    scenario_id: str
    model_id: str
    commodity_system: str = ""
    analytical_level: str = ""
    tier: str = ""
    param_status: str = "missing"  # completed | failed | missing
    param_error: str | None = None
    in_manifest: bool | None = None  # None when manifests unavailable
    exec_status: str = "no_record"
    skip_class: str = "record_missing"
    error_message: str | None = None
    implementation_mode: str | None = None
    # recorded (run record carries the mode) | output_marker (derived from
    # _execution_mode / _used_analytical_mvp in the outputs) |
    # adapter_declared (adapter's ImplementationInfo default) | none
    implementation_mode_evidence: str = "none"
    runtime_seconds: float | None = None
    task_id: int | None = None
    manifest_name: str | None = None
    outputs_status_this_run: str | None = None
    record_source: str | None = None  # state | csv | recovered
    upstream_sources: list[UpstreamSource] = field(default_factory=list)
    stale_upstream: bool = False
    upstream_evidence: str = "none"  # full | flags_only | none

    @property
    def cell_code(self) -> str:
        if self.exec_status == "completed":
            return CELL_CODES.get(
                f"completed/{self.implementation_mode or 'unknown'}",
                CELL_CODES["completed/unknown"],
            )
        return CELL_CODES.get(self.skip_class, "-")

    @property
    def contributed(self) -> bool:
        return self.exec_status == "completed"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["upstream_sources"] = [s.to_dict() for s in self.upstream_sources]
        d["cell_code"] = self.cell_code
        d["contributed"] = self.contributed
        return d


# ---------------------------------------------------------------------------
# Registry lookups (best effort, never required)
# ---------------------------------------------------------------------------


def registry_lookup() -> tuple[dict[str, str], dict[str, AnalyticalLevel]]:
    """Return (commodity_system_by_model, level_by_model) from the registry."""
    systems, levels, _declared = registry_lookup_full()
    return systems, levels


def registry_lookup_full() -> tuple[dict[str, str], dict[str, AnalyticalLevel], dict[str, str]]:
    """Return (systems, levels, declared_mode_when_executed) per model id."""
    try:
        from src.models.registry import build_default_registry, default_config_dir

        registry = build_default_registry(default_config_dir())
    except Exception:  # noqa: BLE001
        try:
            from src.models.registry import build_default_registry

            registry = build_default_registry()
        except Exception:  # noqa: BLE001
            return {}, {}, {}
    adapters = registry.all_adapters()
    systems = {a.model_id: a.commodity_system.value for a in adapters}
    levels = {a.model_id: a.analytical_level for a in adapters}
    declared: dict[str, str] = {}
    for a in adapters:
        try:
            mode = a.implementation_info.mode_when_executed
        except Exception:  # noqa: BLE001
            continue
        if mode != ImplementationMode.UNKNOWN:
            declared[a.model_id] = mode.value
    return systems, levels, declared


def canonical_scenario_order(scenario_ids: Iterable[str]) -> list[str]:
    """Order scenario ids A..E first (Scenario enum order), then any extras."""
    known = [s.value for s in Scenario]
    ids = list(dict.fromkeys(scenario_ids))
    return [s for s in known if s in ids] + [s for s in ids if s not in known]


def default_model_ids() -> list[str]:
    try:
        from src.parameters.model_specs import ALL_MODEL_SPECS

        return list(ALL_MODEL_SPECS)
    except Exception:  # noqa: BLE001
        return []


def default_scenario_ids() -> list[str]:
    return [s.value for s in Scenario]


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def _overrides_from_record(rec: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = rec.get("outputs") or {}
    overrides = outputs.get("_upstream_overrides") if isinstance(outputs, dict) else None
    if not overrides:
        overrides = rec.get("upstream_overrides") or []
    return [o for o in overrides if isinstance(o, dict)]


def build_ledger(
    scenario_ids: Iterable[str],
    model_ids: Iterable[str],
    *,
    param_records: dict[tuple[str, str], dict[str, Any]] | None = None,
    model_records: dict[tuple[str, str], dict[str, Any]] | None = None,
    manifest_cells: set[tuple[str, str]] | None = None,
    outputs_status_index: dict[tuple[str, str], str] | None = None,
    systems_by_model: dict[str, str] | None = None,
    levels_by_model: dict[str, AnalyticalLevel] | None = None,
    declared_modes_by_model: dict[str, str] | None = None,
    record_source: str = "state",
    upstream_evidence: str = "full",
) -> list[CoverageCell]:
    """Join the per-stage evidence into one :class:`CoverageCell` per grid cell.

    Args:
        param_records: ``(scenario, model) -> params record`` (Module 2).
        model_records: ``(scenario, model) -> execution record`` (Module 3).
        manifest_cells: cells present in any Stage 3 manifest; ``None``
            when manifests are unavailable (then ``in_manifest`` is None).
        outputs_status_index: ``(scenario, model) -> status`` for
            ``data/outputs`` entries written by *this* run; used to tell
            ``record_overwritten`` from ``record_missing``.
        declared_modes_by_model: adapter-declared
            ``ImplementationInfo.mode_when_executed`` per model, used as the
            last-resort label (evidence ``adapter_declared``) for completed
            cells whose records carry no marker (historical runs).
    """
    param_records = param_records or {}
    model_records = model_records or {}
    outputs_status_index = outputs_status_index or {}
    systems_by_model = systems_by_model or {}
    levels_by_model = levels_by_model or {}
    declared_modes_by_model = declared_modes_by_model or {}
    scenario_ids = canonical_scenario_order(scenario_ids)
    model_ids = list(model_ids)

    cells: dict[tuple[str, str], CoverageCell] = {}
    for scenario_id in scenario_ids:
        for model_id in model_ids:
            key = (scenario_id, model_id)
            level = levels_by_model.get(model_id)
            cell = CoverageCell(
                scenario_id=scenario_id,
                model_id=model_id,
                commodity_system=systems_by_model.get(model_id, ""),
                analytical_level=level.value if level else "",
                tier=_TIER_BY_LEVEL.get(level, "") if level else "",
                record_source=record_source,
                upstream_evidence=upstream_evidence,
            )
            prec = param_records.get(key)
            if prec is None:
                cell.param_status = "missing"
            else:
                pstatus = str(prec.get("status") or "completed").lower()
                if pstatus != "completed" or not isinstance(prec.get("parameters"), list):
                    cell.param_status = "failed"
                    cell.param_error = prec.get("error_message")
                else:
                    cell.param_status = "completed"
            if manifest_cells is not None:
                cell.in_manifest = key in manifest_cells
            cell.outputs_status_this_run = outputs_status_index.get(key)

            mrec = model_records.get(key)
            if mrec is not None:
                status = str(mrec.get("status") or "").lower()
                cell.exec_status = status if status in ("completed", "failed", "skipped") else "no_record"
                cell.error_message = mrec.get("error_message")
                cell.skip_class = classify_execution(status, cell.error_message)
                cell.runtime_seconds = _float_or_none(mrec.get("runtime_seconds"))
                cell.task_id = _int_or_none(mrec.get("task_id"))
                cell.manifest_name = mrec.get("manifest_name")
                if cell.exec_status == "completed":
                    mode = mrec.get("implementation_mode")
                    evidence = "recorded"
                    if not mode or mode == ImplementationMode.UNKNOWN.value:
                        resolved = resolve_implementation_mode(
                            None, None, outputs=mrec.get("outputs") or {}
                        ).value
                        if resolved != ImplementationMode.UNKNOWN.value:
                            mode, evidence = resolved, "output_marker"
                        elif model_id in declared_modes_by_model:
                            mode, evidence = declared_modes_by_model[model_id], "adapter_declared"
                        else:
                            mode, evidence = ImplementationMode.UNKNOWN.value, "none"
                    cell.implementation_mode = mode
                    cell.implementation_mode_evidence = evidence
                if mrec.get("recovered"):
                    cell.record_source = "recovered"
            else:
                cell.exec_status, cell.skip_class = classify_not_dispatched(
                    cell.param_status, cell.in_manifest, cell.outputs_status_this_run
                )
            cells[key] = cell

    # Second pass: upstream sources need every cell's exec_status.
    for key, cell in cells.items():
        mrec = model_records.get(key)
        if mrec is None or cell.exec_status != "completed":
            continue
        for o in _overrides_from_record(mrec):
            src = str(o.get("source_model_id") or "")
            if not src:
                continue
            src_cell = cells.get((cell.scenario_id, src))
            ran = bool(src_cell and src_cell.exec_status == "completed")
            cell.upstream_sources.append(
                UpstreamSource(
                    source_model_id=src,
                    source_field=o.get("source_field"),
                    target_name=str(o.get("name") or ""),
                    target_key=o.get("target_key"),
                    source_ran_in_run=ran,
                    computed_value=o.get("computed_value"),
                    llm_value=o.get("llm_value"),
                )
            )
        cell.stale_upstream = any(not s.source_ran_in_run for s in cell.upstream_sources)

    return [cells[(s, m)] for s in scenario_ids for m in model_ids]


def _float_or_none(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int_or_none(v: Any) -> int | None:
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_param_records(state_dir: Path, run_id: str) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for path in sorted(state_dir.glob(f"{run_id}_params_*.json")):
        rec = _load_json(path)
        if isinstance(rec, dict):
            out[(str(rec.get("scenario_id")), str(rec.get("model_id")))] = rec
    return out


def load_model_records(state_dir: Path, run_id: str) -> dict[tuple[str, str], dict]:
    """Load Module 3 records. When two files describe the same cell (a
    legacy ``model_<n>`` file plus a ``model_recovered_*`` file), the
    recovered one wins only if the legacy one is absent; otherwise the
    first seen is kept and the duplicate ignored."""
    out: dict[tuple[str, str], dict] = {}
    for path in sorted(state_dir.glob(f"{run_id}_model_*.json")):
        rec = _load_json(path)
        if not isinstance(rec, dict):
            continue
        key = (str(rec.get("scenario_id")), str(rec.get("model_id")))
        if key in out and not out[key].get("recovered"):
            continue
        out[key] = rec
    return out


def load_manifest_cells(state_dir: Path, run_id: str) -> set[tuple[str, str]] | None:
    mdir = state_dir / "manifests"
    if not mdir.exists():
        return None
    cells: set[tuple[str, str]] = set()
    found = False
    for path in sorted(mdir.glob(f"{run_id}_models*.json")):
        entries = _load_json(path)
        if not isinstance(entries, list):
            continue
        found = True
        for e in entries:
            if isinstance(e, dict):
                cells.add((str(e.get("scenario_id")), str(e.get("model_id"))))
    return cells if found else None


def outputs_status_index(outputs_root: Path | None, run_id: str) -> dict[tuple[str, str], str]:
    """``(scenario, model) -> status`` for data/outputs entries of this run."""
    out: dict[tuple[str, str], str] = {}
    if outputs_root is None or not outputs_root.exists():
        return out
    for scenario_dir in sorted(outputs_root.iterdir()):
        if not scenario_dir.is_dir():
            continue
        for model_dir in sorted(scenario_dir.iterdir()):
            meta = _load_json(model_dir / "metadata.json")
            if isinstance(meta, dict) and meta.get("run_id") == run_id:
                out[(scenario_dir.name, model_dir.name)] = str(meta.get("status") or "")
    return out


def scenario_ids_from_state(state_dir: Path, run_id: str) -> list[str]:
    state = _load_json(state_dir / f"{run_id}_scenarios.json")
    if isinstance(state, dict):
        ids = [str(n.get("scenario_id")) for n in state.get("scenario_narratives", []) if isinstance(n, dict)]
        if ids:
            return ids
    return default_scenario_ids()


def ledger_from_state_dir(
    run_id: str,
    state_dir: Path,
    outputs_root: Path | None = None,
    *,
    scenario_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
) -> list[CoverageCell]:
    systems, levels, declared = registry_lookup_full()
    return build_ledger(
        scenario_ids or scenario_ids_from_state(state_dir, run_id),
        model_ids or default_model_ids(),
        param_records=load_param_records(state_dir, run_id),
        model_records=load_model_records(state_dir, run_id),
        manifest_cells=load_manifest_cells(state_dir, run_id),
        outputs_status_index=outputs_status_index(outputs_root, run_id),
        systems_by_model=systems,
        levels_by_model=levels,
        declared_modes_by_model=declared,
        record_source="state",
        upstream_evidence="full",
    )


_MARKER_KEYS = ("_execution_mode", "_implementation_mode", "_used_analytical_mvp", "_macro_source")


def output_markers_from_quantitative_csv(csv_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Recover implementation-mode markers per cell from quantitative_results.csv."""
    out: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for r in _read_csv(csv_dir / "quantitative_results.csv"):
        key_name = r.get("output_key", "")
        if key_name not in _MARKER_KEYS:
            continue
        raw = r.get("value_raw")
        value: Any = raw
        if key_name == "_used_analytical_mvp":
            value = str(raw).strip().lower() == "true"
        out[(r.get("scenario_id", ""), r.get("model_id", ""))][key_name] = value
    return dict(out)


def ledger_from_report_csv(
    run_id: str,
    csv_dir: Path,
    *,
    scenario_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
) -> list[CoverageCell]:
    """Build the ledger from Stage 5 CSVs when state files are unavailable.

    ``model_status.csv`` gives per-cell status / error / implementation
    mode; ``consistency_flags.csv`` gives the *flagged* upstream overrides
    only, so ``upstream_evidence`` is ``flags_only``. Parameter-stage and
    manifest evidence is absent, so cells with no row are reported as
    ``no_record`` / ``record_missing``.
    """
    status_rows = _read_csv(csv_dir / "model_status.csv")
    flags = _read_csv(csv_dir / "consistency_flags.csv")
    markers = output_markers_from_quantitative_csv(csv_dir)
    model_records: dict[tuple[str, str], dict] = {}
    for r in status_rows:
        key = (r.get("scenario_id", ""), r.get("model_id", ""))
        rec: dict[str, Any] = dict(r)
        rec["outputs"] = dict(markers.get(key, {}))
        if not rec.get("implementation_mode"):
            rec.pop("implementation_mode", None)
        model_records[key] = rec
    # Attach flagged overrides as pseudo-records.
    for f_ in flags:
        key = (f_.get("scenario_id", ""), f_.get("model_a_id", ""))
        rec = model_records.get(key)
        if rec is None:
            continue
        msg = f_.get("message", "") or ""
        if "upstream-computed" not in msg and "cross-source" not in msg.lower():
            continue
        rec.setdefault("upstream_overrides", []).append({
            "source_model_id": f_.get("model_b_id"),
            "name": (f_.get("variable") or "").split("[")[0],
            "target_key": _target_key_from_variable(f_.get("variable") or ""),
            "llm_value": f_.get("value_a"),
            "computed_value": f_.get("value_b"),
        })
    present_scenarios = canonical_scenario_order(k[0] for k in model_records)
    systems, levels, declared = registry_lookup_full()
    scen = scenario_ids or (present_scenarios or default_scenario_ids())
    mods = model_ids or default_model_ids()
    return build_ledger(
        scen,
        mods,
        model_records=model_records,
        systems_by_model=systems,
        levels_by_model=levels,
        declared_modes_by_model=declared,
        record_source="csv",
        upstream_evidence="flags_only",
        # Parameter / manifest evidence is unknown from CSVs: mark every
        # cell as having parameters so missing rows classify as records.
        param_records={(s, m): {"status": "completed", "parameters": []} for s in scen for m in mods},
    )


def _target_key_from_variable(variable: str) -> str | None:
    m = re.search(r"\[([^\]]+)\]", variable)
    return m.group(1) if m else None


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Summaries and renderers
# ---------------------------------------------------------------------------


def summarize(cells: list[CoverageCell]) -> dict[str, Any]:
    scenario_ids = canonical_scenario_order(c.scenario_id for c in cells)
    model_ids = list(dict.fromkeys(c.model_id for c in cells))
    by_scenario: dict[str, dict[str, Any]] = {}
    for s in scenario_ids:
        sc = [c for c in cells if c.scenario_id == s]
        by_scenario[s] = {
            "cells": len(sc),
            "completed": sum(c.contributed for c in sc),
            "by_exec_status": dict(Counter(c.exec_status for c in sc)),
            "by_skip_class": dict(Counter(c.skip_class for c in sc)),
            "by_implementation_mode": dict(Counter(c.implementation_mode for c in sc if c.contributed)),
            "completed_models": [c.model_id for c in sc if c.contributed],
            "stale_upstream_cells": [c.model_id for c in sc if c.stale_upstream],
        }
    scenarios_by_model = {
        m: [c.scenario_id for c in cells if c.model_id == m and c.contributed]
        for m in model_ids
    }
    anchors = [m for m, s in scenarios_by_model.items() if len(s) == len(scenario_ids) and scenario_ids]
    return {
        "scenarios": scenario_ids,
        "models": model_ids,
        "grid_cells": len(cells),
        "completed_cells": sum(c.contributed for c in cells),
        "by_skip_class": dict(Counter(c.skip_class for c in cells)),
        "by_implementation_mode": dict(Counter(c.implementation_mode for c in cells if c.contributed)),
        "by_implementation_mode_evidence": dict(Counter(c.implementation_mode_evidence for c in cells if c.contributed)),
        "by_scenario": by_scenario,
        "scenarios_completed_by_model": scenarios_by_model,
        "all_scenario_models": anchors,
        "stale_upstream_cells": [
            {"scenario_id": c.scenario_id, "model_id": c.model_id,
             "sources_not_run": [s.source_model_id for s in c.upstream_sources if not s.source_ran_in_run]}
            for c in cells if c.stale_upstream
        ],
        "upstream_evidence": cells[0].upstream_evidence if cells else "none",
        "record_source": cells[0].record_source if cells else None,
    }


def to_csv_rows(cells: list[CoverageCell]) -> list[dict[str, Any]]:
    rows = []
    for c in cells:
        d = c.to_dict()
        d["upstream_sources"] = ";".join(
            f"{s.source_model_id}{'' if s.source_ran_in_run else '(not run)'}" for s in c.upstream_sources
        )
        rows.append(d)
    return rows


CSV_COLUMNS = [
    "scenario_id", "model_id", "commodity_system", "analytical_level", "tier",
    "param_status", "param_error", "in_manifest", "exec_status", "skip_class",
    "cell_code", "implementation_mode", "implementation_mode_evidence",
    "runtime_seconds", "task_id", "manifest_name",
    "outputs_status_this_run", "record_source", "upstream_sources", "stale_upstream",
    "upstream_evidence", "error_message",
]


def write_csv(cells: list[CoverageCell], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in to_csv_rows(cells):
            w.writerow(r)
    return path


def _matrix(cells: list[CoverageCell]) -> tuple[list[str], list[str], dict[tuple[str, str], CoverageCell]]:
    scenario_ids = canonical_scenario_order(c.scenario_id for c in cells)
    by_key = {(c.scenario_id, c.model_id): c for c in cells}
    # Order models by commodity system then id for a readable matrix.
    model_ids = sorted(
        dict.fromkeys(c.model_id for c in cells),
        key=lambda m: (next((c.commodity_system for c in cells if c.model_id == m), ""), m),
    )
    return scenario_ids, model_ids, by_key


_SCENARIO_SHORT = {
    "swift_contained": "A", "prolonged_contained": "B", "swift_escalated": "C",
    "prolonged_escalated": "D", "infrastructure_collapse": "E",
}


def render_markdown(cells: list[CoverageCell], run_id: str, summary: dict[str, Any] | None = None) -> str:
    summary = summary or summarize(cells)
    scenario_ids, model_ids, by_key = _matrix(cells)
    lines = [f"# Coverage ledger for run `{run_id}`", ""]
    lines.append(
        f"Grid: {len(summary['models'])} models x {len(summary['scenarios'])} scenarios = "
        f"{summary['grid_cells']} cells; {summary['completed_cells']} completed. "
        f"Record source: `{summary['record_source']}`; upstream evidence: `{summary['upstream_evidence']}`."
    )
    ev = summary.get("by_implementation_mode_evidence") or {}
    if ev:
        lines.append(
            "Implementation-mode evidence for completed cells: "
            + ", ".join(f"{k}: {v}" for k, v in sorted(ev.items()))
            + " (`adapter_declared` means the run record carried no marker and the adapter's declared default mode was used)."
        )
    lines += ["", "## Matrix", "", "| model | system | " + " | ".join(_SCENARIO_SHORT.get(s, s) for s in scenario_ids) + " |",
              "|---|---|" + "|".join("---" for _ in scenario_ids) + "|"]
    for m in model_ids:
        system = next((c.commodity_system for c in cells if c.model_id == m), "")
        codes = [by_key[(s, m)].cell_code if (s, m) in by_key else "-" for s in scenario_ids]
        lines.append(f"| `{m}` | {system} | " + " | ".join(f"`{c}`" for c in codes) + " |")
    lines += ["", "Legend: " + "; ".join(f"`{k}` = {v}" for k, v in CELL_CODE_LEGEND.items()), ""]

    lines += ["## Per scenario", "", "| scenario | cells | completed | skip classes |", "|---|---|---|---|"]
    for s, info in summary["by_scenario"].items():
        classes = ", ".join(f"{k}: {v}" for k, v in sorted(info["by_skip_class"].items()) if k != "completed")
        lines.append(f"| {s} | {info['cells']} | {info['completed']} | {classes} |")

    lines += ["", "## Models completed in every scenario", "",
              ", ".join(f"`{m}`" for m in summary["all_scenario_models"]) or "_none_", ""]
    lines += ["## Scenarios completed per model", "", "| model | scenarios |", "|---|---|"]
    for m, scen in summary["scenarios_completed_by_model"].items():
        lines.append(f"| `{m}` | {', '.join(_SCENARIO_SHORT.get(s, s) for s in scen) or '-'} |")

    stale = summary["stale_upstream_cells"]
    lines += ["", "## Cells whose forwarded inputs cite an upstream model that did not complete in this run", ""]
    if stale:
        lines += ["| scenario | model | sources not run |", "|---|---|---|"]
        for c in stale:
            lines.append(f"| {c['scenario_id']} | `{c['model_id']}` | {', '.join(c['sources_not_run'])} |")
        if summary["upstream_evidence"] == "flags_only":
            lines.append("")
            lines.append("_Evidence limited to flagged overrides (consistency_flags.csv); unflagged forwarding is not visible from CSVs._")
    else:
        lines.append("_none_")
    lines.append("")
    return "\n".join(lines)


def render_latex(cells: list[CoverageCell], run_id: str, label: str = "tab:coverage") -> str:
    scenario_ids, model_ids, by_key = _matrix(cells)
    cols = "ll" + "c" * len(scenario_ids)
    header = " & ".join(["Model", "System"] + [_SCENARIO_SHORT.get(s, s) for s in scenario_ids])
    out = [
        "% Generated by src/interface/coverage.py; do not edit by hand.",
        "\\begin{table}[t]", "\\centering", "\\small",
        f"\\caption{{Per-cell coverage of run {_tex(run_id)}. Uppercase = completed "
        "(F full upstream model, I published-output ingestion, R analytical reduction, U mode not recorded); "
        "lowercase = did not contribute (" + "; ".join(f"{k} {_tex(v)}" for k, v in CELL_CODE_LEGEND.items() if k.islower() or k == '-') + ").}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{cols}}}", "\\toprule", header + " \\\\", "\\midrule",
    ]
    for m in model_ids:
        system = next((c.commodity_system for c in cells if c.model_id == m), "")
        codes = [by_key[(s, m)].cell_code if (s, m) in by_key else "-" for s in scenario_ids]
        out.append(" & ".join([f"\\texttt{{{_tex(m)}}}", _tex(system)] + codes) + " \\\\")
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(out)


def _tex(s: str) -> str:
    return (
        str(s).replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("&", "\\&")
        .replace("%", "\\%").replace("#", "\\#").replace("{", "\\{").replace("}", "\\}")
    )


def write_all(cells: list[CoverageCell], run_id: str, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(cells)
    paths = {
        "csv": write_csv(cells, out_dir / "coverage_ledger.csv"),
        "json": out_dir / "coverage_ledger.json",
        "md": out_dir / "coverage_ledger.md",
        "tex": out_dir / "coverage_ledger.tex",
    }
    with open(paths["json"], "w") as f:
        json.dump({"run_id": run_id, "summary": summary, "cells": [c.to_dict() for c in cells]}, f, indent=2, default=str)
    paths["md"].write_text(render_markdown(cells, run_id, summary), encoding="utf-8")
    paths["tex"].write_text(render_latex(cells, run_id), encoding="utf-8")
    return paths
