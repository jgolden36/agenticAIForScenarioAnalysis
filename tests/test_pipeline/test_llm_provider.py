"""Provider construction for the backends used in the model comparison. No API calls."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.common.llm import _ANTHROPIC_NON_STREAMING_MAX_TOKENS, _create_provider


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.delenv("PIPELINE_LLM_OMIT_TEMPERATURE", raising=False)


class _Reply(BaseModel):
    answer: str


def test_groq_provider_requests_json_schema() -> None:
    llm = _create_provider("groq", "openai/gpt-oss-120b", 0.0, None, max_tokens=16000)
    assert llm.model_name == "openai/gpt-oss-120b"
    assert llm.max_tokens == 16000
    bound = llm.with_structured_output(_Reply).first
    assert bound.kwargs["response_format"]["type"] == "json_schema"
    assert "tools" not in bound.kwargs


def test_anthropic_streams_only_above_the_non_streaming_limit() -> None:
    small = _create_provider("anthropic", "claude-sonnet-4-6", 0.0, None, max_tokens=_ANTHROPIC_NON_STREAMING_MAX_TOKENS)
    large = _create_provider("anthropic", "claude-sonnet-4-6", 0.0, None, max_tokens=32000)
    assert small.streaming is False
    assert large.streaming is True
    assert large.max_tokens == 32000


def test_anthropic_temperature_is_sent_unless_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _create_provider("anthropic", "claude-sonnet-4-6", 0.0, None, max_tokens=1000).temperature == 0.0
    monkeypatch.setenv("PIPELINE_LLM_OMIT_TEMPERATURE", "1")
    assert _create_provider("anthropic", "claude-opus-4-8", 0.0, None, max_tokens=1000).temperature is None
