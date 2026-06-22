# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this is

**validtr** is an agent-harness CLI tool. You give it a natural-language task description; it
recommends an agentic stack (LLM provider/model, agent framework, MCP servers, skills), provisions
it in Docker, executes the task, generates tests from the task spec, scores the result
(composite 0-100), and retries with adjustments until a score threshold is met or attempts run out.

Three independently-versioned components live as sibling directories in one repo (not a
monorepo build tool — just plain sibling dirs):
- `validtr-cli/` — Go CLI, talks HTTP/JSON to the engine
- `validtr-engine/` — Python/FastAPI engine that owns the actual pipeline and all Docker lifecycle
- `validtr-ui/` — React/TS web UI, also talks HTTP/JSON to the engine
- `docs/` — VitePress docs site, deployed to GitHub Pages

**`docs/roadmap/implemented-vs-roadmap.md` is the authoritative source of truth for what's
actually implemented.** `architecture-v3.md` at the repo root is a forward-looking design doc that
describes features (gRPC transport, `validtr history`/`stack push/pull/browse`/`ui` CLI commands,
community stack registry, non-code scorers) that **do not exist yet**. When the two conflict,
trust the roadmap doc, not architecture-v3.md.

## Directory structure

```
README.md                    user-facing overview, quickstart
architecture-v3.md            forward-looking design doc (aspirational, not current state)
docs/                          VitePress site
  roadmap/implemented-vs-roadmap.md   <- authoritative current-status doc
  concepts/                    architecture, pipeline, scoring, task-lifecycle, harness-projection
  development/                 local-dev.md, testing.md, release-workflow.md
  reference/                   cli, api, configuration, env-vars, providers, models, etc.
tests/test_output.py          NOT a test of validtr itself — example of generated-output validation

validtr-cli/                   Go CLI
  main.go, cmd/                 root.go, run.go, mcp.go, config.go (cobra commands)
  internal/config/              YAML config + env-var credential resolution
  internal/engine/client.go     HTTP/JSON client to the Python engine

validtr-engine/                 Python FastAPI engine
  api/                          server.py, routes/{run,mcp,config}.py
  orchestrator.py               top-level pipeline entry point (run_task())
  analyzer/                     TaskAnalyzer — LLM call producing a TaskDefinition
  recommender/                  RecommendationEngine — web search + MCP/skills/framework registry + LLM reasoning
                                 (skill_scanner.py: optional SkillSpector risk scan, soft-import)
  provisioner/                  ComposeGenerator, Dockerfile templates
  executor/                     ExecutionEngine — Docker Compose (with MCP sidecars) or direct LLM fast-path
  test_generator/                generates + runs pytest tests from task spec (never sees agent trace)
  scorer/                       ScoringEngine -> code_scorer.py (only code-task scorer exists)
                                 (context_compressor.py: optional headroom compression, soft-import)
  retry/                        RetryController, analysis.py (model upgrade path now from providers/model_catalog.py)
  providers/                    base.py (LLMProvider ABC) + anthropic.py, openai.py, gemini.py, pricing.py, usage.py,
                                 model_catalog.py (cascadeflow-backed live model registry, soft-import)
  models/                       Pydantic models: task, stack, result, test_result, score, projection
  estimator/                     harness token/cost projection (most actively developed subsystem)
  tests/                        pytest suite, ~21 files, one per subsystem

validtr-ui/                    React 19 + TS, Vite, Tailwind, Zustand, Recharts
  src/{api,components,hooks,pages,store,styles,lib}
```

## Pipeline (orchestrator.py::run_task, 7 stages)

1. **TaskAnalyzer** — LLM produces a `TaskDefinition` (type/domain/requirements/complexity/success_criteria)
2. **RecommendationEngine** — produces a `StackRecommendation` (provider/model/MCP servers/skills)
3/4. **ExecutionEngine** — `execute()` (full Docker Compose w/ MCP sidecars) when stack has MCP
   servers, else `execute_direct()` (fast path, single LLM call, no Docker). Agent containers run
   hardened: capabilities dropped, non-root, mem/pid/cpu caps, tmpfs `/tmp`
   (`_container_security_kwargs` in `executor/engine.py`)
5. **TestGenerator** — LLM generates tests from task spec + execution output only, runs them
   isolated, parses results from pytest JUnit XML
6. **ScoringEngine** — composite: Test passing 40%, Execution 25%, Syntax 15%, Completeness 20%
   (LLM judge). Code-task scorer only; other task types fall back to it.
7. **RetryController** — if score < threshold, analyzes failures, adjusts the stack
   (stronger model, add MCP server), loops back to step 2. Up to `max_attempts`.

Key abstraction: `LLMProvider` ABC (`providers/base.py`) unifies Anthropic/OpenAI/Gemini behind
`complete()`/`complete_json()`. **There is no default model anywhere** — `--model` is mandatory,
enforced both in the Go CLI (`cmd/run.go`) and in `LLMProvider.__init__`. Don't add a default.

Entry points: CLI `validtr-cli/main.go` → `cmd.Execute()`; engine `validtr-engine/api/server.py`
(FastAPI, routers at `/api`, `/api/mcp`, `/api/config`, CORS restricted to `http://localhost:4040`).

## Build / run / test / lint

```bash
# Engine (Python)
cd validtr-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.server:app --host 127.0.0.1 --port 4041 --reload
pytest
ruff check .          # line-length 100, target py312, select E/F/I/N/W

# CLI (Go)
cd validtr-cli
go build -o ../validtr .
go test ./...

# UI
cd validtr-ui
npm install
npm run dev           # :4040, proxies API to :4041
npm run build          # tsc -b && vite build

# Docs
cd docs
npm install
npm run docs:dev
npm run docs:build
```

**Only CI**: `.github/workflows/docs-gh-pages.yml` builds/deploys the VitePress docs on push to
`main` touching `docs/**`. There is **no CI for Go tests, pytest, or lint** — run these locally
before considering a change complete.

## Code conventions

**Python (engine)**
- Module-level docstring describing the module's role, at the top of every file
- Pydantic `BaseModel` for all data contracts; `str, Enum` for enums (`TaskType`, `Complexity`, `MCPTransport`)
- `logger = logging.getLogger(__name__)` per module; orchestrator logs use `[N/7]`-prefixed
  pipeline-stage lines
- Async-first; use `asyncio.gather` to parallelize independent work (see test generation +
  completeness judging in `orchestrator.py`)
- try/except around external calls (Docker, LLM APIs), log context, then re-raise
- Security comments explain *why* (e.g. path-traversal guard in `executor/engine.py`, container
  hardening rationale in `_container_security_kwargs` docstring)
- Constants for weights/limits at module top (e.g. `TEST_PASSING_WEIGHT = 40` in `scorer/code_scorer.py`)
- Factory pattern for provider dispatch: `get_provider()` in `providers/base.py` dynamically
  imports/dispatches by string name — follow this pattern when adding a provider
- ruff-enforced: 100-char lines, import sorting, naming

**Go (CLI)**
- One file per command group in `cmd/`, `init()` registers flags/subcommands (standard Cobra pattern)
- `fmt.Errorf("...: %w", err)` everywhere
- Plain stdlib `testing`, no testify
- `// Name does X` doc comments above exported identifiers
- Comment intent explicitly when something is a security boundary, e.g.
  `// API keys and credentials are NEVER stored here`

## Testing

- **Python**: `validtr-engine/tests/`, pytest + pytest-asyncio (`asyncio_mode = "auto"`), roughly
  one file per subsystem (`test_models.py`, `test_providers.py`, `test_scorer.py`,
  `test_retry.py`, `test_projection.py`, etc.). Docker/provider-API integration paths are not
  fully unit-isolated — be aware tests may have real-world side effects if mocks are removed.
- **Go**: only `validtr-cli/internal/config/config_test.go` exists — covers config load/save
  roundtrip, `Set()` per key (including rejecting `api-key` from being stored), env-var resolution.
- **`tests/test_output.py` at repo root is not a validtr test** — it's a template illustrating what
  the Test Generator produces for a generated FastAPI+JWT app. Don't treat it as part of the
  engine's own test suite.

## Environment variables / config

- Provider keys (required, never stored in config file): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
- `TAVILY_API_KEY` — used by the recommendation engine's web search
- MCP-server-specific credentials surfaced dynamically by registry metadata (e.g. `DATABASE_URL`,
  `GITHUB_TOKEN`, `AWS_ACCESS_KEY_ID`, `KUBECONFIG`)
- Injected into agent containers at runtime: `VALIDTR_RUN_ID`, `VALIDTR_PROVIDER`, `VALIDTR_MODEL`
- Non-secret config: `~/.validtr/config.yaml` (`provider`, `score_threshold`, `max_attempts`,
  `timeout`, `engine_addr`) — template at `validtr-engine/config.example.yaml`, loaded/saved by
  `validtr-cli/internal/config/config.go`. CLI `--config <path>` overrides the path.

## Git workflow

- `main` branch, topic branches like `<feature>-<desc>` (e.g. `harness-token-projection`,
  `remove-default-models`, `scorer-dedup`), merged via PR (`Merge pull request #N from
  AdminTurnedDevOps/<branch>`)
- Substantive code commits use conventional-commit prefixes: `feat(projection): ...`,
  `refactor(projection): ...`, or plain imperative sentences for fixes
  (`Fix retired Anthropic model IDs...`)
- Docs-only/site commits tend to be terse single words (`"re"`, `"reorder"`) — not representative
  of the convention for code changes; follow the conventional-commit style for code.
