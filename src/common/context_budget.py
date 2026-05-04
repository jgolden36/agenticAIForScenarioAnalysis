"""LLM context-window budgeting helpers.

Centralises the "how big is the served context window?" and "how many
tokens am I about to send?" questions so every LLM call site (Module 4
synthesis, Module 5/Stage 5 qualitative export, future modules) can
agree on the same budget without hard-coding character heuristics.

Three layers cooperate:

1. **The SLURM driver** (e.g. ``slurm/jobs/stonybrook_ai_cluster.job``)
   exports three env vars based on which model vLLM actually loaded
   (or which cloud provider is in use):

   - ``PIPELINE_LLM_CONTEXT_WINDOW``       — total tokens vLLM/provider
                                              will accept per request.
   - ``PIPELINE_LLM_PROMPT_BUDGET_TOKENS`` — soft cap on prompt portion.
   - ``PIPELINE_LLM_MAX_COMPLETION_TOKENS`` — soft cap on completion.

2. **This module** reads those env vars (with sane fallbacks derived
   from ``PIPELINE_LLM_MODEL`` when env vars are missing) and exposes
   ``count_tokens`` / ``truncate_to_budget`` / ``chunk_to_budget`` so
   any prompt-builder can stay under budget *before* hitting the wire.

3. **The LLM client** (``src/common/llm.py``) caps generated
   completions via ``max_tokens`` and wraps providers with a defensive
   retry that halves the prompt and re-invokes once on a
   "maximum context length" error.

Token counting prefers ``tiktoken`` (cl100k_base for OpenAI / vLLM,
o200k_base for gpt-4o, llama tokenizer when available). Falls back to
``len(text) // 4`` — which is a reasonable upper bound for English
text — when tiktoken is unavailable so the helper is import-safe even
in minimal environments.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Iterable

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Defaults — used when env vars are unset and we can still guess from
# PIPELINE_LLM_MODEL. Conservative on purpose: better to under-budget
# than to push a request that vLLM rejects with HTTP 400.
# --------------------------------------------------------------------

_FALLBACK_CONTEXT_WINDOW = 8192

_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # Anthropic
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-sonnet-20240620": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "claude-3-opus-20240229": 200000,
    # OpenAI
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-2024-04-09": 128000,
    # Llama (vLLM)
    "meta-llama/Llama-3.1-8B-Instruct": 131072,
    "meta-llama/Llama-3.1-70B-Instruct": 131072,
    "meta-llama/Llama-3.1-405B-Instruct": 131072,
    "meta-llama/Llama-3.2-1B-Instruct": 131072,
    "meta-llama/Llama-3.2-3B-Instruct": 131072,
    "meta-llama/Llama-3.3-70B-Instruct": 131072,
    # Mistral
    "mistralai/Mistral-7B-Instruct-v0.3": 32768,
    "mistralai/Mixtral-8x7B-Instruct-v0.1": 32768,
    # Qwen
    "Qwen/Qwen2.5-7B-Instruct": 32768,
    "Qwen/Qwen2.5-72B-Instruct": 32768,
}

# Split: ~70% prompt, ~25% completion, ~5% headroom for chat template
# overhead, structured-output schema descriptions, and tokeniser drift.
_DEFAULT_PROMPT_FRACTION = 0.70
_DEFAULT_COMPLETION_FRACTION = 0.25


def _env_int(name: str) -> int | None:
    """Read a positive int env var; return None on missing/invalid."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        val = int(raw.strip())
        return val if val > 0 else None
    except ValueError:
        logger.warning(f"{name} is set to {raw!r} but is not a valid int; ignoring.")
        return None


def get_context_window() -> int:
    """Return the total context window served by the current LLM.

    Resolution order:

    1. ``PIPELINE_LLM_CONTEXT_WINDOW`` env var (set by the SLURM driver).
    2. Lookup of ``PIPELINE_LLM_MODEL`` in ``_MODEL_CONTEXT_WINDOWS``.
    3. ``_FALLBACK_CONTEXT_WINDOW`` (8192).
    """
    env = _env_int("PIPELINE_LLM_CONTEXT_WINDOW")
    if env is not None:
        return env
    model = os.environ.get("PIPELINE_LLM_MODEL", "").strip()
    if model and model in _MODEL_CONTEXT_WINDOWS:
        return _MODEL_CONTEXT_WINDOWS[model]
    return _FALLBACK_CONTEXT_WINDOW


def get_prompt_budget_tokens() -> int:
    """Return the soft cap on the prompt portion of an LLM request.

    Resolution order:

    1. ``PIPELINE_LLM_PROMPT_BUDGET_TOKENS`` env var.
    2. ``get_context_window() * _DEFAULT_PROMPT_FRACTION``.
    """
    env = _env_int("PIPELINE_LLM_PROMPT_BUDGET_TOKENS")
    if env is not None:
        return env
    return max(1024, int(get_context_window() * _DEFAULT_PROMPT_FRACTION))


def get_completion_budget_tokens() -> int:
    """Return the soft cap on the completion portion of an LLM request.

    Resolution order:

    1. ``PIPELINE_LLM_MAX_COMPLETION_TOKENS`` env var.
    2. ``get_context_window() * _DEFAULT_COMPLETION_FRACTION``.
    """
    env = _env_int("PIPELINE_LLM_MAX_COMPLETION_TOKENS")
    if env is not None:
        return env
    return max(512, int(get_context_window() * _DEFAULT_COMPLETION_FRACTION))


# --------------------------------------------------------------------
# Token counting
# --------------------------------------------------------------------


@lru_cache(maxsize=8)
def _get_tiktoken_encoding(model: str | None):
    """Cache tiktoken encodings; return None if tiktoken is unavailable."""
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None

    name = (model or "").strip()
    try:
        if name and name.startswith(("gpt-4o", "o1", "o3")):
            return tiktoken.get_encoding("o200k_base")
        if name:
            try:
                return tiktoken.encoding_for_model(name)
            except KeyError:
                pass
        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"tiktoken init failed for model={name!r}: {exc}")
        return None


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens in ``text`` for the given model.

    Uses tiktoken when available (cl100k_base by default; o200k_base
    for gpt-4o family). Falls back to ``len(text) // 4`` rounded up,
    which is a reasonable upper bound for English text and a safe
    over-estimate for code / JSON.
    """
    if not text:
        return 0
    enc = _get_tiktoken_encoding(model or os.environ.get("PIPELINE_LLM_MODEL"))
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"tiktoken encode failed: {exc}; using char fallback")
    # Char-based fallback: 4 chars per token is the usual rule of thumb
    # for English; round up so a 1-char string counts as 1 token.
    return (len(text) + 3) // 4


# --------------------------------------------------------------------
# Truncation / chunking
# --------------------------------------------------------------------


_DEFAULT_TRUNCATION_MARKER = "\n... [truncated for context budget]"


def truncate_to_budget(
    text: str,
    max_tokens: int,
    model: str | None = None,
    marker: str = _DEFAULT_TRUNCATION_MARKER,
) -> str:
    """Truncate ``text`` so it fits in ``max_tokens`` (including marker).

    Returns ``text`` unchanged when it is already under budget. When
    truncation is needed, the trailing portion is dropped and a clear
    ``marker`` appended so downstream consumers (and the LLM itself)
    can see that something was cut.
    """
    if max_tokens <= 0 or not text:
        return text

    n = count_tokens(text, model=model)
    if n <= max_tokens:
        return text

    enc = _get_tiktoken_encoding(model or os.environ.get("PIPELINE_LLM_MODEL"))
    marker_tokens = count_tokens(marker, model=model)
    target = max(1, max_tokens - marker_tokens)

    if enc is not None:
        try:
            tokens = enc.encode(text)
            kept = enc.decode(tokens[:target])
            return kept + marker
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"tiktoken truncate failed: {exc}; using char fallback")

    # Char-based fallback: 4 chars per token, then snap to a word boundary.
    char_target = max(1, target * 4)
    if len(text) <= char_target:
        return text + marker
    snapped = text[:char_target].rsplit(" ", 1)[0]
    return snapped + marker


def chunk_to_budget(
    items: Iterable[str],
    max_tokens: int,
    model: str | None = None,
    separator: str = "\n\n",
) -> list[list[str]]:
    """Greedy-pack ``items`` into chunks, each whose total tokens
    (joined by ``separator``) stay at or below ``max_tokens``.

    Useful when synthesising many model outputs into a series of LLM
    calls: the caller can iterate over the returned chunks and emit
    one prompt per chunk. Items longer than ``max_tokens`` get a chunk
    of their own (the caller is expected to subsequently truncate them
    via ``truncate_to_budget``).
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    sep_tokens = count_tokens(separator, model=model) if separator else 0

    for item in items:
        if not item:
            continue
        item_tokens = count_tokens(item, model=model)
        if not current:
            current = [item]
            current_tokens = item_tokens
            continue
        added = sep_tokens + item_tokens
        if current_tokens + added <= max_tokens:
            current.append(item)
            current_tokens += added
        else:
            chunks.append(current)
            current = [item]
            current_tokens = item_tokens

    if current:
        chunks.append(current)
    return chunks


# --------------------------------------------------------------------
# Convenience: structured budget snapshot for logging
# --------------------------------------------------------------------


def budget_snapshot() -> dict[str, int | str | None]:
    """Return the resolved budgets + the model that drove them.

    Used by stage scripts and W&B logging to record the exact budget
    in effect for a given run, which is useful when diagnosing
    truncations after the fact.
    """
    return {
        "model": os.environ.get("PIPELINE_LLM_MODEL"),
        "context_window": get_context_window(),
        "prompt_budget_tokens": get_prompt_budget_tokens(),
        "completion_budget_tokens": get_completion_budget_tokens(),
        "tiktoken_available": _get_tiktoken_encoding(None) is not None,
    }
