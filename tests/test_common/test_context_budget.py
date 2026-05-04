"""Tests for the LLM context-budgeting helpers (src.common.context_budget)."""

from __future__ import annotations

import pytest

from src.common import context_budget as cb


# --------------------------------------------------------------------
# Budget resolution
# --------------------------------------------------------------------


def _clear_budget_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "PIPELINE_LLM_CONTEXT_WINDOW",
        "PIPELINE_LLM_PROMPT_BUDGET_TOKENS",
        "PIPELINE_LLM_MAX_COMPLETION_TOKENS",
        "PIPELINE_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


def test_get_context_window_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_CONTEXT_WINDOW", "16384")
    assert cb.get_context_window() == 16384


def test_get_context_window_uses_model_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    assert cb.get_context_window() == 131072


def test_get_context_window_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_MODEL", "totally-unknown-model")
    assert cb.get_context_window() == cb._FALLBACK_CONTEXT_WINDOW


def test_get_prompt_budget_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_PROMPT_BUDGET_TOKENS", "5000")
    assert cb.get_prompt_budget_tokens() == 5000


def test_get_prompt_budget_derives_from_window(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_CONTEXT_WINDOW", "10000")
    # 70% of 10000 = 7000.
    assert cb.get_prompt_budget_tokens() == 7000


def test_get_completion_budget_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_MAX_COMPLETION_TOKENS", "2048")
    assert cb.get_completion_budget_tokens() == 2048


def test_get_completion_budget_derives_from_window(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_CONTEXT_WINDOW", "20000")
    # 25% of 20000 = 5000.
    assert cb.get_completion_budget_tokens() == 5000


def test_invalid_env_var_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_CONTEXT_WINDOW", "not-a-number")
    assert cb.get_context_window() == cb._FALLBACK_CONTEXT_WINDOW


# --------------------------------------------------------------------
# Token counting
# --------------------------------------------------------------------


def test_count_tokens_empty_returns_zero() -> None:
    assert cb.count_tokens("") == 0


def test_count_tokens_short_string_is_positive() -> None:
    assert cb.count_tokens("hello world") >= 1


def test_count_tokens_scales_roughly_with_length() -> None:
    short = cb.count_tokens("hello world")
    long = cb.count_tokens("hello world " * 100)
    assert long > short * 50  # generous lower bound


def test_count_tokens_char_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the tiktoken-unavailable path and confirm len//4 rounding up."""
    # Clear any cached tiktoken encodings *before* patching so the patch
    # actually wins for the duration of the test.
    cb._get_tiktoken_encoding.cache_clear()
    monkeypatch.setattr(cb, "_get_tiktoken_encoding", lambda model=None: None)
    # 1 char -> 1 token (rounded up from len//4 = 0).
    assert cb.count_tokens("x") == 1
    # 4 chars -> 1 token.
    assert cb.count_tokens("xxxx") == 1
    # 5 chars -> 2 tokens ((5+3)/4 = 2).
    assert cb.count_tokens("xxxxx") == 2


# --------------------------------------------------------------------
# Truncation
# --------------------------------------------------------------------


def test_truncate_to_budget_passthrough_when_under() -> None:
    text = "short text"
    out = cb.truncate_to_budget(text, max_tokens=1000)
    assert out == text


def test_truncate_to_budget_shortens_when_over() -> None:
    text = "word " * 1000
    out = cb.truncate_to_budget(text, max_tokens=20)
    assert len(out) < len(text)
    assert "[truncated for context budget]" in out


def test_truncate_to_budget_zero_budget_passthrough() -> None:
    text = "hello"
    assert cb.truncate_to_budget(text, max_tokens=0) == text


def test_truncate_to_budget_empty_text() -> None:
    assert cb.truncate_to_budget("", max_tokens=10) == ""


def test_truncate_to_budget_with_custom_marker() -> None:
    text = "x" * 5000
    out = cb.truncate_to_budget(text, max_tokens=10, marker="--CUT--")
    assert out.endswith("--CUT--")


# --------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------


def test_chunk_to_budget_packs_under_limit() -> None:
    items = ["alpha", "beta", "gamma", "delta"]
    chunks = cb.chunk_to_budget(items, max_tokens=1000)
    assert len(chunks) == 1
    assert chunks[0] == items


def test_chunk_to_budget_splits_when_over() -> None:
    items = ["word " * 50 for _ in range(8)]
    chunks = cb.chunk_to_budget(items, max_tokens=80)
    assert len(chunks) > 1
    assert sum(len(c) for c in chunks) == 8


def test_chunk_to_budget_skips_empty_items() -> None:
    items = ["alpha", "", "beta", None]  # type: ignore[list-item]
    chunks = cb.chunk_to_budget([i for i in items if i is not None], max_tokens=1000)
    flat = [item for chunk in chunks for item in chunk]
    assert flat == ["alpha", "beta"]


def test_chunk_to_budget_oversize_item_gets_own_chunk() -> None:
    items = ["small", "huge " * 10000, "tiny"]
    chunks = cb.chunk_to_budget(items, max_tokens=100)
    # The huge item must be in its own chunk; the surrounding small/tiny
    # items may share one chunk or be separate but the huge one is alone.
    huge_chunks = [c for c in chunks if any("huge" in i for i in c)]
    assert len(huge_chunks) == 1
    assert len(huge_chunks[0]) == 1


# --------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------


def test_budget_snapshot_returns_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_budget_env(monkeypatch)
    monkeypatch.setenv("PIPELINE_LLM_CONTEXT_WINDOW", "16384")
    snap = cb.budget_snapshot()
    assert snap["context_window"] == 16384
    assert "prompt_budget_tokens" in snap
    assert "completion_budget_tokens" in snap
    assert "tiktoken_available" in snap
