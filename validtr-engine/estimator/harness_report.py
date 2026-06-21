"""Parsing for the in-container harness-report.json artifact."""

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from models.projection import HarnessComponent

logger = logging.getLogger(__name__)


class HarnessReport(BaseModel):
    """Token telemetry emitted by the agent for harness projection."""

    harness_overhead_tokens: int = 0
    components: list[HarnessComponent] = Field(default_factory=list)
    measured_input_tokens: int = 0
    measured_output_tokens: int = 0
    avg_output_tokens_per_turn: int = 0
    tokenizer: str = ""

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
