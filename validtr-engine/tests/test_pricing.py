"""Tests for OpenRouter-backed pricing and cost computation."""

import json
import os
import time

from providers import pricing

CATALOG = {
    "anthropic/claude-sonnet-4": {"input": 3e-06, "output": 1.5e-05},
    "openai/gpt-4o": {"input": 2.5e-06, "output": 1e-05},
    "google/gemini-2.5-flash": {"input": 3e-07, "output": 2.5e-06},
}


class TestResolveRates:
    def test_exact_match(self):
        rates = pricing.resolve_rates("openai", "gpt-4o", CATALOG)
        assert rates == {"input": 2.5e-06, "output": 1e-05}

    def test_gemini_provider_maps_to_google_slug(self):
        rates = pricing.resolve_rates("gemini", "gemini-2.5-flash", CATALOG)
        assert rates is not None
        assert rates["output"] == 2.5e-06

    def test_strips_date_suffix(self):
        # validtr pins a dated id; OpenRouter lists the undated one.
        rates = pricing.resolve_rates("anthropic", "claude-sonnet-4-20250514", CATALOG)
        assert rates == {"input": 3e-06, "output": 1.5e-05}

    def test_unknown_model_returns_none(self):
        assert pricing.resolve_rates("anthropic", "claude-imaginary-9", CATALOG) is None

    def test_empty_catalog_returns_none(self):
        assert pricing.resolve_rates("openai", "gpt-4o", {}) is None


class TestComputeCost:
    def test_single_model(self):
        by_model = {"gpt-4o": {"input": 1000, "output": 500}}
        cost = pricing.compute_cost("openai", by_model, CATALOG)
        assert cost == 1000 * 2.5e-06 + 500 * 1e-05

    def test_multiple_models_summed(self):
        by_model = {
            "gpt-4o": {"input": 1000, "output": 0},
            "gpt-unknown": {"input": 9999, "output": 9999},
        }
        cost = pricing.compute_cost("openai", by_model, CATALOG)
        # Only the priced model contributes; the unknown one is skipped.
        assert cost == 1000 * 2.5e-06

    def test_all_unknown_returns_none(self):
        by_model = {"mystery": {"input": 100, "output": 100}}
        assert pricing.compute_cost("openai", by_model, CATALOG) is None

    def test_empty_usage_returns_none(self):
        assert pricing.compute_cost("openai", {}, CATALOG) is None


class TestFetchParsing:
    def test_parses_openrouter_shape(self, monkeypatch):
        fake = {
            "data": [
                {"id": "openai/gpt-4o", "pricing": {"prompt": "0.0000025", "completion": "0.00001"}},
                {"id": "broken", "pricing": {"prompt": None, "completion": "0.1"}},
                {"id": "no-pricing"},
            ]
        }

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(fake).encode()

        monkeypatch.setattr(pricing.urllib.request, "urlopen", lambda *a, **k: FakeResp())
        catalog = pricing.fetch_openrouter_catalog()
        assert catalog == {"openai/gpt-4o": {"input": 2.5e-06, "output": 1e-05}}


class TestLoadCatalog:
    def test_uses_fresh_cache_without_fetching(self, tmp_path):
        cache = os.path.join(tmp_path, "p.json")
        with open(cache, "w") as f:
            json.dump(CATALOG, f)

        def boom():
            raise AssertionError("should not fetch when cache is fresh")

        result = pricing.load_catalog(cache_path=cache, ttl=3600, fetcher=boom)
        assert result == CATALOG

    def test_fetches_and_writes_when_cache_missing(self, tmp_path):
        cache = os.path.join(tmp_path, "sub", "p.json")
        result = pricing.load_catalog(cache_path=cache, ttl=3600, fetcher=lambda: CATALOG)
        assert result == CATALOG
        assert os.path.exists(cache)

    def test_refetches_when_cache_stale(self, tmp_path):
        cache = os.path.join(tmp_path, "p.json")
        with open(cache, "w") as f:
            json.dump({"old": {"input": 1.0, "output": 1.0}}, f)
        os.utime(cache, (time.time() - 10_000, time.time() - 10_000))
        result = pricing.load_catalog(cache_path=cache, ttl=3600, fetcher=lambda: CATALOG)
        assert result == CATALOG

    def test_falls_back_to_stale_cache_on_fetch_failure(self, tmp_path):
        cache = os.path.join(tmp_path, "p.json")
        with open(cache, "w") as f:
            json.dump(CATALOG, f)
        os.utime(cache, (time.time() - 10_000, time.time() - 10_000))

        def boom():
            raise OSError("network down")

        result = pricing.load_catalog(cache_path=cache, ttl=3600, fetcher=boom)
        assert result == CATALOG

    def test_returns_empty_when_no_cache_and_fetch_fails(self, tmp_path):
        cache = os.path.join(tmp_path, "missing.json")

        def boom():
            raise OSError("network down")

        assert pricing.load_catalog(cache_path=cache, ttl=3600, fetcher=boom) == {}
