---
title: Harness Token Projection
date: 2026-06-21
description: How validtr projects token usage and cost for common workflows with a validated agent harness.
tags: [tokens, cost, harness, projection]
author: validtr
---

# Harness Token Projection

After a run, validtr projects how many tokens — and how much money — the
**validated agent harness** (LLM + agent + MCP servers + skills) would consume
across a few representative workflow sizes. This helps you understand the ongoing
cost of a harness, not just the cost of the single validation run.

## Prerequisites

- A completed `validtr run` (projection is shown in the run results; it is not
  produced for `--dry-run`).
- For cost figures: network access to OpenRouter pricing (cached locally for 24h).
  Unpriced models show cost as `unavailable`.

## Preset workflow sizes

Projections are shown for three preset sizes, measured in agent-loop turns:

| Preset   | Turns |
|----------|-------|
| Light    | 3     |
| Standard | 10    |
| Heavy    | 25    |

These turn counts are tunable constants (`PRESETS` in
`validtr-engine/estimator/projection.py`).

## How the estimate is built

- **System prompt** — counted for real (the agent tokenizes its actual system
  prompt in-container).
- **Measured usage** — the agent's real input/output token usage from the run is
  folded into the run totals and used to anchor the projection's output-per-turn.
- **MCP servers and skills** — sized with documented, tunable per-component token
  estimates (`MCP_SERVER_TOKEN_ESTIMATE`, `SKILL_TOKEN_ESTIMATE` in
  `validtr-engine/estimator/harness_overhead.py`). The agent is single-shot and
  does not introspect live tool schemas, so these are estimates, not exact counts.

## Projection model

validtr uses a **growing-context** model: each turn re-sends the fixed harness
overhead (system prompt + tool/skill estimates) plus the conversation accumulated
so far, so longer workflows cost more than linearly. Output per turn is anchored
to the measured run (or a documented default when unavailable). See
`AVG_TOOL_RESULT_TOKENS_PER_TURN` and `DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN` in
`validtr-engine/estimator/projection.py`.

All projection figures are **estimates**, labeled as such in the CLI and UI.
