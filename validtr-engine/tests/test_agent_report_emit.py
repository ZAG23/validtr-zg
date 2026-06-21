"""The generated agent loop must emit a parseable harness-report.json.

This guards the embedded agent-loop template (a string in compose_generator):
the emitted code must compile and contain the harness-report producer, so the
projection feature actually has a data source on real runs.
"""

import os
import py_compile
import tempfile

from models.stack import FrameworkRecommendation, LLMRecommendation, StackRecommendation
from provisioner.compose_generator import ComposeGenerator


def _emit_agent_loop() -> str:
    gen = ComposeGenerator(output_base=tempfile.mkdtemp())
    run_dir = os.path.join(gen.output_base, "run")
    os.makedirs(run_dir, exist_ok=True)
    stack = StackRecommendation(
        llm=LLMRecommendation(provider="anthropic", model="claude-sonnet-4-20250514", reason="t"),
        framework=FrameworkRecommendation(),
    )
    gen._write_agent_loop(run_dir, stack)
    return os.path.join(run_dir, "agent_loop.py")


def test_emitted_agent_loop_compiles():
    py_compile.compile(_emit_agent_loop(), doraise=True)


def test_emitted_agent_loop_contains_report_producer():
    src = open(_emit_agent_loop()).read()
    assert "_write_harness_report" in src
    assert "harness-report.json" in src
    assert "_count_tokens" in src
    # measured usage is threaded out of generation
    assert "return text, in_tok, out_tok" in src
    # report fields the engine-side HarnessReport expects
    for field in ("system_prompt_tokens", "measured_input_tokens",
                  "measured_output_tokens", "mcp_server_names", "skill_names"):
        assert field in src, field
