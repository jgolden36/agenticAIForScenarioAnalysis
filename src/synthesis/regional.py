"""Regional and sectoral distribution extraction for Module 4 / Stage 5.

Reads two declarative YAML configs:

* ``configs/distributional_outputs.yaml`` — which keys in each model's
  ``outputs`` dict carry regional / sectoral structure, and how to read
  them.
* ``configs/region_crosswalk.yaml`` — per-model mapping from native
  region/country/node ids onto a unified taxonomy
  ``{US, CHN, IND, EU, MENA_GCC, MENA_OTHER, SSA, LAC, ROW, GLOBAL}``.

Both files are *opt-in*: if either is missing, the loaders return empty
mappings and the extraction functions return empty lists, so callers
that integrate regional reporting (the synthesizer, the Stage-5
exporter, the Stage-6 visualizer) degrade silently to today's
scenario-level scalar behaviour.

This module is import-safe in environments without the model registry
or any of its optional dependencies; it depends only on ``pyyaml`` and
the stdlib.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.common.logging import get_logger

logger = get_logger(__name__)


UNIFIED_REGIONS: tuple[str, ...] = (
    "US",
    "CHN",
    "IND",
    "EU",
    "MENA_GCC",
    "MENA_OTHER",
    "SSA",
    "LAC",
    "ROW",
    "GLOBAL",
)

DEFAULT_UNIFIED = "ROW"

_DEFAULT_DISTRIBUTIONAL_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "distributional_outputs.yaml"
)
_DEFAULT_CROSSWALK_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "region_crosswalk.yaml"
)

# Track unmapped (model, native_id) pairs so we warn at most once per pair.
_WARNED_UNMAPPED: set[tuple[str, str]] = set()


# --------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------


@dataclass(frozen=True)
class RegionalRecord:
    """One distributional data point extracted from a model output dict.

    ``unified_region`` is the result of running ``native_region`` through
    the per-model crosswalk; ``sector`` is None for purely regional data.
    """

    model_id: str
    output_key: str
    native_region: str
    unified_region: str
    sector: str | None
    value_label: str
    value: float


@dataclass
class DispersionMetric:
    """Summary of how widely a (model, output_key, value_label) varies
    across regions. Used by the synthesizer prompt and the qualitative
    narrative prompt."""

    model_id: str
    output_key: str
    value_label: str
    n_regions: int
    min_value: float
    max_value: float
    mean_value: float
    stdev_value: float
    top_region: str
    top_value: float
    bottom_region: str
    bottom_value: float
    range_value: float = field(init=False)

    def __post_init__(self) -> None:
        self.range_value = self.max_value - self.min_value


# --------------------------------------------------------------------
# Loaders (cached)
# --------------------------------------------------------------------


@lru_cache(maxsize=4)
def load_distributional_spec(path: str | None = None) -> dict[str, Any]:
    """Load ``configs/distributional_outputs.yaml``.

    Returns ``{}`` (and logs a debug line) when the file is absent or
    malformed, so callers can run unmodified on environments without
    the config.
    """
    p = Path(path) if path else _DEFAULT_DISTRIBUTIONAL_PATH
    if not p.exists():
        logger.debug("distributional spec not found at %s; skipping", p)
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning("distributional spec at %s is not a dict; ignoring", p)
            return {}
        return data
    except Exception as exc:  # pragma: no cover
        logger.warning("could not parse %s: %s", p, exc)
        return {}


@lru_cache(maxsize=4)
def load_region_crosswalk(path: str | None = None) -> dict[str, dict[str, str]]:
    """Load ``configs/region_crosswalk.yaml``.

    Returns ``{}`` when the file is absent. Native ids are normalised to
    upper-case so lookups are case-insensitive.
    """
    p = Path(path) if path else _DEFAULT_CROSSWALK_PATH
    if not p.exists():
        logger.debug("region crosswalk not found at %s; skipping", p)
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning("region crosswalk at %s is not a dict; ignoring", p)
            return {}
        out: dict[str, dict[str, str]] = {}
        for model_id, mapping in data.items():
            if not isinstance(mapping, dict):
                continue
            normalised: dict[str, str] = {}
            for native, unified in mapping.items():
                if unified is None:
                    continue
                normalised[str(native).upper()] = str(unified)
            out[str(model_id).lower()] = normalised
        return out
    except Exception as exc:  # pragma: no cover
        logger.warning("could not parse %s: %s", p, exc)
        return {}


def reset_caches() -> None:
    """Clear the YAML loader caches (for tests)."""
    load_distributional_spec.cache_clear()
    load_region_crosswalk.cache_clear()
    _WARNED_UNMAPPED.clear()


# --------------------------------------------------------------------
# Crosswalk lookup
# --------------------------------------------------------------------


def map_to_unified(model_id: str, native_region: str) -> str:
    """Map a native region id through the per-model crosswalk.

    Resolution order:
      1. Per-model exact match (case-insensitive).
      2. Per-model wildcard ``"*"`` if present.
      3. Global default ``ROW``.

    Unrecognised ids that fall through to the default are logged once
    per ``(model_id, native_id)`` pair. An empty native id triggers the
    wildcard-only path; this is used by ``sectoral_dict`` extraction
    where the model is implicitly single-region.
    """
    crosswalk = load_region_crosswalk()
    model_map = crosswalk.get(model_id.lower(), {})
    if not native_region:
        return model_map.get("*", DEFAULT_UNIFIED)
    key = str(native_region).upper()
    if key in model_map:
        return model_map[key]
    star = model_map.get("*")
    if star:
        return star
    pair = (model_id, native_region)
    if pair not in _WARNED_UNMAPPED:
        _WARNED_UNMAPPED.add(pair)
        logger.info(
            "regional crosswalk: %s native id %r -> %s (default; "
            "add explicit mapping in configs/region_crosswalk.yaml to override)",
            model_id, native_region, DEFAULT_UNIFIED,
        )
    return DEFAULT_UNIFIED


# --------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------


def _coerce_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _value_cols_present(row: dict, value_cols: list[str]) -> list[str]:
    """Return the subset of ``value_cols`` that appear in ``row`` with a
    parseable numeric value. Falls back to *any* numeric column if none
    of the configured value_cols match."""
    hits = [c for c in value_cols if c in row and _coerce_float(row.get(c)) is not None]
    if hits:
        return hits
    return [
        c for c, v in row.items()
        if c not in value_cols and _coerce_float(v) is not None
    ]


def _extract_regional_list(
    model_id: str,
    output_key: str,
    rows: Any,
    spec: dict,
) -> list[RegionalRecord]:
    if not isinstance(rows, list):
        return []
    region_col = spec.get("region_col") or "region"
    value_cols = list(spec.get("value_cols") or [])
    out: list[RegionalRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        native = row.get(region_col)
        if native is None or native == "":
            continue
        cols = _value_cols_present(row, value_cols)
        for col in cols:
            v = _coerce_float(row.get(col))
            if v is None:
                continue
            out.append(RegionalRecord(
                model_id=model_id,
                output_key=output_key,
                native_region=str(native),
                unified_region=map_to_unified(model_id, str(native)),
                sector=None,
                value_label=col,
                value=v,
            ))
    return out


def _extract_regional_sectoral_list(
    model_id: str,
    output_key: str,
    rows: Any,
    spec: dict,
) -> list[RegionalRecord]:
    if not isinstance(rows, list):
        return []
    region_col = spec.get("region_col") or "region"
    sector_col = spec.get("sector_col") or "sector"
    value_cols = list(spec.get("value_cols") or [])
    out: list[RegionalRecord] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        native = row.get(region_col)
        sector = row.get(sector_col)
        if native is None or native == "":
            continue
        cols = _value_cols_present(row, value_cols)
        for col in cols:
            v = _coerce_float(row.get(col))
            if v is None:
                continue
            out.append(RegionalRecord(
                model_id=model_id,
                output_key=output_key,
                native_region=str(native),
                unified_region=map_to_unified(model_id, str(native)),
                sector=str(sector) if sector is not None else None,
                value_label=col,
                value=v,
            ))
    return out


def _extract_sectoral_dict(
    model_id: str,
    output_key: str,
    blob: Any,
    spec: dict,
) -> list[RegionalRecord]:
    if not isinstance(blob, dict):
        return []
    label = str(spec.get("value_label") or output_key)
    out: list[RegionalRecord] = []
    for sector, raw in blob.items():
        v = _coerce_float(raw)
        if v is None:
            continue
        out.append(RegionalRecord(
            model_id=model_id,
            output_key=output_key,
            native_region="",
            unified_region=map_to_unified(model_id, ""),
            sector=str(sector),
            value_label=label,
            value=v,
        ))
    return out


def _extract_polygon_dict(
    model_id: str,
    output_key: str,
    blob: Any,
    spec: dict,
) -> list[RegionalRecord]:
    """SahysMod-style ``{poly_id: {time_key: value}}`` -> latest time."""
    if not isinstance(blob, dict):
        return []
    label = str(spec.get("value_label") or output_key)
    out: list[RegionalRecord] = []
    for poly_id, series in blob.items():
        if isinstance(series, dict):
            if not series:
                continue
            try:
                latest_key = sorted(series.keys())[-1]
            except TypeError:
                latest_key = list(series.keys())[-1]
            v = _coerce_float(series.get(latest_key))
        else:
            v = _coerce_float(series)
        if v is None:
            continue
        out.append(RegionalRecord(
            model_id=model_id,
            output_key=output_key,
            native_region=str(poly_id),
            unified_region=map_to_unified(model_id, str(poly_id)),
            sector=None,
            value_label=label,
            value=v,
        ))
    return out


_EXTRACTORS = {
    "regional": _extract_regional_list,
    "regional_sectoral": _extract_regional_sectoral_list,
    "sectoral_dict": _extract_sectoral_dict,
    "regional_polygon_dict": _extract_polygon_dict,
}


def extract_regional_records(
    model_id: str,
    outputs: dict | None,
    spec: dict[str, Any] | None = None,
) -> list[RegionalRecord]:
    """Walk a model's ``outputs`` dict and return every distributional
    record described by the per-model section of
    ``configs/distributional_outputs.yaml``.

    Returns ``[]`` when the model has no spec section, or when the
    relevant keys are absent. Never raises on malformed values; rows
    that cannot be parsed are skipped.
    """
    if not outputs:
        return []
    full_spec = spec if spec is not None else load_distributional_spec()
    model_spec = full_spec.get(model_id) or full_spec.get(model_id.lower())
    if not isinstance(model_spec, dict):
        return []
    records: list[RegionalRecord] = []
    for output_key, key_spec in model_spec.items():
        if output_key.startswith("_"):
            continue
        if not isinstance(key_spec, dict):
            continue
        kind = key_spec.get("kind")
        extractor = _EXTRACTORS.get(kind)
        if extractor is None:
            continue
        blob = outputs.get(output_key)
        if blob is None:
            continue
        try:
            records.extend(extractor(model_id, output_key, blob, key_spec))
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "regional extraction failed for %s.%s: %s",
                model_id, output_key, exc,
            )
    return records


# --------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------


def _aggregator_for(
    model_id: str,
    output_key: str,
    value_label: str,
    overrides: dict[str, str],
) -> str:
    key_full = f"{model_id}.{output_key}.{value_label}"
    key_short = f"{model_id}.{output_key}"
    if key_full in overrides:
        return overrides[key_full]
    if key_short in overrides:
        return overrides[key_short]
    if value_label.endswith("_pct") or value_label.endswith("_pct_change"):
        return "mean"
    return "sum"


def _apply(values: list[float], op: str) -> float:
    if not values:
        return 0.0
    if op == "mean":
        return statistics.fmean(values)
    if op == "median":
        return statistics.median(values)
    if op == "max":
        return max(values)
    if op == "min":
        return min(values)
    return sum(values)


def aggregate_to_unified(
    records: Iterable[RegionalRecord],
    spec: dict[str, Any] | None = None,
) -> dict[tuple[str, str, str], dict[str, float]]:
    """Roll native records up to the unified taxonomy.

    Returns a dict keyed by ``(model_id, output_key, value_label)`` mapping
    each ``unified_region`` to an aggregated float. Aggregator (sum vs
    mean) is resolved per spec ``_aggregation_overrides``; default is
    mean for ``*_pct`` labels, sum otherwise.
    """
    full_spec = spec if spec is not None else load_distributional_spec()
    overrides_raw = full_spec.get("_aggregation_overrides") or {}
    overrides = {str(k): str(v).lower() for k, v in overrides_raw.items()}

    groups: dict[tuple[str, str, str, str], list[float]] = {}
    for r in records:
        groups.setdefault(
            (r.model_id, r.output_key, r.value_label, r.unified_region), []
        ).append(r.value)

    out: dict[tuple[str, str, str], dict[str, float]] = {}
    for (model_id, output_key, value_label, unified), vals in groups.items():
        op = _aggregator_for(model_id, output_key, value_label, overrides)
        out.setdefault((model_id, output_key, value_label), {})[unified] = _apply(vals, op)
    return out


def aggregate_sectoral(
    records: Iterable[RegionalRecord],
) -> dict[tuple[str, str, str], dict[str, float]]:
    """Roll up sector-bearing records, ignoring the regional dimension.

    Returns ``{(model_id, output_key, value_label): {sector: value}}``.
    Sector values are averaged across regions when both dimensions are
    present (so a regional_sectoral table collapses to a sector view).
    """
    groups: dict[tuple[str, str, str, str], list[float]] = {}
    for r in records:
        if r.sector is None:
            continue
        groups.setdefault(
            (r.model_id, r.output_key, r.value_label, r.sector), []
        ).append(r.value)
    out: dict[tuple[str, str, str], dict[str, float]] = {}
    for (model_id, output_key, value_label, sector), vals in groups.items():
        out.setdefault((model_id, output_key, value_label), {})[sector] = (
            statistics.fmean(vals) if vals else 0.0
        )
    return out


# --------------------------------------------------------------------
# Dispersion metrics (for prompt context)
# --------------------------------------------------------------------


def dispersion_metrics(
    records: Iterable[RegionalRecord],
    spec: dict[str, Any] | None = None,
) -> list[DispersionMetric]:
    """Per (model, output_key, value_label), summarise how widely the
    unified-region distribution varies. Sorted by descending range so
    the synthesizer prompt highlights the most asymmetric impacts first.
    """
    unified = aggregate_to_unified(records, spec=spec)
    out: list[DispersionMetric] = []
    for (model_id, output_key, value_label), region_vals in unified.items():
        if len(region_vals) < 2:
            continue
        items = sorted(region_vals.items(), key=lambda kv: kv[1])
        bottom_region, bottom_value = items[0]
        top_region, top_value = items[-1]
        vals = list(region_vals.values())
        try:
            stdev = statistics.pstdev(vals)
        except statistics.StatisticsError:
            stdev = 0.0
        out.append(DispersionMetric(
            model_id=model_id,
            output_key=output_key,
            value_label=value_label,
            n_regions=len(vals),
            min_value=min(vals),
            max_value=max(vals),
            mean_value=statistics.fmean(vals),
            stdev_value=stdev,
            top_region=top_region,
            top_value=top_value,
            bottom_region=bottom_region,
            bottom_value=bottom_value,
        ))
    out.sort(key=lambda m: m.range_value, reverse=True)
    return out


# --------------------------------------------------------------------
# Markdown renderers (used by the synthesizer prompt and the qualitative
# narrative prompt).
# --------------------------------------------------------------------


def render_regional_breakdowns(
    records_by_model: dict[str, list[RegionalRecord]],
    spec: dict[str, Any] | None = None,
    max_rows_per_table: int = 12,
) -> str:
    """Compact Markdown table per (model, output_key, value_label) of
    unified-region values. Returns ``"None."`` when no records.
    """
    if not records_by_model:
        return "None — no model in this scenario produced regional data."
    flat: list[RegionalRecord] = []
    for recs in records_by_model.values():
        flat.extend(r for r in recs if r.sector is None)
    if not flat:
        return "None — no model in this scenario produced regional data."
    unified = aggregate_to_unified(flat, spec=spec)
    parts: list[str] = []
    for (model_id, output_key, value_label), region_vals in sorted(unified.items()):
        items = sorted(region_vals.items(), key=lambda kv: kv[1])[:max_rows_per_table]
        parts.append(f"**{model_id} · {output_key} · {value_label}**")
        parts.append("")
        parts.append("| Unified region | Value |")
        parts.append("|---|---:|")
        for region, val in items:
            parts.append(f"| {region} | {val:g} |")
        parts.append("")
    return "\n".join(parts).rstrip()


def render_sectoral_breakdowns(
    records_by_model: dict[str, list[RegionalRecord]],
    max_rows_per_table: int = 12,
) -> str:
    if not records_by_model:
        return "None — no model in this scenario produced sectoral data."
    flat: list[RegionalRecord] = []
    for recs in records_by_model.values():
        flat.extend(r for r in recs if r.sector is not None)
    if not flat:
        return "None — no model in this scenario produced sectoral data."
    sectoral = aggregate_sectoral(flat)
    parts: list[str] = []
    for (model_id, output_key, value_label), sec_vals in sorted(sectoral.items()):
        items = sorted(sec_vals.items(), key=lambda kv: kv[1])[:max_rows_per_table]
        parts.append(f"**{model_id} · {output_key} · {value_label}**")
        parts.append("")
        parts.append("| Sector | Value |")
        parts.append("|---|---:|")
        for sector, val in items:
            parts.append(f"| {sector} | {val:g} |")
        parts.append("")
    return "\n".join(parts).rstrip()


def render_dispersion_summary(
    metrics: list[DispersionMetric],
    max_lines: int = 10,
) -> str:
    """One-line-per-metric summary of regional asymmetry, used in the
    qualitative narrative prompt so the LLM can call out winners and
    losers without us forwarding the full table."""
    if not metrics:
        return "(no regional dispersion detected for this model)"
    lines: list[str] = []
    for m in metrics[:max_lines]:
        lines.append(
            f"- {m.model_id}.{m.output_key}.{m.value_label}: "
            f"top {m.top_region}={m.top_value:g}, "
            f"bottom {m.bottom_region}={m.bottom_value:g}, "
            f"range={m.range_value:g}, stdev={m.stdev_value:g} "
            f"({m.n_regions} regions)"
        )
    return "\n".join(lines)
