"""Upstream-to-downstream parameter forwarding (Algorithm 1, step 11).

Reads upstream model outputs and computes the downstream model input
shocks that should be injected in place of the values the LLM
extracted from the scenario narrative. Supports two transitions in
the level hierarchy today:

* COMMODITY -> COMMODITY_DOWNSTREAM
  e.g. ``world_helium_model.effective_supply_gap_pct`` is forwarded
  into ``simrlfab.helium_supply_reduction_pct`` and
  ``argonne_abm.supply_shock_pct`` so the semiconductor-fab and
  helium-market-ABM simulations consume the helium model's actual
  computed sectoral shortfall instead of an LLM estimate.

* COMMODITY (and COMMODITY_DOWNSTREAM) -> SHORT_RUN_MACRO /
  LONG_RUN_MACRO_STRATEGIC
  e.g. ``poles_jrc.peak_price_change_pct`` -> ``opencge.oil_price_shock_pct``,
  ``world_helium_model.price_change_pct`` -> ``opencge.commodity_price_shocks.helium``.

The mapping is declarative and lives in
``configs/upstream_forwarding_mapping.yaml`` so analysts can change it
without touching code. (The historical filename
``configs/upstream_to_macro_mapping.yaml`` is still honoured as a
fallback so existing checkouts keep working.)

The Replace-with-metadata policy applies: every replaced parameter
appends an entry to an ``_upstream_overrides`` list, recording the
original LLM value, the upstream-derived value, the source model and
field, the transform used, and the deviation in percent. Both the
local LangGraph orchestrator (``src/pipeline/graph.py``) and the
SLURM cluster scripts (``slurm/scripts/dispatch_models.py``,
``slurm/scripts/run_model.py``) call into the same functions here so
the merge logic stays identical across runtimes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.common.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceSpec:
    """One upstream source for a downstream input parameter."""

    source_model: str
    source_field: str
    transform: str = "identity"
    baseline: float | None = None
    keys: tuple[str, ...] = ()
    value_kind: str = "percent"


@dataclass(frozen=True)
class ParamMapping:
    """Mapping for one downstream input parameter (or one key of a dict-valued one).

    ``scenarios`` optionally restricts the rule to a subset of scenarios.
    Empty/None means "applies to every scenario" (the historical
    default). When set, the rule fires only for scenario ids in the
    list -- used e.g. to feed water-system shocks into macro models
    only under the prescribed ``infrastructure_collapse`` tail-risk
    scenario, where desalination/water-supply destruction is part of
    the narrative, while leaving the other four matrix scenarios
    unaffected.
    """

    target_param: str
    target_key: str | None
    sources: tuple[SourceSpec, ...]
    scenarios: tuple[str, ...] = ()


@dataclass
class UpstreamMapping:
    """Loaded mapping config: per-downstream-model parameter rules."""

    by_model: dict[str, list[ParamMapping]] = field(default_factory=dict)
    warn_threshold_pct: float = 50.0


@dataclass
class ComputedShock:
    """One upstream-derived value ready to be merged into downstream params."""

    target_param: str
    target_key: str | None
    value: float | list[float]
    source_model_id: str
    source_field: str
    transform: str


@dataclass
class OverrideRecord:
    """Audit trail for one replaced downstream parameter."""

    name: str
    target_key: str | None
    llm_value: Any
    computed_value: Any
    source_model_id: str
    source_field: str
    transform: str
    deviation_pct: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target_key": self.target_key,
            "llm_value": self.llm_value,
            "computed_value": self.computed_value,
            "source_model_id": self.source_model_id,
            "source_field": self.source_field,
            "transform": self.transform,
            "deviation_pct": self.deviation_pct,
        }


# ---------------------------------------------------------------------------
# Mapping loader
# ---------------------------------------------------------------------------


_DEFAULT_MAPPING_FILENAME = "upstream_forwarding_mapping.yaml"
_LEGACY_MAPPING_FILENAME = "upstream_to_macro_mapping.yaml"

_loaded_cache: dict[Path, UpstreamMapping] = {}


def default_mapping_path() -> Path:
    """Resolve ``configs/upstream_forwarding_mapping.yaml`` from the project root.

    Falls back to the legacy ``configs/upstream_to_macro_mapping.yaml``
    if the new filename does not exist, so unmigrated checkouts keep
    working.
    """
    root = Path(__file__).resolve().parents[2]
    new_path = root / "configs" / _DEFAULT_MAPPING_FILENAME
    if new_path.exists():
        return new_path
    legacy_path = root / "configs" / _LEGACY_MAPPING_FILENAME
    if legacy_path.exists():
        return legacy_path
    return new_path  # signal "not found" via .exists() at the call site


def load_mapping(path: Path | str | None = None) -> UpstreamMapping:
    """Load and cache the upstream-to-downstream mapping config.

    Args:
        path: Optional override path. Defaults to
            ``configs/upstream_forwarding_mapping.yaml`` under the
            project root, with a fallback to the legacy filename.

    Returns:
        UpstreamMapping. Returns an empty mapping (no overrides applied,
        graceful no-op) if the file does not exist or is malformed.
    """
    target = Path(path) if path is not None else default_mapping_path()

    cached = _loaded_cache.get(target)
    if cached is not None:
        return cached

    if not target.exists():
        logger.info(
            "upstream forwarding mapping not found at %s; merging will be a no-op",
            target,
        )
        empty = UpstreamMapping()
        _loaded_cache[target] = empty
        return empty

    try:
        with open(target) as f:
            raw = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning(
            "Failed to parse upstream forwarding mapping at %s: %s; merging disabled",
            target,
            exc,
        )
        empty = UpstreamMapping()
        _loaded_cache[target] = empty
        return empty

    mapping = _parse_mapping_dict(raw)
    _loaded_cache[target] = mapping
    logger.info(
        "Loaded upstream forwarding mapping from %s (%d downstream models, threshold=%.1f%%)",
        target,
        len(mapping.by_model),
        mapping.warn_threshold_pct,
    )
    return mapping


def clear_mapping_cache() -> None:
    """Drop cached mappings (used by tests)."""
    _loaded_cache.clear()


def _parse_mapping_dict(raw: dict[str, Any]) -> UpstreamMapping:
    """Convert the YAML dict into an :class:`UpstreamMapping`."""
    defaults = raw.get("defaults") or {}
    threshold = float(
        defaults.get("llm_vs_upstream_warn_threshold_pct", 50.0)
    )

    by_model: dict[str, list[ParamMapping]] = {}
    models = raw.get("models") or {}
    if not isinstance(models, dict):
        logger.warning("upstream forwarding mapping 'models' is not a dict; ignoring")
        return UpstreamMapping(by_model=by_model, warn_threshold_pct=threshold)

    for downstream_model_id, params in models.items():
        if not isinstance(params, dict):
            continue
        param_mappings: list[ParamMapping] = []
        for rule_name, rule_body in params.items():
            if not isinstance(rule_body, dict):
                continue
            target_param = rule_body.get("target_param", rule_name)
            target_key = rule_body.get("target_key")
            sources_raw = rule_body.get("sources") or []
            sources: list[SourceSpec] = []
            for s in sources_raw:
                if not isinstance(s, dict):
                    continue
                if not s.get("source_model") or not s.get("source_field"):
                    continue
                sources.append(
                    SourceSpec(
                        source_model=str(s["source_model"]),
                        source_field=str(s["source_field"]),
                        transform=str(s.get("transform", "identity")),
                        baseline=(
                            float(s["baseline"])
                            if s.get("baseline") is not None
                            else None
                        ),
                        keys=tuple(s.get("keys") or ()),
                        value_kind=str(s.get("value_kind", "percent")),
                    )
                )
            scenarios_raw = rule_body.get("scenarios") or ()
            if isinstance(scenarios_raw, str):
                scenarios_tuple: tuple[str, ...] = (scenarios_raw,)
            elif isinstance(scenarios_raw, (list, tuple)):
                scenarios_tuple = tuple(str(s) for s in scenarios_raw)
            else:
                scenarios_tuple = ()
            param_mappings.append(
                ParamMapping(
                    target_param=str(target_param),
                    target_key=str(target_key) if target_key is not None else None,
                    sources=tuple(sources),
                    scenarios=scenarios_tuple,
                )
            )
        by_model[str(downstream_model_id)] = param_mappings

    return UpstreamMapping(by_model=by_model, warn_threshold_pct=threshold)


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


def _apply_transform(spec: SourceSpec, raw_value: Any) -> float | list[float] | None:
    """Apply ``spec.transform`` to ``raw_value``. Returns None on failure."""
    transform = spec.transform

    if transform == "identity":
        return _coerce_numeric_or_list(raw_value)

    if transform == "to_percent":
        coerced = _coerce_numeric_or_list(raw_value)
        if coerced is None:
            return None
        if isinstance(coerced, list):
            return [v * 100.0 for v in coerced]
        return coerced * 100.0

    if transform == "level_to_pct":
        if spec.baseline is None or spec.baseline == 0:
            logger.warning(
                "level_to_pct transform requires a non-zero baseline; got %r for %s.%s",
                spec.baseline,
                spec.source_model,
                spec.source_field,
            )
            return None
        coerced = _coerce_numeric_or_list(raw_value)
        if coerced is None:
            return None
        baseline = float(spec.baseline)
        if isinstance(coerced, list):
            return [(v / baseline - 1.0) * 100.0 for v in coerced]
        return (coerced / baseline - 1.0) * 100.0

    if transform == "mean_of_keys":
        if not isinstance(raw_value, dict):
            return None
        keys = spec.keys or tuple(raw_value.keys())
        values: list[float] = []
        for k in keys:
            sub = raw_value.get(k)
            if sub is None:
                continue
            try:
                values.append(float(sub))
            except (TypeError, ValueError):
                continue
        if not values:
            return None
        mean = sum(values) / len(values)
        if spec.value_kind == "index":
            return (mean - 1.0) * 100.0
        if spec.value_kind == "level":
            if spec.baseline is None or spec.baseline == 0:
                logger.warning(
                    "mean_of_keys with value_kind=level requires baseline; got %r",
                    spec.baseline,
                )
                return None
            return (mean / float(spec.baseline) - 1.0) * 100.0
        return mean

    logger.warning("Unknown transform %r; ignoring source", transform)
    return None


def _coerce_numeric_or_list(value: Any) -> float | list[float] | None:
    """Coerce a value into a float or list[float]; return None if impossible."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        out: list[float] = []
        for v in value:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
            else:
                return None
        return out
    return None


# ---------------------------------------------------------------------------
# Compute upstream-derived shocks from upstream-tier results
# ---------------------------------------------------------------------------


def _result_outputs(result: Any) -> dict[str, Any] | None:
    """Pull outputs dict + status from a ModelExecutionResult or dict-shaped result."""
    if result is None:
        return None
    if isinstance(result, dict):
        status = str(result.get("status", "")).lower()
        if status not in ("completed", ""):
            return None
        outputs = result.get("outputs") or {}
        if isinstance(outputs, dict):
            return outputs
        return None
    status = getattr(result, "status", None)
    status_value = getattr(status, "value", status)
    if status_value is not None and str(status_value).lower() != "completed":
        return None
    outputs = getattr(result, "outputs", None)
    if isinstance(outputs, dict):
        return outputs
    return None


def _result_scenario_id(result: Any) -> str | None:
    """Extract the scenario_id of a result (handles enum and string forms)."""
    if result is None:
        return None
    if isinstance(result, dict):
        sid = result.get("scenario_id")
    else:
        sid = getattr(result, "scenario_id", None)
    if sid is None:
        return None
    return getattr(sid, "value", str(sid))


def _result_model_id(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, dict):
        return result.get("model_id")
    return getattr(result, "model_id", None)


def compute_downstream_inputs(
    scenario_id: str,
    upstream_results: list[Any],
    mapping: UpstreamMapping,
    target_models: list[str] | set[str] | None = None,
) -> dict[str, list[ComputedShock]]:
    """Compute per-downstream-model upstream-derived shocks for one scenario.

    Args:
        scenario_id: The scenario the upstream results belong to.
        upstream_results: List of ``ModelExecutionResult`` (Pydantic) or
            dict-shaped equivalents from completed upstream stages.
            Non-COMPLETED runs are silently skipped.
        mapping: Loaded mapping config.
        target_models: Optional restriction. When provided, only rules
            whose downstream-model id is in this set are evaluated -- used
            by the orchestrator and SLURM dispatcher to scope the merge
            to a specific tier (e.g. only the COMMODITY_DOWNSTREAM models
            during the first barrier, only the macro models during the
            second). When ``None`` (default), every downstream model in
            the mapping is considered.

    Returns:
        Dict ``{downstream_model_id: [ComputedShock, ...]}``. Models
        with no successful upstream sources do not appear in the dict.
    """
    by_source: dict[str, dict[str, Any]] = {}
    for r in upstream_results:
        if _result_scenario_id(r) != scenario_id:
            continue
        outputs = _result_outputs(r)
        mid = _result_model_id(r)
        if outputs is None or not mid:
            continue
        by_source[mid] = outputs

    target_set: set[str] | None = (
        set(target_models) if target_models is not None else None
    )

    out: dict[str, list[ComputedShock]] = {}
    for downstream_model_id, rules in mapping.by_model.items():
        if target_set is not None and downstream_model_id not in target_set:
            continue
        shocks: list[ComputedShock] = []
        for rule in rules:
            # Honour per-rule scenario filters: an empty `scenarios`
            # tuple means "all scenarios" (back-compat default); a
            # non-empty tuple restricts the rule to its listed ids.
            if rule.scenarios and scenario_id not in rule.scenarios:
                continue
            shock = _resolve_rule(rule, by_source)
            if shock is not None:
                shocks.append(shock)
        if shocks:
            out[downstream_model_id] = shocks
    return out


# Backwards-compat alias (the previous name used to be macro-specific).
compute_macro_inputs = compute_downstream_inputs


def _resolve_rule(
    rule: ParamMapping,
    outputs_by_source: dict[str, dict[str, Any]],
) -> ComputedShock | None:
    """Walk ``rule.sources`` in order; return the first successful match."""
    for src in rule.sources:
        outputs = outputs_by_source.get(src.source_model)
        if outputs is None:
            continue
        raw = outputs.get(src.source_field)
        if raw is None:
            continue
        value = _apply_transform(src, raw)
        if value is None:
            continue
        return ComputedShock(
            target_param=rule.target_param,
            target_key=rule.target_key,
            value=value,
            source_model_id=src.source_model,
            source_field=src.source_field,
            transform=src.transform,
        )
    return None


# ---------------------------------------------------------------------------
# Merge into downstream params (Replace-with-metadata)
# ---------------------------------------------------------------------------


def _llm_value_for(
    llm_params: dict[str, Any], shock: ComputedShock
) -> Any:
    """Look up the LLM-extracted value the shock will replace."""
    if shock.target_key is None:
        return llm_params.get(shock.target_param)
    parent = llm_params.get(shock.target_param)
    if isinstance(parent, dict):
        return parent.get(shock.target_key)
    return None


def _deviation_pct(llm_value: Any, computed: Any) -> float | None:
    """Symmetric percent deviation between two scalars; None for non-numerics."""
    try:
        a = float(llm_value)
    except (TypeError, ValueError):
        return None
    try:
        b = float(computed)
    except (TypeError, ValueError):
        return None
    avg = (abs(a) + abs(b)) / 2.0
    if avg == 0:
        return 0.0
    return abs(a - b) / avg * 100.0


def merge_into_params(
    downstream_model_id: str,
    llm_params: dict[str, Any],
    computed: list[ComputedShock],
) -> tuple[dict[str, Any], list[OverrideRecord]]:
    """Replace LLM-extracted shocks with upstream-computed values.

    Replace-with-metadata policy: every replaced field appends a
    record to the returned ``override_records`` list. LLM values are
    preserved for any parameter (or sub-key of a dict-valued
    parameter) that no upstream source resolved.

    Args:
        downstream_model_id: Downstream model id (used only for logging).
        llm_params: The original LLM-extracted parameter dict for the
            (scenario, downstream_model) pair. NOT mutated.
        computed: Upstream-derived shocks for this downstream model.

    Returns:
        Tuple ``(merged_params, override_records)``.
    """
    merged: dict[str, Any] = dict(llm_params)
    records: list[OverrideRecord] = []

    for shock in computed:
        llm_value = _llm_value_for(merged, shock)
        deviation = _deviation_pct(llm_value, shock.value)

        if shock.target_key is None:
            merged[shock.target_param] = shock.value
        else:
            parent = merged.get(shock.target_param)
            if not isinstance(parent, dict):
                parent = {}
            else:
                parent = dict(parent)
            parent[shock.target_key] = shock.value
            merged[shock.target_param] = parent

        records.append(
            OverrideRecord(
                name=shock.target_param,
                target_key=shock.target_key,
                llm_value=llm_value,
                computed_value=shock.value,
                source_model_id=shock.source_model_id,
                source_field=shock.source_field,
                transform=shock.transform,
                deviation_pct=deviation,
            )
        )
        logger.info(
            "[%s] override %s%s = %s (was %r) from %s.%s [%s] deviation=%s",
            downstream_model_id,
            shock.target_param,
            f"[{shock.target_key}]" if shock.target_key else "",
            shock.value,
            llm_value,
            shock.source_model_id,
            shock.source_field,
            shock.transform,
            f"{deviation:.1f}%" if deviation is not None else "n/a",
        )

    return merged, records


# ---------------------------------------------------------------------------
# Helpers used by both the local graph and the SLURM scripts
# ---------------------------------------------------------------------------


def register_overrides_in_outputs(
    outputs: dict[str, Any], override_records: list[OverrideRecord] | list[dict[str, Any]]
) -> dict[str, Any]:
    """Attach ``_upstream_overrides`` to a model output dict.

    Accepts either :class:`OverrideRecord` instances or pre-serialised
    dicts so that callers reading back persisted manifests don't have
    to re-instantiate the dataclass.
    """
    if not override_records:
        return outputs
    serialised: list[dict[str, Any]] = []
    for rec in override_records:
        if isinstance(rec, OverrideRecord):
            serialised.append(rec.to_dict())
        elif isinstance(rec, dict):
            serialised.append(rec)
    outputs = dict(outputs) if outputs else {}
    outputs["_upstream_overrides"] = serialised
    return outputs


def is_downstream_model_id(
    model_id: str, mapping: UpstreamMapping | None = None
) -> bool:
    """Return True if ``model_id`` has any upstream-to-downstream rules."""
    mp = mapping or load_mapping()
    return model_id in mp.by_model


# Backwards-compat alias.
is_macro_model_id = is_downstream_model_id
