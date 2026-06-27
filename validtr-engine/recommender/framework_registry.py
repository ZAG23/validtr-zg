"""Framework Registry — curated agent frameworks with a live PyPI freshness check.

Unlike MCP servers and skills, there is no central "agent framework registry" to
crawl, so this can't be fully dynamic discovery the way `mcp_registry.py` and
`skills_registry.py` are. What it *can* do is stop the recommendation prompt from
ever pushing a framework that's gone stale or unmaintained: each curated entry's
PyPI release date is checked live (cached for an hour, same TTL pattern as the MCP
and skills registries) and flagged `stale` if its last release is older than
`_STALE_AFTER_DAYS`. The curated list itself still needs occasional manual upkeep —
that's the one thing this module doesn't solve.
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"
_CACHE_TTL = 3600
_STALE_AFTER_DAYS = 540  # ~18 months with no release
_MAX_CONCURRENT = 10

# pypi_package=None means "no framework" — always available, never checked.
CURATED_FRAMEWORKS = [
    {
        "name": "LangGraph",
        "pypi_package": "langgraph",
        "description": "Graph-based agent orchestration with explicit state and control flow",
        "domains": ["general", "multi-step", "stateful"],
    },
    {
        "name": "CrewAI",
        "pypi_package": "crewai",
        "description": "Role-based multi-agent collaboration — a crew of specialized agents",
        "domains": ["multi-agent", "collaboration"],
    },
    {
        "name": "AG2",
        "pypi_package": "ag2",
        "description": "Multi-agent conversation framework (community successor to AutoGen)",
        "domains": ["multi-agent", "conversation"],
    },
    {
        "name": "OpenAI Agents SDK",
        "pypi_package": "openai-agents",
        "description": "Lightweight agent and handoff primitives",
        "domains": ["tool-use", "handoffs"],
    },
    {
        "name": "Pydantic AI",
        "pypi_package": "pydantic-ai",
        "description": "Type-safe agent framework built on Pydantic validation",
        "domains": ["structured-output", "validation"],
    },
    {
        "name": "smolagents",
        "pypi_package": "smolagents",
        "description": "Minimal, code-first agent framework from Hugging Face",
        "domains": ["lightweight", "code-execution"],
    },
    {
        "name": "LlamaIndex Agents",
        "pypi_package": "llama-index",
        "description": "Agent framework with strong built-in RAG/retrieval support",
        "domains": ["rag", "retrieval", "data"],
    },
    {
        "name": "none",
        "pypi_package": None,
        "description": "Direct single-shot prompting, no framework — best for simple tasks",
        "domains": ["simple"],
    },
]


class FrameworkRegistryClient:
    """Fetches PyPI freshness for the curated framework list, with an in-memory TTL cache."""

    def __init__(self):
        self._cache: list[dict] | None = None
        self._cache_time: float = 0

    async def get_all(self) -> list[dict]:
        """Return the curated framework list, each annotated with `stale` and
        `latest_version` (None when the package has no PyPI entry to check, or the
        check failed — unknown freshness is not treated as stale)."""
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < _CACHE_TTL:
            return self._cache

        sem = asyncio.Semaphore(_MAX_CONCURRENT)
        async with httpx.AsyncClient(timeout=10.0) as client:

            async def _check(fw: dict) -> dict:
                if fw["pypi_package"] is None:
                    return {**fw, "stale": False, "latest_version": None}
                async with sem:
                    stale, version = await self._check_package(client, fw["pypi_package"])
                return {**fw, "stale": stale, "latest_version": version}

            results = await asyncio.gather(*[_check(fw) for fw in CURATED_FRAMEWORKS])

        self._cache = list(results)
        self._cache_time = now
        logger.info(
            "Framework registry: %d frameworks (%d stale)",
            len(results),
            sum(1 for r in results if r["stale"]),
        )
        return self._cache

    async def _check_package(
        self, client: httpx.AsyncClient, package: str
    ) -> tuple[bool, str | None]:
        """Return (stale, latest_version) for a PyPI package. Never raises —
        treats fetch failures as "not stale, version unknown" rather than penalizing
        a framework just because PyPI was unreachable."""
        try:
            resp = await client.get(PYPI_JSON_URL.format(package=package))
            if resp.status_code != 200:
                return False, None

            data = resp.json()
            version = data.get("info", {}).get("version")
            releases = data.get("releases", {})
            release_files = releases.get(version, []) if version else []
            if not release_files:
                return False, version

            upload_time = release_files[0].get("upload_time")
            if not upload_time:
                return False, version

            age_days = (time.time() - _parse_iso(upload_time)) / 86400
            return age_days > _STALE_AFTER_DAYS, version
        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.debug("PyPI freshness check failed for %s: %s", package, e)
            return False, None


def _parse_iso(value: str) -> float:
    """Parse a PyPI upload_time(_iso_8601) string to a Unix timestamp."""
    import datetime

    value = value.replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(value).timestamp()


def static_frameworks() -> list[dict]:
    """Curated list without a live freshness check — used when the caller wants to
    skip the network round-trip (e.g. simple tasks that skip registry fetches)."""
    return [{**fw, "stale": False, "latest_version": None} for fw in CURATED_FRAMEWORKS]


def format_for_prompt(frameworks: list[dict]) -> str:
    """Render frameworks as text for the recommendation prompt, dropping stale ones."""
    active = [f for f in frameworks if not f.get("stale")]
    if not active:
        active = frameworks
    return "\n".join(f"- {f['name']}: {f['description']}" for f in active)


def is_known(name: str | None, frameworks: list[dict]) -> bool:
    """Whether a framework name (case-insensitive) is in the given catalog."""
    if not name:
        return False
    lowered = name.strip().lower()
    return any(f["name"].lower() == lowered for f in frameworks)
