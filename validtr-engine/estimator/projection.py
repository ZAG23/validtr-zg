"""Pure growing-context token projection for the agent harness."""

from models.projection import HarnessComponent, HarnessProjection, ProjectionRow
from providers import pricing

PRESETS: tuple[tuple[str, int], ...] = (("Light", 3), ("Standard", 10), ("Heavy", 25))

# Documented, tunable assumptions.
DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN = 300
AVG_TOOL_RESULT_TOKENS_PER_TURN = 200


def project_turns(
    overhead_tokens: int,
    avg_output_per_turn: int,
    turns: int,
    avg_tool_result: int = AVG_TOOL_RESULT_TOKENS_PER_TURN,
) -> tuple[int, int]:
    """Return (total_input_tokens, total_output_tokens) for a workflow of `turns`.

    Growing-context model: each turn re-sends the fixed harness overhead plus the
    conversation accumulated so far (prior assistant output + tool results).
    """
    growth = avg_output_per_turn + avg_tool_result
    total_input = sum(overhead_tokens + i * growth for i in range(turns))
    total_output = turns * avg_output_per_turn
    return total_input, total_output


def project(
    overhead_tokens: int,
    avg_output_per_turn: int | None = None,
    presets: tuple[tuple[str, int], ...] = PRESETS,
) -> list[dict]:
    """Project token usage for each preset. Returns row dicts (no cost yet)."""
    avg = avg_output_per_turn or DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN
    rows: list[dict] = []
    for name, turns in presets:
        ti, to = project_turns(overhead_tokens, avg, turns)
        rows.append({
            "preset": name,
            "turns": turns,
            "est_input_tokens": ti,
            "est_output_tokens": to,
            "est_total_tokens": ti + to,
        })
    return rows


def build_projection(
    overhead_tokens: int,
    avg_output_per_turn: int | None,
    components: list[HarnessComponent],
    provider: str,
    model: str,
    catalog: dict[str, dict[str, float]],
) -> HarnessProjection:
    """Build a fully priced HarnessProjection from harness overhead + usage anchor."""
    rates = pricing.resolve_rates(provider, model, catalog)
    rows: list[ProjectionRow] = []
    for raw in project(overhead_tokens, avg_output_per_turn):
        if rates is not None:
            input_cost = raw["est_input_tokens"] * rates["input"]
            output_cost = raw["est_output_tokens"] * rates["output"]
            cost = input_cost + output_cost
            est_cost = f"${cost:.4f}"
        else:
            est_cost = "unavailable"
        rows.append(ProjectionRow(est_cost=est_cost, **raw))
    return HarnessProjection(
        overhead_tokens=overhead_tokens,
        avg_output_tokens_per_turn=avg_output_per_turn or DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN,
        components=components,
        rows=rows,
    )
