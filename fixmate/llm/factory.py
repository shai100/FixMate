"""Selects the active LLM backend based on configuration.

A single factory function so the rest of the code asks "give me the LLM" without
knowing or caring which vendor is wired up. Switch backends by setting
``LLM_PROVIDER=ollama`` or ``LLM_PROVIDER=anthropic``.
"""

from fixmate.core.settings import settings
from fixmate.llm.anthropic_provider import AnthropicProvider
from fixmate.llm.base import LLMProvider
from fixmate.llm.ollama_provider import OllamaProvider


def get_provider(provider: str | None = None) -> LLMProvider:
    """Return an ``LLMProvider`` for the requested (or configured) backend.

    Args:
        provider: ``"ollama"`` or ``"anthropic"``; defaults to ``settings.llm_provider``.

    Raises:
        ValueError: if the name is not a known backend.
    """
    provider = provider or settings.llm_provider
    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url, model=settings.ollama_generation_model
        )
    if provider == "anthropic":
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    raise ValueError(f"unknown LLM_PROVIDER: {provider!r} (expected 'ollama' or 'anthropic')")
