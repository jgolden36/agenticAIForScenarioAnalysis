"""One structured LLM call with its audit record.

``structured_call`` renders the prompt, hashes the rendered messages, asks the LLM for the
schema with ``with_structured_output`` (as ``src/scenarios/generator.py`` does), and returns
the parsed object with ``{provider, model, temperature, prompt_sha256, raw}``. Any failure,
from building the call to parsing the answer, raises :class:`LLMUnavailable`; the API turns it
into ``{"status": "unavailable", "reason"}``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError


class LLMUnavailable(RuntimeError):
    """The LLM could not be built, could not be called, or answered off-schema."""


@dataclass
class LLMHandle:
    llm: Any
    provider: str
    model: str
    temperature: float


def prompt_sha256(messages: list[Any]) -> str:
    rows = [[getattr(m, "type", type(m).__name__), getattr(m, "content", str(m))] for m in messages]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def structured_call(handle: LLMHandle, prompt: Any, variables: dict[str, Any], schema: type[BaseModel]
                    ) -> tuple[BaseModel, dict[str, Any]]:
    try:
        messages = prompt.format_messages(**variables)
    except Exception as e:  # noqa: BLE001  -- a template error is a service fault, reported, not raised
        raise LLMUnavailable(f"prompt could not be rendered: {type(e).__name__}: {e}") from e
    meta: dict[str, Any] = {"provider": handle.provider, "model": handle.model, "temperature": handle.temperature,
                            "prompt_sha256": prompt_sha256(messages), "raw": None}
    try:
        structured = handle.llm.with_structured_output(schema)
        raw = structured.invoke(messages)
    except Exception as e:  # noqa: BLE001  -- every provider failure becomes "unavailable"
        raise LLMUnavailable(f"LLM call failed: {type(e).__name__}: {str(e)[:300]}") from e
    try:
        parsed = raw if isinstance(raw, schema) else schema.model_validate(raw)
    except ValidationError as e:
        meta["raw"] = raw if isinstance(raw, (dict, list, str)) else repr(raw)
        raise LLMUnavailable(f"LLM output did not match {schema.__name__}: {str(e)[:300]}") from e
    meta["raw"] = parsed.model_dump(mode="json")
    return parsed, meta
