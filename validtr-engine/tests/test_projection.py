from estimator import projection


def test_project_turns_growing_context():
    # overhead=1000, avg_output=300, avg_tool_result=200 -> growth=500
    ti, to = projection.project_turns(1000, 300, turns=3, avg_tool_result=200)
    # inputs: 1000 + 1500 + 2000 = 4500 ; outputs: 3*300 = 900
    assert ti == 4500
    assert to == 900


def test_project_uses_default_avg_when_none():
    rows = projection.project(overhead_tokens=1000, avg_output_per_turn=None)
    presets = {r["preset"]: r for r in rows}
    assert set(presets) == {"Light", "Standard", "Heavy"}
    assert presets["Light"]["turns"] == 3
    assert presets["Heavy"]["turns"] == 25
    # output anchored to default
    default_out = 3 * projection.DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN
    assert presets["Light"]["est_output_tokens"] == default_out


def test_project_total_is_input_plus_output():
    rows = projection.project(overhead_tokens=1000, avg_output_per_turn=300)
    for r in rows:
        assert r["est_total_tokens"] == r["est_input_tokens"] + r["est_output_tokens"]


def test_heavier_preset_costs_more_tokens():
    rows = {r["preset"]: r["est_total_tokens"] for r in projection.project(1000, 300)}
    assert rows["Light"] < rows["Standard"] < rows["Heavy"]
