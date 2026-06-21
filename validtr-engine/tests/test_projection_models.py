# validtr-engine/tests/test_projection_models.py
from models.projection import HarnessComponent, HarnessProjection, ProjectionRow


def test_models_construct_with_defaults():
    comp = HarnessComponent(kind="mcp_server", name="filesystem", tokens=1840)
    row = ProjectionRow(
        preset="Standard", turns=10,
        est_input_tokens=1, est_output_tokens=2, est_total_tokens=3,
    )
    proj = HarnessProjection(
        overhead_tokens=4213,
        avg_output_tokens_per_turn=251,
        components=[comp],
        rows=[row],
    )
    assert proj.overhead_tokens == 4213
    assert proj.rows[0].est_cost == "unavailable"  # default
    assert proj.components[0].name == "filesystem"


def test_harness_projection_defaults_empty():
    proj = HarnessProjection()
    assert proj.overhead_tokens == 0
    assert proj.rows == []
    assert proj.components == []
