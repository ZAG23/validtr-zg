"""Tests for recommender/framework_registry.py."""

import httpx
import pytest

from recommender.framework_registry import (
    CURATED_FRAMEWORKS,
    FrameworkRegistryClient,
    format_for_prompt,
    is_known,
    static_frameworks,
)


class TestStaticFrameworks:
    def test_includes_none_option(self):
        names = {f["name"] for f in static_frameworks()}
        assert "none" in names

    def test_none_marked_active(self):
        none_fw = next(f for f in static_frameworks() if f["name"] == "none")
        assert none_fw["stale"] is False
        assert none_fw["latest_version"] is None

    def test_matches_curated_count(self):
        assert len(static_frameworks()) == len(CURATED_FRAMEWORKS)


class TestFormatForPrompt:
    def test_drops_stale_entries(self):
        frameworks = [
            {"name": "Fresh", "description": "still good", "stale": False},
            {"name": "Old", "description": "abandoned", "stale": True},
        ]
        text = format_for_prompt(frameworks)
        assert "Fresh" in text
        assert "Old" not in text

    def test_falls_back_to_all_if_everything_stale(self):
        frameworks = [{"name": "Old", "description": "abandoned", "stale": True}]
        text = format_for_prompt(frameworks)
        assert "Old" in text


class TestIsKnown:
    def test_case_insensitive_match(self):
        frameworks = [{"name": "LangGraph", "description": "", "stale": False}]
        assert is_known("langgraph", frameworks)
        assert is_known("LangGraph", frameworks)

    def test_unknown_name_returns_false(self):
        frameworks = [{"name": "LangGraph", "description": "", "stale": False}]
        assert not is_known("SomeMadeUpFramework", frameworks)

    def test_none_name_returns_false(self):
        assert not is_known(None, [{"name": "LangGraph"}])


class TestFrameworkRegistryClient:
    @pytest.mark.asyncio
    async def test_get_all_caches_within_ttl(self, monkeypatch):
        client = FrameworkRegistryClient()
        calls = {"count": 0}

        async def fake_check(self, http_client, package):
            calls["count"] += 1
            return False, "1.0.0"

        monkeypatch.setattr(FrameworkRegistryClient, "_check_package", fake_check)

        first = await client.get_all()
        second = await client.get_all()

        assert first == second
        # one call per package-having framework, not doubled on the cached call
        non_none_count = len([f for f in CURATED_FRAMEWORKS if f["pypi_package"]])
        assert calls["count"] == non_none_count

    @pytest.mark.asyncio
    async def test_none_framework_never_checked(self, monkeypatch):
        client = FrameworkRegistryClient()
        checked_packages = []

        async def fake_check(self, http_client, package):
            checked_packages.append(package)
            return False, "1.0.0"

        monkeypatch.setattr(FrameworkRegistryClient, "_check_package", fake_check)
        results = await client.get_all()

        none_entry = next(r for r in results if r["name"] == "none")
        assert none_entry["stale"] is False
        assert None not in checked_packages

    @pytest.mark.asyncio
    async def test_check_package_handles_http_error(self):
        client = FrameworkRegistryClient()

        class _FailingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                raise httpx.ConnectError("boom")

        async with httpx.AsyncClient(transport=_FailingTransport()) as http_client:
            stale, version = await client._check_package(http_client, "some-package")

        assert stale is False
        assert version is None

    @pytest.mark.asyncio
    async def test_check_package_marks_old_release_stale(self):
        client = FrameworkRegistryClient()

        def handler(request):
            return httpx.Response(
                200,
                json={
                    "info": {"version": "0.1.0"},
                    "releases": {
                        "0.1.0": [{"upload_time": "2015-01-01T00:00:00"}],
                    },
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            stale, version = await client._check_package(http_client, "ancient-package")

        assert stale is True
        assert version == "0.1.0"

    @pytest.mark.asyncio
    async def test_check_package_marks_recent_release_fresh(self):
        import datetime

        client = FrameworkRegistryClient()
        recent = (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()

        def handler(request):
            return httpx.Response(
                200,
                json={
                    "info": {"version": "2.0.0"},
                    "releases": {"2.0.0": [{"upload_time": recent}]},
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            stale, version = await client._check_package(http_client, "fresh-package")

        assert stale is False
        assert version == "2.0.0"
