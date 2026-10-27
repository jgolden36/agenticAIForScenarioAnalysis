"""Tests for ImplementationMode resolution from adapter outputs."""

from src.common.types import AnalyticalLevel, CommoditySystem, ImplementationMode
from src.models.base import (
    ImplementationInfo,
    ModelAdapter,
    ModelOutput,
    ValidationResult,
    normalize_mode_token,
    resolve_implementation_mode,
)


class _Adapter(ModelAdapter):
    def __init__(self, info: ImplementationInfo | None = None):
        self._info = info

    @property
    def model_id(self):
        return "x"

    @property
    def commodity_system(self):
        return CommoditySystem.OIL

    @property
    def analytical_level(self):
        return AnalyticalLevel.COMMODITY

    @property
    def description(self):
        return "x"

    @property
    def implementation_info(self):
        return self._info or ImplementationInfo()

    def validate_inputs(self, params):
        return ValidationResult(valid=True)

    def translate_inputs(self, params):
        return params

    def execute(self, inputs):
        return ModelOutput(model_id="x")

    def parse_outputs(self, raw):
        return raw


def test_normalize_tokens():
    assert normalize_mode_token("analytical_mvp") == ImplementationMode.ANALYTICAL_REDUCTION
    assert normalize_mode_token("Analytical-MVP") == ImplementationMode.ANALYTICAL_REDUCTION
    assert normalize_mode_token("aeo_ingestion") == ImplementationMode.PUBLISHED_OUTPUT_INGESTION
    assert normalize_mode_token("output_ingestion") == ImplementationMode.PUBLISHED_OUTPUT_INGESTION
    assert normalize_mode_token("subprocess") == ImplementationMode.FULL_UPSTREAM
    assert normalize_mode_token("python") == ImplementationMode.FULL_UPSTREAM
    assert normalize_mode_token("eviews_subprocess") == ImplementationMode.FULL_UPSTREAM
    assert normalize_mode_token("something_else") is None
    assert normalize_mode_token(None) is None


def test_resolve_prefers_metadata_mode():
    out = ModelOutput(model_id="x", outputs={}, metadata={"mode": "analytical_mvp"})
    assert resolve_implementation_mode(out) == ImplementationMode.ANALYTICAL_REDUCTION


def test_resolve_uses_engine_key():
    out = ModelOutput(model_id="x", outputs={}, metadata={"engine": "python"})
    assert resolve_implementation_mode(out) == ImplementationMode.FULL_UPSTREAM


def test_resolve_uses_output_markers():
    out = ModelOutput(model_id="x", outputs={"_execution_mode": "analytical_mvp"})
    assert resolve_implementation_mode(out) == ImplementationMode.ANALYTICAL_REDUCTION
    out = ModelOutput(model_id="x", outputs={"_used_analytical_mvp": True})
    assert resolve_implementation_mode(out) == ImplementationMode.ANALYTICAL_REDUCTION
    out = ModelOutput(model_id="x", outputs={"_macro_source": "mpsge_jl_kernel_fallback"})
    assert resolve_implementation_mode(out) == ImplementationMode.ANALYTICAL_REDUCTION
    out = ModelOutput(model_id="x", outputs={"_execution_mode": "cge_modeling"})
    assert resolve_implementation_mode(out) == ImplementationMode.FULL_UPSTREAM


def test_resolve_falls_back_to_adapter_declaration_then_unknown():
    out = ModelOutput(model_id="x", outputs={"y": 1.0})
    assert resolve_implementation_mode(out) == ImplementationMode.UNKNOWN
    assert resolve_implementation_mode(out, _Adapter()) == ImplementationMode.UNKNOWN
    declared = _Adapter(ImplementationInfo(mode_when_executed=ImplementationMode.FULL_UPSTREAM))
    assert resolve_implementation_mode(out, declared) == ImplementationMode.FULL_UPSTREAM
    # Explicit markers win over the declaration.
    out2 = ModelOutput(model_id="x", outputs={}, metadata={"mode": "analytical_mvp"})
    assert resolve_implementation_mode(out2, declared) == ImplementationMode.ANALYTICAL_REDUCTION


def test_resolve_from_outputs_dict_only():
    assert resolve_implementation_mode(None, None, outputs={"_execution_mode": "analytical_mvp"}) == ImplementationMode.ANALYTICAL_REDUCTION
    assert resolve_implementation_mode(None, None, outputs={}) == ImplementationMode.UNKNOWN
