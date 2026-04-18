"""LangChain LLM client configuration.

Provides a configurable LLM client that does not hardcode a specific provider.
Supports cloud APIs (Anthropic, OpenAI, Bedrock) and local GPU inference
servers (vLLM, Ollama, text-generation-inference) for cluster deployments.

Includes concurrency-limited wrappers for rate-limit protection when
fan-out parallelism dispatches many simultaneous LLM requests.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    base_url: str | None = None,
    max_concurrency: int | None = None,
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

    llm = _create_provider(provider, model, temperature, base_url, **kwargs)

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
    **kwargs,
) -> BaseChatModel:
    """Instantiate the appropriate LangChain chat model."""

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
            **kwargs,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        extra: dict[str, Any] = {}
        if base_url:
            extra["base_url"] = base_url
        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temperature,
            **extra,
            **kwargs,
        )

    elif provider == "vllm":
        from langchain_openai import ChatOpenAI

        vllm_url = base_url or "http://localhost:8000/v1"
        return ChatOpenAI(
            model=model or "meta-llama/Llama-3.1-70B-Instruct",
            temperature=temperature,
            base_url=vllm_url,
            api_key=os.environ.get("VLLM_API_KEY", "EMPTY"),
            **kwargs,
        )

    elif provider == "ollama":
        from langchain_openai import ChatOpenAI

        ollama_url = base_url or "http://localhost:11434/v1"
        return ChatOpenAI(
            model=model or "llama3.1",
            temperature=temperature,
            base_url=ollama_url,
            api_key="ollama",
            **kwargs,
        )

    elif provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=model or "anthropic.claude-sonnet-4-20250514-v1:0",
            model_kwargs={"temperature": temperature, **kwargs},
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider!r}. "
            f"Supported: anthropic, openai, bedrock, vllm, ollama"
        )


async def get_llm_async(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    base_url: str | None = None,
    max_concurrency: int | None = None,
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
        **kwargs,
    )
