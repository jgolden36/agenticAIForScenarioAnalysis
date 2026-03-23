"""LangChain LLM client configuration.

Provides a configurable LLM client that does not hardcode a specific provider.
The backend is selected via configuration (environment variables or config files).
"""

from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    **kwargs,
) -> BaseChatModel:
    """Create and return a configured LLM instance.

    Args:
        provider: LLM provider name (e.g., "anthropic", "openai", "bedrock").
                  Defaults to PIPELINE_LLM_PROVIDER env var, then "anthropic".
        model: Model identifier. Defaults to PIPELINE_LLM_MODEL env var.
        temperature: Sampling temperature. Defaults to 0.0 for deterministic output.
        **kwargs: Additional provider-specific keyword arguments.

    Returns:
        A configured LangChain chat model instance.

    Raises:
        ValueError: If the specified provider is not supported.
        ImportError: If the required provider package is not installed.
    """
    provider = provider or os.environ.get("PIPELINE_LLM_PROVIDER", "anthropic")
    model = model or os.environ.get("PIPELINE_LLM_MODEL")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model or "claude-sonnet-4-20250514",
            temperature=temperature,
            **kwargs,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model or "gpt-4o",
            temperature=temperature,
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
            f"Supported providers: anthropic, openai, bedrock"
        )
