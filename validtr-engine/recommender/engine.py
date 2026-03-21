"""Recommendation Engine — orchestrates web search, MCP registry, and LLM reasoning."""

import asyncio
import logging

from models.stack import StackRecommendation
from models.task import Complexity, TaskDefinition, TaskType
from providers.base import LLMProvider
from recommender.llm_reasoning import LLMReasoningEngine
from recommender.mcp_registry import MCPRegistryClient
from recommender.skills_registry import SkillsRegistryClient
from recommender.web_search import WebSearchProvider

logger = logging.getLogger(__name__)
_REGISTRY_HINTS = {
    "api",
    "auth0",
    "aws",
    "azure",
    "browser",
    "cloud",
    "database",
    "deploy",
    "docker",
    "filesystem",
    "github",
    "gitlab",
    "google",
    "integration",
    "jira",
    "k8s",
    "kubernetes",
    "mcp",
    "mongodb",
    "mysql",
    "oauth",
    "postgres",
    "redis",
    "repo",
    "repository",
    "scrape",
    "search",
    "slack",
    "sql",
    "terraform",
}
_MAX_SKILLS_FOR_PROMPT = 12


class RecommendationEngine:
    """Combines web search, MCP registry lookup, and LLM reasoning to recommend a stack."""

    def __init__(
        self,
        provider: LLMProvider,
        search_api_key: str | None = None,
        search_provider: str = "tavily",
    ):
        self.web_search = WebSearchProvider(api_key=search_api_key, provider=search_provider)
        self.mcp_registry = MCPRegistryClient()
        self.skills_registry = SkillsRegistryClient()
        self.llm_reasoning = LLMReasoningEngine(provider=provider)

    async def recommend(
        self,
        task: TaskDefinition,
        preferred_provider: str | None = None,
    ) -> StackRecommendation:
        """Generate a stack recommendation for the given task."""
        logger.info("Generating recommendation for task: %s", task.id)

        # Build a targeted search query from task
        frameworks = " ".join(task.requirements.frameworks) if task.requirements.frameworks else ""
        search_query = f"best practices {task.type.value} {task.domain} {frameworks}".strip()

        # Build a task-specific MCP query from the task metadata
        mcp_query = f"{task.type.value} {task.domain} {frameworks}".strip()

        fetch_registries = _should_fetch_registries(task)
        if fetch_registries:
            web_results, relevant_mcp, all_skills = await asyncio.gather(
                self.web_search.search(search_query),
                self.mcp_registry.get_relevant(mcp_query, limit=20),
                self.skills_registry.get_all(),
            )
            all_skills = _trim_skills_for_prompt(task, all_skills)
        else:
            logger.info("Skipping MCP and skills registry fetch for straightforward code-generation task")
            web_results = await self.web_search.search(search_query)
            relevant_mcp = []
            all_skills = []

        logger.info(
            "Web search: %d results, MCP servers: %d relevant, Skills catalog: %d skills",
            len(web_results), len(relevant_mcp), len(all_skills),
        )

        # Use LLM to synthesize into a recommendation
        recommendation = await self.llm_reasoning.recommend(
            task=task,
            web_results=web_results,
            mcp_servers=relevant_mcp,
            available_skills=all_skills,
            preferred_provider=preferred_provider,
        )
        logger.info(
            "Recommended: %s/%s, %d MCP servers",
            recommendation.llm.provider,
            recommendation.llm.model,
            len(recommendation.mcp_servers),
        )

        return recommendation

    async def search_additional(
        self,
        task: TaskDefinition,
        query_hints: list[str],
    ) -> list:
        """Run additional MCP registry + web searches based on failure hints.

        Returns a list of MCPServerRecommendation objects found.
        """
        from models.stack import MCPServerRecommendation, MCPTransport

        all_servers = []
        seen_names: set[str] = set()

        for hint in query_hints[:3]:  # limit to 3 queries
            mcp_results = await self.mcp_registry.search(hint)
            for s in mcp_results:
                name = s.get("name", "")
                if name and name not in seen_names:
                    seen_names.add(name)
                    all_servers.append(
                        MCPServerRecommendation(
                            name=name,
                            transport=MCPTransport(s.get("transport", "stdio")),
                            install=s.get("install", ""),
                            credentials=s.get("credentials", "none"),
                            description=s.get("description", ""),
                        )
                    )

        return all_servers


def _should_fetch_registries(task: TaskDefinition) -> bool:
    """Return True when registry lookups are likely to change the runtime stack."""
    if task.type != TaskType.CODE_GENERATION:
        return True
    if task.complexity == Complexity.COMPLEX:
        return True

    hint_text = " ".join([
        task.raw_input,
        task.domain,
        " ".join(task.requirements.frameworks),
        " ".join(task.requirements.capabilities),
    ]).lower()
    return any(hint in hint_text for hint in _REGISTRY_HINTS)


def _trim_skills_for_prompt(task: TaskDefinition, skills: list[dict]) -> list[dict]:
    """Keep only the most relevant skills so the prompt stays small."""
    if not skills:
        return []

    terms = {
        term
        for term in (
            [task.domain, task.raw_input, *task.requirements.frameworks, *task.requirements.capabilities]
        )
        for term in str(term).lower().replace("/", " ").replace("-", " ").split()
        if len(term) >= 3
    }

    scored: list[tuple[int, dict]] = []
    for skill in skills:
        name = str(skill.get("name", "")).lower()
        desc = str(skill.get("description", "")).lower()
        score = 0
        if any(term in name for term in terms):
            score += 5
        score += sum(2 for term in terms if term in desc)
        if score > 0:
            scored.append((score, skill))

    if not scored:
        return skills[:_MAX_SKILLS_FOR_PROMPT]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [skill for _, skill in scored[:_MAX_SKILLS_FOR_PROMPT]]
