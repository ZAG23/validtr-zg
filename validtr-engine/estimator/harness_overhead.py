"""Engine-side heuristic sizing of harness overhead components.

The agent is single-shot and not an MCP client, so MCP tool schemas and skill
bodies cannot be introspected. These documented, tunable constants estimate the
fixed per-turn context each MCP server and skill contributes. The system prompt
is counted for real by the agent and passed through HarnessReport.
"""

from estimator.harness_report import HarnessReport
from models.projection import HarnessComponent

# Documented, tunable per-component token estimates.
MCP_SERVER_TOKEN_ESTIMATE = 700   # approx tool-schema overhead per MCP server
SKILL_TOKEN_ESTIMATE = 400        # approx instruction overhead per skill


def components_from_report(report: HarnessReport) -> list[HarnessComponent]:
    """Build the harness overhead component breakdown from a report."""
    components = [
        HarnessComponent(kind="system_prompt", name="system", tokens=report.system_prompt_tokens)
    ]
    components += [
        HarnessComponent(kind="mcp_server", name=n, tokens=MCP_SERVER_TOKEN_ESTIMATE)
        for n in report.mcp_server_names
    ]
    components += [
        HarnessComponent(kind="skill", name=n, tokens=SKILL_TOKEN_ESTIMATE)
        for n in report.skill_names
    ]
    return components


def overhead_tokens(components: list[HarnessComponent]) -> int:
    """Total fixed per-turn overhead tokens."""
    return sum(c.tokens for c in components)


def avg_output_per_turn(report: HarnessReport) -> int:
    """Measured output tokens per turn (anchor for the projection)."""
    return report.measured_output_tokens // report.turns if report.turns > 0 else 0
