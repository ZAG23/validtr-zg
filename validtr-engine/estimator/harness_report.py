"""Parsing for the in-container harness-report.json artifact."""

import json
import logging

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class HarnessReport(BaseModel):
    """Token telemetry the agent emits in-container for harness projection.

    Carries only what the agent uniquely knows: the real system-prompt token
    count, its measured usage, the turn count, and the MCP/skill names. The engine
    applies heuristic per-component estimates (see estimator.harness_overhead).
    """

    system_prompt_tokens: int = 0
    measured_input_tokens: int = 0
    measured_output_tokens: int = 0
    turns: int = 1
    mcp_server_names: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)

    @property
    def measured_total_tokens(self) -> int:
        return self.measured_input_tokens + self.measured_output_tokens


def read_harness_report(path: str) -> HarnessReport | None:
    """Read and validate a harness report. Returns None if missing/malformed."""
    try:
        with open(path) as f:
            data = json.load(f)
        return HarnessReport.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as e:
        logger.warning("Could not read harness report %s: %s", path, e)
        return None
