import pytest

from fixmate.llm.anthropic_provider import AnthropicProvider
from fixmate.llm.factory import get_provider
from fixmate.llm.ollama_provider import OllamaProvider


def test_factory_returns_ollama(monkeypatch):
    monkeypatch.setattr("fixmate.llm.factory.settings.llm_provider", "ollama")
    assert isinstance(get_provider(), OllamaProvider)


def test_factory_returns_anthropic(monkeypatch):
    monkeypatch.setattr("fixmate.llm.factory.settings.llm_provider", "anthropic")
    monkeypatch.setattr("fixmate.llm.factory.settings.anthropic_api_key", "test-key")
    assert isinstance(get_provider(), AnthropicProvider)


def test_factory_explicit_override(monkeypatch):
    monkeypatch.setattr("fixmate.llm.factory.settings.llm_provider", "ollama")
    monkeypatch.setattr("fixmate.llm.factory.settings.anthropic_api_key", "test-key")
    assert isinstance(get_provider("anthropic"), AnthropicProvider)


def test_factory_unknown_raises(monkeypatch):
    monkeypatch.setattr("fixmate.llm.factory.settings.llm_provider", "bananas")
    with pytest.raises(ValueError):
        get_provider()
