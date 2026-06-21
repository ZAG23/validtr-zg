from estimator import harness_overhead as ho
from estimator.harness_report import HarnessReport
from models.projection import HarnessComponent


def _report(**kw):
    base = dict(system_prompt_tokens=400, measured_input_tokens=8000,
                measured_output_tokens=1000, turns=4,
                mcp_server_names=["filesystem", "github"], skill_names=["k8skill"])
    base.update(kw)
    return HarnessReport(**base)


def test_components_from_report():
    comps = ho.components_from_report(_report())
    assert comps[0] == HarnessComponent(kind="system_prompt", name="system", tokens=400)
    kinds = {(c.kind, c.name): c.tokens for c in comps}
    assert kinds[("mcp_server", "github")] == ho.MCP_SERVER_TOKEN_ESTIMATE
    assert kinds[("skill", "k8skill")] == ho.SKILL_TOKEN_ESTIMATE


def test_overhead_tokens_sums_components():
    comps = ho.components_from_report(_report())
    expected = 400 + 2 * ho.MCP_SERVER_TOKEN_ESTIMATE + 1 * ho.SKILL_TOKEN_ESTIMATE
    assert ho.overhead_tokens(comps) == expected


def test_avg_output_per_turn():
    assert ho.avg_output_per_turn(_report(measured_output_tokens=1000, turns=4)) == 250


def test_avg_output_per_turn_zero_turns_guard():
    assert ho.avg_output_per_turn(_report(turns=0)) == 0


def test_no_mcp_or_skills_just_system_prompt():
    comps = ho.components_from_report(_report(mcp_server_names=[], skill_names=[]))
    assert len(comps) == 1
    assert comps[0].kind == "system_prompt"
