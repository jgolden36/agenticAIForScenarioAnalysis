"""Backwards-compatibility shim.

The implementation moved to ``src.pipeline.upstream_forwarding`` when
the merge mechanism was generalized to handle any upstream-to-
downstream level transition (not just commodity-to-macro). New code
should import from ``src.pipeline.upstream_forwarding`` directly; this
module re-exports the public symbols so that existing callers and
external scripts continue to work without modification.

The on-disk YAML config was likewise renamed from
``configs/upstream_to_macro_mapping.yaml`` to
``configs/upstream_forwarding_mapping.yaml``. ``default_mapping_path``
falls back to the legacy filename when the new one is absent, so the
file rename is also non-breaking.
"""

from __future__ import annotations

from src.pipeline.upstream_forwarding import (  # noqa: F401  (re-exports)
    ComputedShock,
    OverrideRecord,
    ParamMapping,
    SourceSpec,
    UpstreamMapping,
    clear_mapping_cache,
    compute_downstream_inputs,
    compute_macro_inputs,
    default_mapping_path,
    is_downstream_model_id,
    is_macro_model_id,
    load_mapping,
    merge_into_params,
    register_overrides_in_outputs,
)

__all__ = [
    "ComputedShock",
    "OverrideRecord",
    "ParamMapping",
    "SourceSpec",
    "UpstreamMapping",
    "clear_mapping_cache",
    "compute_downstream_inputs",
    "compute_macro_inputs",
    "default_mapping_path",
    "is_downstream_model_id",
    "is_macro_model_id",
    "load_mapping",
    "merge_into_params",
    "register_overrides_in_outputs",
]
