"""LangChain LLM client configuration.

Provides a configurable LLM client that does not hardcode a specific provider.
Supports cloud APIs (Anthropic, OpenAI, Bedrock) and local GPU inference
servers (vLLM, Ollama, text-generation-inference) for cluster deployments.

Includes concurrency-limited wrappers for rate-limit protection when
fan-out parallelism dispatches many simultaneous LLM requests, plus a
defensive ``with_overflow_retry`` helper that re-invokes a chain with a
truncated input on "maximum context length" errors.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Callable, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from src.common.context_budget import get_completion_budget_tokens

logger = logging.getLogger(__name__)


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    base_url: str | None = None,
    max_concurrency: int | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> BaseChatModel:
    """Create and return a configured LLM instance.

    Args:
        provider: LLM provider name. Supported:
            - "anthropic": Anthropic API
            - "openai": OpenAI API
            - "bedrock": AWS Bedrock
            - "vllm": Local vLLM OpenAI-compatible server on GPU cluster
            - "ollama": Local Ollama server
            Defaults to PIPELINE_LLM_PROVIDER env var, then "anthropic".
        model: Model identifier. Defaults to PIPELINE_LLM_MODEL env var.
        temperature: Sampling temperature. Defaults to 0.0 for deterministic output.
        base_url: Custom endpoint URL. Required for vllm/ollama providers if
            not set via PIPELINE_LLM_BASE_URL env var.
        max_concurrency: Max concurrent requests to this LLM. When set,
            wraps the model with a concurrency limiter. Defaults to
            PIPELINE_LLM_MAX_CONCURRENCY env var.
        max_tokens: Hard cap on completion tokens per request. Defaults
            to ``src.common.context_budget.get_completion_budget_tokens()``
            (which itself reads ``PIPELINE_LLM_MAX_COMPLETION_TOKENS``).
            Pass ``0`` (or any falsy value via the env) to disable the
            cap and let the provider use its own default.
        **kwargs: Additional provider-specific keyword arguments.

    Returns:
        A configured LangChain chat model instance, optionally wrapped
        with a concurrency limiter.
    """
    provider = provider or os.environ.get("PIPELINE_LLM_PROVIDER", "anthropic")
    model = model or os.environ.get("PIPELINE_LLM_MODEL")
    base_url = base_url or os.environ.get("PIPELINE_LLM_BASE_URL")

    if max_concurrency is None:
        env_val = os.environ.get("PIPELINE_LLM_MAX_CONCURRENCY")
        max_concurrency = int(env_val) if env_val else None

    if max_tokens is None:
        # Default to the configured completion budget. Callers that
        # genuinely want the provider's open-ended default can pass
        # ``max_tokens=0`` (or set the env var to 0/empty).
        max_tokens = get_completion_budget_tokens()

    llm = _create_provider(
        provider, model, temperature, base_url, max_tokens=max_tokens, **kwargs
    )

    if max_concurrency and max_concurrency > 0:
        llm = llm.with_config(
            RunnableConfig(max_concurrency=max_concurrency)
        )

    return llm


def _create_provider(
    provider: str,
    model: str | None,
    temperature: float,
    base_url: str | None,
    max_tokens: int | None = None,
    **kwargs,
) -> BaseChatModel:
    """Instantiate the appropriate LangChain chat model.

    ``max_tokens`` is forwarded to the underlying provider so the
    completion length is bounded explicitly; without it vLLM defaults
    to ``max_model_len - prompt_tokens`` which leaves no headroom for
    a large prompt and amplifies "context length exceeded" failures.
    """

    # Only forward max_tokens when the caller actually wants a cap (a
    # value of 0 or None tells us to fall through to the provider's
    # native default, which is what users get if they explicitly opted
    # out via env).
    cap_tokens = max_tokens if (max_tokens is not None and max_tokens > 0) else None

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        anth_kwargs: dict[str, Any] = {}
        if cap_tokens is not None:
            # ChatAnthropic uses ``max_tokens`` (required by the SDK
            # for non-streaming calls; LangChain defaults to a large
            # value if absent).
            anth_kwargs["max_tokens"] = cap_tokens
        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
            **anth_kwargs,
            **kwargs,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        extra: dict[str, Any] = {}
        if base_url:
            extra["base_url"] = base_url
        if cap_tokens is not None:
            # ChatOpenAI maps ``max_tokens`` to the OpenAI Chat
            # Completions API ``max_tokens`` parameter.
            extra["max_tokens"] = cap_tokens
        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temperature,
            **extra,
            **kwargs,
        )

    elif provider == "vllm":
        from langchain_openai import ChatOpenAI

        vllm_url = base_url or "http://localhost:8000/v1"
        vllm_kwargs: dict[str, Any] = {}
        if cap_tokens is not None:
            vllm_kwargs["max_tokens"] = cap_tokens
        return ChatOpenAI(
            model=model or "meta-llama/Llama-3.1-70B-Instruct",
            temperature=temperature,
            base_url=vllm_url,
            api_key=os.environ.get("VLLM_API_KEY", "EMPTY"),
            **vllm_kwargs,
            **kwargs,
        )

    elif provider == "ollama":
        from langchain_openai import ChatOpenAI

        ollama_url = base_url or "http://localhost:11434/v1"
        ollama_kwargs: dict[str, Any] = {}
        if cap_tokens is not None:
            ollama_kwargs["max_tokens"] = cap_tokens
        return ChatOpenAI(
            model=model or "llama3.1",
            temperature=temperature,
            base_url=ollama_url,
            api_key="ollama",
            **ollama_kwargs,
            **kwargs,
        )

    elif provider == "bedrock":
        from langchain_aws import ChatBedrock

        bedrock_kwargs: dict[str, Any] = {"temperature": temperature, **kwargs}
        if cap_tokens is not None:
            # Bedrock Anthropic models accept ``max_tokens`` inside
            # ``model_kwargs`` (e.g. ``anthropic.claude-...``).
            bedrock_kwargs["max_tokens"] = cap_tokens
        return ChatBedrock(
            model_id=model or "anthropic.claude-sonnet-4-20250514-v1:0",
            model_kwargs=bedrock_kwargs,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider!r}. "
            f"Supported: anthropic, openai, bedrock, vllm, ollama"
        )


# --------------------------------------------------------------------
# Context-overflow retry
# --------------------------------------------------------------------


# Substring fingerprints used to identify "I've exceeded the context
# window" errors across providers. Matched case-insensitively against
# ``str(exc)`` because LangChain wraps the underlying SDK exception in
# its own classes (e.g. langchain_core.exceptions.OutputParserException
# or openai.BadRequestError) and the substring is the most reliable
# signal we have.
_CONTEXT_OVERFLOW_FINGERPRINTS: tuple[str, ...] = (
    "maximum context length",                    # OpenAI Chat Completions
    "context_length_exceeded",                   # OpenAI error code
    "maximum_tokens",                            # vLLM
    "this model's maximum context length",       # OpenAI / vLLM API server
    "input is too long",                         # Anthropic
    "prompt is too long",                        # Anthropic
    "exceeds the model's context window",        # Generic
    "maxtokensexceeded",                         # Bedrock
    "validationexception",                       # Bedrock (often paired)
    "input too long",                            # Bedrock Anthropic
)


def is_context_length_error(exc: BaseException) -> bool:
    """Return ``True`` if ``exc`` looks like a context-length overflow.

    Matches across providers by scanning ``str(exc)`` for known error
    fingerprints. False positives are rare because the fingerprints
    are specific phrases the providers actually emit.
    """
    msg = str(exc).lower()
    return any(fp in msg for fp in _CONTEXT_OVERFLOW_FINGERPRINTS)


T = TypeVar("T")


def with_overflow_retry(
    invocable: Runnable | Callable[[dict], T],
    truncate_input: Callable[[dict], dict],
    *,
    max_retries: int = 1,
    on_truncation: Callable[[int], None] | None = None,
) -> Runnable[dict, T]:
    """Wrap a chain so it re-invokes with a halved input on context overflow.

    Args:
        invocable: A LangChain ``Runnable`` (or any callable taking a
            single dict and returning the structured output). The wrapper
            calls it with the input dict, catches context-length errors,
            applies ``truncate_input`` to shrink the dict, and retries.
        truncate_input: Pure function ``inputs -> shrunken_inputs``. The
            caller is expected to halve the heaviest field(s) — the
            wrapper has no opinion on which field is the prompt because
            the chain's input shape is caller-defined.
        max_retries: Maximum retries on overflow before re-raising the
            last exception. Default 1 (so a single overflow gets one
            chance to recover; deeper failures surface so the synthesis
            stage can fall back to a deterministic summary).
        on_truncation: Optional callback invoked with the retry index
            (1-based) every time a retry happens. Used by the synthesis
            stage to surface truncation events into ``synthesis_state``.

    Returns:
        A ``RunnableLambda`` that takes the original input dict and
        returns the chain's output (or raises the final exception).
    """

    def _invoke_sync(inputs: dict) -> Any:
        attempt = 0
        current = inputs
        while True:
            try:
                if isinstance(invocable, Runnable):
                    return invocable.invoke(current)
                return invocable(current)
            except Exception as exc:
                if not is_context_length_error(exc):
                    raise
                attempt += 1
                if attempt > max_retries:
                    logger.warning(
                        f"Context overflow persisted after {max_retries} retry(ies); "
                        f"surfacing original error: {exc}"
                    )
                    raise
                logger.warning(
                    f"Context overflow detected (attempt {attempt}); "
                    f"truncating input and retrying. Error was: {exc}"
                )
                if on_truncation is not None:
                    try:
                        on_truncation(attempt)
                    except Exception as cb_exc:  # pragma: no cover - defensive
                        logger.debug(f"on_truncation callback raised: {cb_exc}")
                current = truncate_input(current)

    async def _invoke_async(inputs: dict) -> Any:
        attempt = 0
        current = inputs
        while True:
            try:
                if isinstance(invocable, Runnable):
                    return await invocable.ainvoke(current)
                result = invocable(current)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception as exc:
                if not is_context_length_error(exc):
                    raise
                attempt += 1
                if attempt > max_retries:
                    logger.warning(
                        f"Context overflow persisted after {max_retries} retry(ies); "
                        f"surfacing original error: {exc}"
                    )
                    raise
                logger.warning(
                    f"Context overflow detected (attempt {attempt}); "
                    f"truncating input and retrying. Error was: {exc}"
                )
                if on_truncation is not None:
                    try:
                        on_truncation(attempt)
                    except Exception as cb_exc:  # pragma: no cover - defensive
                        logger.debug(f"on_truncation callback raised: {cb_exc}")
                current = truncate_input(current)

    return RunnableLambda(_invoke_sync, afunc=_invoke_async)


async def get_llm_async(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    base_url: str | None = None,
    max_concurrency: int | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> BaseChatModel:
    """Async version of get_llm (same signature, same result).

    Provided for consistency in async contexts; the factory itself is
    synchronous but the returned model supports both .invoke() and .ainvoke().
    """
    return get_llm(
        provider=provider,
        model=model,
        temperature=temperature,
        base_url=base_url,
        max_concurrency=max_concurrency,
        max_tokens=max_tokens,
        **kwargs,
    )
