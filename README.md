# validtr

Test the quality and cost of your Agent Harness.

<p align="center">
 <img src="images/validtr-logo.png?raw=true" alt="Logo" width="70%" height="70%" />
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-0F172A"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-1f6feb">
  <img alt="Go" src="https://img.shields.io/badge/go-1.22%2B-0ea5e9">
  <img alt="Runtime" src="https://img.shields.io/badge/runtime-Docker-16a34a">
</p>

<p align="center"><strong>Natural language in. Production-grade agentic harness out.</strong></p>

An Agent Harness CLI tool that takes a natural language task description, recommends the optimal agentic stack (LLM, agent framework, MCP servers, agent skills), provisions that stack in Docker containers, executes the task, generates tests, and scores the result.

If the score falls below 95%, it iterates — adjusting the stack and retrying until the threshold is met or max retries are exhausted.

## Why validtr

- Recommends the best-fit stack for your task instead of hardcoding one provider/toolchain.
- Runs the generated solution in isolated Docker environments.
- Generates tests from the task spec and output, then scores quality.
- Retries with stack adjustments until it hits a quality threshold.

## Prerequisites

- **Docker** — containers are the execution environment
- **Python 3.12+**
- **Go 1.22+**
- **At least one LLM provider API key** (Anthropic, OpenAI, or Gemini)

## Quickstart

### 1) Set up the Python engine

```bash
cd validtr-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2) Build the CLI

```bash
cd validtr-cli && go build -o ../validtr . && cd ..
```

### 3) Configure API keys

Set API keys as environment variables (never stored in config files):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."
export TAVILY_API_KEY="tvly-..."
```

Optionally create `~/.validtr/config.yaml` for non-secret settings:

```yaml
provider: anthropic
score_threshold: 95.0
max_attempts: 3
timeout: 300
engine_addr: "http://127.0.0.1:4041"
```

### Optional extras

A few subsystems are soft dependencies — the engine runs fine without them and falls
back to built-in defaults:

| Extra | `pip install -e ".[...]"` | Enables | Opt-in env var |
|---|---|---|---|
| `cascade` | `cascade` | Live, cost-ordered model registry (replaces the static model list) | always on if installed |
| `compress` | `compress` | Semantic artifact compression for the completeness judge (pulls in torch/transformers — heavy) | `VALIDTR_COMPRESS_ARTIFACTS=1` |
| — | install [SkillSpector](https://github.com/NVIDIA/SkillSpector) separately (not on PyPI) onto the engine's `PYTHONPATH` | Drops high-risk skills before they're surfaced in recommendations | `VALIDTR_SCAN_SKILLS=1` |

### 4) Start the engine

```bash
cd validtr-engine
source .venv/bin/activate
uvicorn api.server:app --host 127.0.0.1 --port 4041
```

### 5) Run your first task

```bash
./validtr run "Build a FastAPI web app with JWT auth" --provider anthropic --model claude-sonnet-4-6
```

> `--model` is required — validtr has no default model for any provider.

![](images/sample.png)

## Usage

### Run a task

```bash
# Single provider (--model is required; validtr has no default model)
./validtr run "Build a FastAPI web app with JWT auth" --provider anthropic --model claude-sonnet-4-6

# Dry run — recommend a stack but don't execute
validtr run "Automate PR code reviews" --provider anthropic --model claude-sonnet-4-6 --dry-run

# Override defaults
validtr run "Build a CLI in Go" \
  --provider openai \
  --model gpt-4o \
  --max-attempts 5 \
  --score-threshold 90 \
  --timeout 600
```

### MCP server discovery

```bash
validtr mcp list
validtr mcp search "kubernetes"
validtr mcp info filesystem
```

### CLI configuration

```bash
validtr config set provider anthropic
validtr config set score-threshold 90
validtr config set max-attempts 5
validtr config set timeout 600
validtr config set engine-addr http://127.0.0.1:4041
validtr config show
```

## Docker Runtime Behavior

Docker is only used during task execution paths.

- `validtr run "<task>"`: builds and runs an **agent container** for the task output, then runs generated tests in a separate isolated **test-runner container**.
- `validtr run --compare ...`: same as `run`, repeated per provider (so containers are started for each provider run).
- `validtr run --dry-run ...`: **no execution/test containers**; it only analyzes the task and returns a recommendation.
- `validtr mcp ...` and `validtr config ...`: do not start containers.

Notes:

- Container/image lifecycle is managed by the Python engine.
- Docker must be running and accessible to complete non-dry-run task execution.

## Web UI

validtr includes a local web UI for submitting tasks, viewing results, and browsing run history.

### Setup

```bash
cd validtr-ui
npm install
```

### Run the UI

Make sure the engine is running first (see step 4 above - `uvicorn api.server:app --host 127.0.0.1 --port 4041`), then:

```bash
cd validtr-ui
npm run dev
```

Open **http://localhost:4040** in your browser.

The dev server proxies API requests to the engine at `localhost:4041` automatically.

### Production build

```bash
cd validtr-ui
npm run build
```

Output is written to `validtr-ui/dist/`.

## Architecture

```
User's Machine
├── Web UI (React @ :4040)   ← Browser-based dashboard
│   └── HTTP ──────────────►
├── Go CLI (Cobra)           ← Single binary, user-facing
│   └── HTTP ──────────────►  Python Engine (FastAPI @ :4041)
│                               ├── Task Analyzer
│                               ├── Recommendation Engine
│                               ├── Stack Provisioner
│                               ├── Execution Engine
│                               ├── Test Generator
│                               ├── Scoring Engine
│                               └── Retry Controller
│                                       │
│                               Docker Environment (per run)
│                               ├── Agent container
│                               ├── MCP server containers
│                               └── Test runner container
│
└── External APIs
    ├── LLM APIs (Anthropic, OpenAI, Gemini)
    ├── Web Search (Tavily)
    ├── MCP Registries (mcp.so, Smithery)
    ├── Skills catalogs (GitHub: anthropics/skills, awesome-copilot, pm-skills)
    └── PyPI (model/framework freshness checks, optional cascadeflow registry)
```

## Project Structure

```
validtr/
├── validtr-cli/                  # Go CLI (Cobra)
│   ├── main.go
│   ├── cmd/
│   │   ├── root.go
│   │   ├── run.go
│   │   ├── mcp.go
│   │   └── config.go
│   └── internal/
│       ├── engine/               # Python engine HTTP client
│       └── config/               # YAML config + env credentials
│
├── validtr-ui/                   # Web UI (React + TypeScript + Tailwind)
│   └── src/
│       ├── api/                  # Typed API client
│       ├── components/           # ScoreGauge, StackCard, RunForm, etc.
│       ├── hooks/                # useRunTask, useHealthCheck
│       ├── pages/                # Dashboard, RunDetail
│       └── store/                # Zustand state management
│
├── validtr-engine/               # Python Engine
│   ├── api/                      # FastAPI server + routes
│   ├── analyzer/                 # Task classification + extraction
│   ├── recommender/              # Web search + MCP/skills/framework registries + LLM reasoning
│   ├── provisioner/              # Docker Compose generation + Dockerfiles
│   ├── executor/                 # Container execution + tracing
│   ├── test_generator/           # LLM-generated tests + runner
│   ├── scorer/                   # Composite scoring (per task type)
│   ├── retry/                    # Failure analysis + stack adjustments
│   ├── providers/                # LLM provider abstraction (Anthropic, OpenAI, Gemini)
│   ├── models/                   # Pydantic models (task, stack, result, score)
│   └── orchestrator.py           # Top-level pipeline: analyze → recommend → execute → test → score → retry
```

## Pipeline

```
1. Task Analyzer        → Classifies task, extracts requirements, generates testable assertions
2. Recommendation Engine → Web search + MCP/skills/framework registries + LLM reasoning → StackRecommendation
3. Stack Provisioner     → Generates Docker Compose, builds containers
4. Execution Engine      → Runs task in container, captures traces and artifacts
5. Test Generator        → LLM generates tests from task spec + output (never sees agent reasoning)
6. Scoring Engine        → Composite score: test passing (40%) + execution (25%) + syntax (15%) + completeness (20%)
7. Retry Controller      → If score < 95%: analyze failures, adjust stack, loop back to step 2
```

## Scoring

Currently only Code tasks have a dedicated scorer. Other task types fall back to the Code scorer.

| Task Type      | Test Passing | Execution | Syntax/Validity | Completeness | Status      |
|----------------|-------------|-----------|-----------------|--------------|-------------|
| Code           | 40%         | 25%       | 15%             | 20%          | Implemented |
| Infrastructure | 40%         | —         | 20% safety, 20% validity | 20% | Uses code scorer fallback |
| Research       | 30% + 40% LLM judge | — | 15% source quality | 15% coherence | Uses code scorer fallback |
| Automation     | 40%         | 25%       | —               | 20% + 15%    | Uses code scorer fallback |

## Supported Providers

| Provider  | Env Var
|-----------|----------------------------|
| Anthropic | ANTHROPIC_API_KEY
| OpenAI    | OPENAI_API_KEY
| Gemini    | GOOGLE_API_KEY

## How Validtr Differentiates From Evals

Where it overlaps

  - Both are multi-turn agent evaluation pipelines.
  - Both use automated grading (tests + rubric/model-based checks).
  - Both care about traces/outcomes, not just final text output.

  Key differences

  - Scope: your app is an end-to-end local runner/recommender/provisioner (analyze → recommend → execute in Docker → generate tests → score → retry). Anthropic’s post is a framework for
    building eval systems, not a single fixed product pipeline.
  - Eval design maturity: Anthropic emphasizes eval harness design, multiple graders (code/model/human), capability vs regression suites, multiple trials per task, calibration. Your app is
    currently a single-run operational pipeline with a fixed scoring structure and retry loop.
  - Statistical rigor: Anthropic stresses repeated trials and suite-level metrics; your current flow appears mostly one-attempt-per-loop scoring (with retries for task completion), not formal
    capability/regression benchmarking at suite scale.
  - Human-in-the-loop: Anthropic explicitly includes human grading/calibration; your app is fully automated today.
  - Primary goal: your tool is closer to “get best stack and deliver output now”; the Anthropic guidance is “measure agent quality/reliability over time”.

## License

MIT
