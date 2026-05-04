"""Pydantic schemas for extracted parameters (Module 2).

The ``ExtractedParameter`` schema enforces type-level guarantees on the
LLM-extracted values so that downstream adapter validators (which expect
strict numerics, percentages, booleans, etc.) do not all simultaneously
fail when the LLM returns ``null`` or a free-text string for a required
numeric field.

Supported ``expected_type`` values (mirrors the ``"type"`` annotation in
``src/parameters/model_specs/*.py``):

- ``number``               — any finite numeric value (int / float)
- ``non_negative_number``  — numeric, ``value >= 0``
- ``positive_number``      — numeric, ``value > 0``
- ``percent``              — numeric in ``[0, 100]``
- ``boolean``              — bool (coerced from ``true/false/0/1`` etc.)
- ``string``               — free text / categorical label
- ``list``                 — list / sequence
- ``dict``                 — dict / structured object
- ``any``                  — no constraint (default; preserves old behavior)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.common.types import ConfidenceLevel, Scenario

ExpectedType = Literal[
    "any",
    "number",
    "non_negative_number",
    "positive_number",
    "percent",
    "boolean",
    "string",
    "list",
    "dict",
]

NUMERIC_TYPES: frozenset[str] = frozenset(
    {"number", "non_negative_number", "positive_number", "percent"}
)


def _coerce_number(value: Any) -> float | None:
    """Best-effort coercion of LLM output to a float.

    Handles:
    - ``int`` / ``float`` pass-through
    - decimal strings ``"3.14"`` and ``"-2"``
    - strings with a trailing unit-letter (``"1.5x"``, ``"5%"``,
      ``"30 mb/d"``) — extracts the leading numeric token
    - bool-as-number (rejected; ``True``/``False`` are not numerics here)

    Returns ``None`` if no numeric value can be recovered.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            pass
        import re
        m = re.match(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return None
    return None


def _coerce_bool(value: Any) -> bool | None:
    """Coerce LLM output to ``bool`` from common true/false representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"true", "yes", "y", "1", "t"}:
            return True
        if s in {"false", "no", "n", "0", "f"}:
            return False
    return None


class ExtractedParameter(BaseModel):
    """A single parameter extracted from a scenario narrative.

    The LLM is permitted to return ``value`` as any JSON type, but the
    ``model_validator`` below coerces and validates it against the
    declared ``expected_type``. Validation failures raise ``ValueError``,
    which surfaces to LangChain's structured-output retry loop as well as
    the explicit re-prompt loop in :mod:`src.parameters.extractor`.
    """

    name: str
    value: Any
    unit: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    directly_stated: bool = True
    extraction_note: str = ""
    expected_type: ExpectedType = "any"

    @model_validator(mode="after")
    def _enforce_expected_type(self) -> "ExtractedParameter":
        et = self.expected_type
        v = self.value

        if et == "any":
            return self

        if v is None:
            raise ValueError(
                f"Parameter '{self.name}' has expected_type={et!r} but value is null. "
                "Provide a best-effort numeric/string estimate; if truly unknown, "
                "leave the parameter out rather than emitting null."
            )

        if et in NUMERIC_TYPES:
            num = _coerce_number(v)
            if num is None:
                raise ValueError(
                    f"Parameter '{self.name}' (expected_type={et!r}) value "
                    f"{v!r} is not numeric and could not be coerced to a number."
                )
            if et == "non_negative_number" and num < 0:
                raise ValueError(
                    f"Parameter '{self.name}' (expected_type={et!r}) must be "
                    f">= 0; got {num}."
                )
            if et == "positive_number" and num <= 0:
                raise ValueError(
                    f"Parameter '{self.name}' (expected_type={et!r}) must be "
                    f"> 0; got {num}."
                )
            if et == "percent" and not (0.0 <= num <= 100.0):
                raise ValueError(
                    f"Parameter '{self.name}' (expected_type={et!r}) must be "
                    f"in [0, 100]; got {num}."
                )
            object.__setattr__(self, "value", num)
            return self

        if et == "boolean":
            b = _coerce_bool(v)
            if b is None:
                raise ValueError(
                    f"Parameter '{self.name}' (expected_type='boolean') value "
                    f"{v!r} is not a recognized boolean."
                )
            object.__setattr__(self, "value", b)
            return self

        if et == "string":
            object.__setattr__(self, "value", str(v))
            return self

        if et == "list":
            if isinstance(v, list):
                return self
            if isinstance(v, tuple):
                object.__setattr__(self, "value", list(v))
                return self
            if isinstance(v, str):
                # Permissive fallback: accept comma-separated strings as lists
                items = [tok.strip() for tok in v.split(",") if tok.strip()]
                object.__setattr__(self, "value", items)
                return self
            raise ValueError(
                f"Parameter '{self.name}' (expected_type='list') value "
                f"{v!r} is not a list."
            )

        if et == "dict":
            if isinstance(v, dict):
                return self
            raise ValueError(
                f"Parameter '{self.name}' (expected_type='dict') value "
                f"{v!r} is not an object/dict."
            )

        return self


class ModelParameterExtraction(BaseModel):
    """Parameters extracted for a specific (scenario, model) pair."""

    scenario_id: Scenario
    model_id: str
    parameters: list[ExtractedParameter] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParameterExtractionSet(BaseModel):
    """All extracted parameters for all (scenario, model) pairs."""

    extractions: list[ModelParameterExtraction] = Field(default_factory=list)
