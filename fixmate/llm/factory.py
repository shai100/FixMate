from fixmate.core.settings import settings
from fixmate.llm.anthropic_provider import AnthropicProvider
from fixmate.llm.base import LLMProvider
from fixmate.llm.ollama_provider import OllamaProvider


def get_provider(provider: str | None = None) -> LLMProvider:
    provider = provider or settings.llm_provider
    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url, model=settings.ollama_generation_model
        )
    if provider == "anthropic":
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
    raise ValueError(f"unknown LLM_PROVIDER: {provider!r} (expected 'ollama' or 'anthropic')")
