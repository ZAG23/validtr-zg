"""Stack recommendation models."""

import logging
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MCPTransport(str, Enum):
    # Supported transports only. Note: MCP's SSE transport is deprecated
    # (superseded by streamable-http) and is intentionally NOT supported.
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable-http"

    @classmethod
    def try_parse(cls, value: str | None) -> "MCPTransport | None":
        """Return the transport if supported, else None.

        Registry/LLM data may advertise transports validtr doesn't support
        (e.g. the deprecated 'sse', or future ones). Callers should skip the
        server rather than crash the run or mislabel its transport.
        """
        if value is None:
            return cls.STDIO
        try:
            return cls(value)
        except ValueError:
            logger.warning("Unsupported MCP transport %r — skipping server", value)
            return None


class LLMRecommendation(BaseModel):
    """Recommended LLM provider and model."""

    provider: str
    model: str
    reason: str


class MCPServerRecommendation(BaseModel):
    """A recommended MCP server."""

    name: str
    transport: MCPTransport
    install: str
    credentials: str = "none"
    description: str = ""


def build_mcp_servers(
    raw: list[dict],
    seen_names: set[str] | None = None,
) -> list["MCPServerRecommendation"]:
    """Build MCP server recommendations from raw registry/LLM dicts.

    Servers advertising an unsupported transport (e.g. deprecated 'sse') are
    skipped rather than crashing the run. Pass `seen_names` to dedup by name
    across multiple calls.
    """
    servers: list[MCPServerRecommendation] = []
    for s in raw:
        name = s.get("name", "")
        if not name:
            continue
        if seen_names is not None:
            if name in seen_names:
                continue
            seen_names.add(name)
        transport = MCPTransport.try_parse(s.get("transport"))
        if transport is None:
            logger.info("Skipping MCP server %r (unsupported transport)", name)
            continue
        servers.append(
            MCPServerRecommendation(
                name=name,
                transport=transport,
                install=s.get("install", ""),
                credentials=s.get("credentials", "none"),
                description=s.get("description", ""),
            )
        )
    return servers


class FrameworkRecommendation(BaseModel):
    """Recommended agent framework (or none)."""

    name: str | None = None
    reason: str = ""


class StackRecommendation(BaseModel):
    """Full stack recommendation from the Recommendation Engine."""

    llm: LLMRecommendation
    framework: FrameworkRecommendation
    mcp_servers: list[MCPServerRecommendation] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    prompt_strategy: str = ""
    estimated_tokens: int = 0
    estimated_cost: str = "$0.00"
    adjustment_notes: list[str] = Field(
        default_factory=list,
        description="Notes about adjustments made during retry",
    )
