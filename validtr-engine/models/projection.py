# validtr-engine/models/projection.py
"""Models for agent-harness token projection."""

from pydantic import BaseModel, Field


class HarnessComponent(BaseModel):
    """Per-component token attribution for the harness overhead."""

    kind: str  # "system_prompt" | "mcp_server" | "skill"
    name: str
    tokens: int = 0


class ProjectionRow(BaseModel):
    """Projected usage for one preset workflow size."""

    preset: str
    turns: int
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    est_total_tokens: int = 0
    est_cost: str = "unavailable"


class HarnessProjection(BaseModel):
    """Forward-looking token/cost projection for the validated harness."""

    overhead_tokens: int = 0
    avg_output_tokens_per_turn: int = 0
    components: list[HarnessComponent] = Field(default_factory=list)
    rows: list[ProjectionRow] = Field(default_factory=list)
