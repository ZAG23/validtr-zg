"""Tests for providers/model_catalog.py — the cascadeflow-backed model registry."""

from providers import model_catalog


class TestFallbackBehavior:
    """With cascadeflow unavailable (or returning nothing), callers still get a usable list."""

    def test_list_models_falls_back_when_no_registry(self, monkeypatch):
        monkeypatch.setattr(model_catalog, "_registry", lambda: None)
        models = model_catalog.list_models("anthropic")
        assert models
        assert all(not m["deprecated"] for m in models)

    def test_upgrade_path_returns_names_only(self, monkeypatch):
        monkeypatch.setattr(model_catalog, "_registry", lambda: None)
        path = model_catalog.upgrade_path("openai")
        assert path == [m["name"] for m in model_catalog.list_models("openai")]

    def test_unknown_provider_returns_empty(self, monkeypatch):
        monkeypatch.setattr(model_catalog, "_registry", lambda: None)
        assert model_catalog.list_models("does-not-exist") == []

    def test_is_deprecated_false_without_registry(self, monkeypatch):
        monkeypatch.setattr(model_catalog, "_registry", lambda: None)
        assert model_catalog.is_deprecated("anthropic", "claude-sonnet-4-6") is False

    def test_format_for_prompt_never_empty(self, monkeypatch):
        monkeypatch.setattr(model_catalog, "_registry", lambda: None)
        text = model_catalog.format_for_prompt()
        assert text
        assert "anthropic" in text


class _FakeEntry:
    def __init__(self, name, provider, cost, deprecated=False, context_window=None):
        self.name = name
        self.provider = provider
        self.cost = cost
        self.deprecated = deprecated
        self.context_window = context_window


class _FakeRegistry:
    def __init__(self, entries):
        self._entries = entries

    def list_by_provider(self, provider):
        return [e for e in self._entries if e.provider == provider]

    def get(self, name):
        for e in self._entries:
            if e.name == name:
                return e
        return None


class TestRegistryBackedBehavior:
    """With a registry available, deprecated models are filtered and ordered cheapest-first."""

    def test_excludes_deprecated_models(self, monkeypatch):
        registry = _FakeRegistry([
            _FakeEntry("claude-old", "anthropic", cost=0.001, deprecated=True),
            _FakeEntry("claude-sonnet-4-6", "anthropic", cost=0.003),
        ])
        monkeypatch.setattr(model_catalog, "_registry", lambda: registry)
        names = [m["name"] for m in model_catalog.list_models("anthropic")]
        assert "claude-old" not in names
        assert "claude-sonnet-4-6" in names

    def test_sorts_cheapest_first(self, monkeypatch):
        registry = _FakeRegistry([
            _FakeEntry("claude-opus-4-8", "anthropic", cost=0.015),
            _FakeEntry("claude-sonnet-4-6", "anthropic", cost=0.003),
        ])
        monkeypatch.setattr(model_catalog, "_registry", lambda: registry)
        names = model_catalog.upgrade_path("anthropic")
        assert names == ["claude-sonnet-4-6", "claude-opus-4-8"]

    def test_falls_back_to_static_list_when_provider_empty(self, monkeypatch):
        registry = _FakeRegistry([_FakeEntry("claude-sonnet-4-6", "anthropic", cost=0.003)])
        monkeypatch.setattr(model_catalog, "_registry", lambda: registry)
        # No entries for "google" (gemini's slug) in the fake registry -> static fallback
        assert model_catalog.upgrade_path("gemini") == model_catalog._FALLBACK_MODELS["gemini"]

    def test_is_deprecated_checks_provider_match(self, monkeypatch):
        registry = _FakeRegistry([_FakeEntry("shared-name", "openai", cost=0.001, deprecated=True)])
        monkeypatch.setattr(model_catalog, "_registry", lambda: registry)
        # Same name, different provider slug -> not deprecated for anthropic
        assert model_catalog.is_deprecated("anthropic", "shared-name") is False
        assert model_catalog.is_deprecated("openai", "shared-name") is True
