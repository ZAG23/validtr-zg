# Changelog

## 2026-06-21

Hardening and quality pass across the engine, CLI, and UI — container isolation,
correct retry behavior, robust test scoring, accurate run telemetry, and docs
brought in line with the implementation.

### Runtime / Security

- Hardened the agent execution container: hard memory (2g), PID (512), and CPU
  (2-core) limits; all Linux capabilities dropped; `no-new-privileges`; runs as
  non-root (`nobody`) with a writable `tmpfs` `/tmp` so MCP stdio servers
  (npx/uvx) keep working. Previously the container ran unconstrained while
  executing generated code with injected credentials.
- Per-run resource cleanup: temporary run directories and per-run agent images
  are now reclaimed after each attempt instead of accumulating.

### Engine

- Retry: execution-failure adjustments now emit a handled `re_search` action, so
  failure hints actually reach the recommendation engine's supplemental MCP
  search. Previously they were emitted as an unhandled action and silently
  dropped.
- Test runner: parse pytest's JUnit XML report (`--junit-xml`) instead of
  scraping stdout; dropped the contradictory `-v`/`-q` flags. A missing or
  malformed report now surfaces as an explicit error rather than a silent zero
  (test passing is 40% of the composite score).
- Telemetry: a new `UsageTracker` aggregates token usage across every
  engine-side LLM call (analyze, recommend, test-gen, score, direct execution);
  run token totals, wall-clock duration, and cost are now populated on results.
- Cost is computed from OpenRouter's public pricing catalog, cached locally with
  a 24h TTL — no hardcoded or hand-maintained rates. Models that can't be matched
  report cost as `unavailable` rather than a misleading `$0.00`.
- Scoring: removed ~70 lines of duplicated logic in `CodeScorer` (no behavior
  change). Default passing threshold aligned to 95 across engine, CLI, and UI.
- Removed unused `SafetyLimits` fields (`max_llm_calls`, `max_tool_calls`).
- **Breaking:** removed all default models. Every provider previously had a
  hardcoded default (e.g. `claude-sonnet-4-20250514`); a model must now be
  specified explicitly. Omitting one raises an error.

### Harness token projection

- After a run, validtr projects token usage and cost for representative workflow
  sizes (**Light** = 3 turns, **Standard** = 10, **Heavy** = 25) with the
  validated agent harness (LLM + agent + MCP servers + skills), using a
  growing-context model.
- The estimate uses the **real** system prompt and the run's **measured** token
  usage; MCP servers and skills are sized with documented, tunable per-component
  token estimates (the single-shot agent does not introspect live tool schemas).
- The agent now emits a `harness-report.json` capturing its real in-container
  token usage, which is folded into the run totals — **closing the previous
  in-container telemetry gap** for the executed agent call.
- Surfaced in the CLI result box and the UI run result card. Projection figures
  are labeled estimates. See `docs/concepts/harness-projection.md`.

### CLI

- **Breaking:** `--max-retries` renamed to `--max-attempts` (and the
  `max_attempts` config key); the value is now the total number of attempts, so
  `1` means a single attempt with no retry. Update any `~/.validtr/config.yaml`
  using `max_retries`.
- **Breaking:** `--model` is now required (there is no default model).
- Run output now reports Tokens / Time / Cost and the harness token projection.

### UI

- The run result card shows a telemetry footer (tokens, duration, cost,
  artifacts) and a harness token-projection panel.

### Docs

- Aligned docs with the implementation: passing threshold documented as 95,
  Python prerequisite corrected to 3.12+, and the CLI↔engine transport documented
  as HTTP/JSON (gRPC marked as a future target).
- Stopped tracking the compiled ~11MB CLI binary in git; build it with
  `go build -o validtr ./validtr-cli`.

### Known limitations

- The in-container agent is single-shot and does not invoke its recommended MCP
  tools or skills, so harness projection sizes those components with heuristic
  estimates rather than real tool schemas. Making the agent actually use its
  harness is planned as separate work.

## 2026-03-08

### Docs

- Added full VitePress docs site for `validtr`.
- Added Mintlify-style custom theme aligned to `validtr` logo colors.
- Added core guides (`overview`, `install`, `quickstart`, `project-layout`).
- Added concept pages (`architecture`, `pipeline`, `scoring`, `task-lifecycle`).
- Added deep reference pages (CLI, API, configuration, providers, models, recommendation, MCP registry, skills registry, execution runtime, testing/validation, retry strategy, prompt contracts).
- Added operations pages (`troubleshooting`, `limitations`).
- Added GitHub Pages deploy workflow.

## Changelog Format

- Date-based entries for now.
- Newest entry at top.
- Group changes by area (`Docs`, `CLI`, `Engine`, `Runtime`, `CI/CD`).
