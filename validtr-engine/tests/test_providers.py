"""Tests for provider factory and provider classes."""

import pytest

from providers.base import LLMProvider, get_provider


class TestGetProvider:
    """Tests for the get_provider() factory function."""

    def test_returns_anthropic_provider(self):
        provider = get_provider("anthropic", api_key="fake-key", model="claude-sonnet-4-20250514")
        assert provider.provider_name == "anthropic"
        assert isinstance(provider, LLMProvider)

    def test_returns_openai_provider(self):
        provider = get_provider("openai", api_key="fake-key", model="gpt-4o")
        assert provider.provider_name == "openai"
        assert isinstance(provider, LLMProvider)

    def test_returns_gemini_provider(self):
        provider = get_provider("gemini", api_key="fake-key", model="gemini-2.5-flash")
        assert provider.provider_name == "gemini"
        assert isinstance(provider, LLMProvider)

    def test_raises_for_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("llama", api_key="fake-key", model="x")

    def test_raises_for_empty_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("", api_key="fake-key", model="x")


class TestModelRequired:
    """validtr has no default model — a model must be specified for every provider."""

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
    def test_raises_without_model(self, provider):
        with pytest.raises(ValueError, match="No model specified"):
            get_provider(provider, api_key="fake-key")

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
    def test_raises_with_empty_model(self, provider):
        with pytest.raises(ValueError, match="No model specified"):
            get_provider(provider, api_key="fake-key", model="")


class TestProviderAttributes:
    """Provider name and explicit model are honored across providers."""

    def test_anthropic_custom_model(self):
        provider = get_provider("anthropic", api_key="fake-key", model="claude-opus-4-20250514")
        assert provider.provider_name == "anthropic"
        assert provider.model == "claude-opus-4-20250514"

    def test_openai_custom_model(self):
        provider = get_provider("openai", api_key="fake-key", model="gpt-4o-mini")
        assert provider.provider_name == "openai"
        assert provider.model == "gpt-4o-mini"

    def test_gemini_custom_model(self):
        provider = get_provider("gemini", api_key="fake-key", model="gemini-2.5-pro")
        assert provider.provider_name == "gemini"
        assert provider.model == "gemini-2.5-pro"
