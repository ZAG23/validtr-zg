# Agent Harness Token Projection — Design

**Date:** 2026-06-21
**Status:** Approved (design); pending implementation plan

## Summary

After a validtr run, project the token usage and cost of running representative
"common workflows" with the validated **agent harness** — the LLM, agent loop,
MCP server tools, and agent skills working together. The goal is to let a user
understand the ongoing token/cost footprint of a harness before adopting it,
not just the cost of the single validation run.

This is a **forward-looking projection** built from **real introspection** of the
harness (actual MCP tool schemas and skill bodies, tokenized with the provider's
own tokenizer), scaled across **preset workflow sizes** using a **growing-context**
model.

## Goals

- Show, in the run results, an estimated token + cost footprint for a few
  representative workflow sizes (Light / Standard / Heavy) using the validated
  harness.
- Make the harness composition visible: more MCP tools / skills ⇒ higher per-turn
  overhead ⇒ higher projected cost. Surface a per-component breakdown.
- Be honest: label everything as an estimate and surface the assumptions.

## Non-goals (YAGNI)

- Projection during `--dry-run` (the chosen capture mechanism requires a real run).
- Per-server tool-schema caching across runs.
- Per-provider model selection for `--compare` (separate follow-up).
- A standalone "estimate this hypothetical harness" command (only projects the
  harness that was actually run).

## Key decisions (from brainstorming)

1. **Core intent:** project common-workflow usage (forward-looking), not just a
   breakdown of this run.
2. **Workflow model:** preset sizes by agent-loop turns — **Light = 3, Standard =
   10, Heavy = 25** (tunable constants).
3. **Estimation basis:** model from harness composition (system prompt + MCP tool
   schemas + skill bodies), so the harness's own contribution is explicit.
4. **Component sizing:** **real introspection** — actual MCP `tools/list` schemas
   and full skill bodies, tokenized with the provider's own tokenizer.
5. **Introspection mechanism:** **reuse the run's already-launched MCP servers**.
   The agent emits a `harness-report.json` artifact the engine reads back. This
   reuses the same agent→engine channel needed to fix the in-container token gap.
6. **Projection math:** **growing-context** model (context accumulates each turn).
7. **Bundled:** closes the previously-paused in-container token telemetry gap via
   the same report.

## Architecture

Four units, each independently testable:

### 1. In-container harness report (capture)

The agent (`provisioner` agent loop, container/MCP path) is already connected to
the provider and to the recommended MCP servers. Extend it to write one
`harness-report.json` into the workspace output directory. The engine reads it
back after the container exits (same pattern as artifact collection).

Report contents:

```json
{
  "harness_overhead_tokens": 4213,
  "components": [
    {"kind": "system_prompt", "name": "system", "tokens": 412},
    {"kind": "mcp_server", "name": "filesystem", "tokens": 1840},
    {"kind": "skill", "name": "k8skill", "tokens": 1961}
  ],
  "measured_input_tokens": 8123,
  "measured_output_tokens": 1004,
  "avg_output_tokens_per_turn": 251,
  "tokenizer": "anthropic"
}
```

- `harness_overhead_tokens` — fixed context re-sent every turn: system prompt +
  all MCP tool schemas (`tools/list` per server) + skill bodies. Counted with the
  provider's own tokenizer (Anthropic `messages.count_tokens`, OpenAI `tiktoken`,
  Gemini `models.count_tokens` — precise and free / local).
- `components` — per-component token attribution for the breakdown UI.
- `measured_input_tokens` / `measured_output_tokens` — the agent's actual usage
  this run (closes the in-container telemetry gap).
- `avg_output_tokens_per_turn` — anchor for the projection.

**Direct fast-path (no MCP servers):** no container, no `tools/list`. The engine
computes overhead from the system prompt (+ any skills) itself; measured usage is
already captured by `UsageTracker`. No report file is produced.

**Degradation:** a missing or partial report never breaks the run. If overhead
can't be determined, the projection is reported as unavailable (consistent with
how cost is treated today).

### 2. Tokenizer abstraction

A small interface `count_tokens(text, provider, model) -> int` with per-provider
implementations:

- Anthropic: `messages.count_tokens` (free API call) — runs in-container where the
  client exists.
- OpenAI: `tiktoken` (local; add `tiktoken` to the agent base image).
- Gemini: `models.count_tokens`.

Because counting happens in-container alongside the live client, the engine side
needs no tokenizer. Unit-tested behind a fake implementation.

### 3. Projection engine (`estimator/projection.py`)

A pure module — no I/O, no network. This is the testable heart.

Inputs: `harness_overhead_tokens`, `avg_output_tokens_per_turn` (anchor; falls
back to a documented default if the run produced none), preset turn counts, and an
`avg_tool_result_tokens_per_turn` documented constant.

Growing-context model, for a workflow of `N` turns:

```
for turn i in 1..N:
    input_i = harness_overhead
            + (i - 1) * (avg_output_tokens_per_turn + avg_tool_result_tokens_per_turn)
total_input  = sum(input_i for i in 1..N)
total_output = N * avg_output_tokens_per_turn
total_tokens = total_input + total_output
```

Cost is computed via the existing `providers/pricing.py` (per-model OpenRouter
rates) from `total_input` / `total_output`.

Output: one row per preset:

```
{ "preset": "Standard", "turns": 10,
  "est_input_tokens": ..., "est_output_tokens": ..., "est_total_tokens": ...,
  "est_cost": "$0.0421" | "unavailable" }
```

### 4. Surfacing

- **Engine model:** add a `HarnessProjection` structure to `FinalResult` carrying
  the preset rows, the per-turn `harness_overhead_tokens`, and the component
  breakdown.
- **API:** add `harness_projection` to `RunResponse`.
- **CLI:** a "Harness token projection" block in the result box — a compact
  Light/Standard/Heavy → tokens/cost table, the per-turn overhead, and the top
  component contributors.
- **UI:** a panel in `RunResultCard` — the projection table plus a component
  breakdown bar. Fields optional so older stored runs still parse.

## Data flow

```
run (MCP path)
  └─ agent container
       ├─ tools/list on each MCP server  ─┐
       ├─ load skill bodies               ├─ count tokens (provider tokenizer)
       ├─ system prompt                  ─┘   └─ harness-report.json
       └─ records own measured usage  ─────────┘
  └─ engine reads harness-report.json
       ├─ folds measured usage into run telemetry totals  (closes the gap)
       └─ estimator/projection.py  →  preset rows + cost (pricing.py)
            └─ FinalResult.harness_projection  →  API  →  CLI / UI
```

## Assumptions (surfaced to the user)

- `avg_output_tokens_per_turn` is anchored to the measured run; if unavailable, a
  documented default is used.
- `avg_tool_result_tokens_per_turn` is a documented constant.
- Preset turn counts (3 / 10 / 25) are documented and tunable.
- All projection output is labeled an **estimate**, with the assumptions visible —
  no false precision.

## Error handling

- Missing/partial `harness-report.json` → projection "unavailable"; run unaffected.
- `tools/list` failure for a server → that server contributes 0 overhead with a
  noted warning; other servers still counted.
- Tokenizer/count failure → fall back to a character-based approximation for that
  component, flagged in the report.
- Unknown model in pricing → cost "unavailable" (existing behavior).

## Testing strategy

- **Projection math** (`estimator/projection.py`): offline unit tests — growing
  vs. flat sanity, preset scaling, cost via a fake pricing catalog, anchor
  fallback.
- **Report parsing:** engine reads `harness-report.json` from fixtures, including
  missing/partial/malformed → unavailable.
- **Tokenizer interface:** behind a fake; per-provider impls smoke-tested where the
  SDK is available.
- **Surfacing:** API response shape test; CLI and UI render with sample data.
- **In-container gap:** measured usage from the report is added to run totals
  (unit test on the folding logic).

## Rollout / dependencies

- Adds `tiktoken` to the agent base image (OpenAI token counting).
- Builds on existing `providers/pricing.py` (PR: telemetry-usage-cost) and
  `UsageTracker`.
- Logically follows `remove-default-models`; rebase once that merges.
