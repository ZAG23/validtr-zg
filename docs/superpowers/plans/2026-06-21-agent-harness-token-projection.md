# Agent Harness Token Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project token usage + cost for common workflows (Light/Standard/Heavy) with the validated agent harness, from real harness introspection, and surface it in the run results.

**Architecture:** The agent (already connected to the provider and recommended MCP servers) writes a `harness-report.json` artifact: tokenized harness overhead (system prompt + MCP tool schemas + skill bodies), a per-component breakdown, and its own measured token usage. The engine reads it back, folds measured usage into run telemetry (closing the in-container gap), runs a pure growing-context projection (`estimator/projection.py`) priced via the existing `providers/pricing.py`, and surfaces the result through the API, CLI, and UI.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic (engine), Go/Cobra (CLI), React+TS (UI), pytest, `tiktoken` (OpenAI token counting in-container).

**Spec:** `docs/superpowers/specs/2026-06-21-agent-harness-token-projection-design.md`

**Branch note:** This branch (`harness-token-projection`) is based on `main`; rebase onto `remove-default-models` once that merges. Run engine tests with `../.venv/bin/python -m pytest` from `validtr-engine/`.

---

## File Structure

- Create: `validtr-engine/models/projection.py` — Pydantic models (`HarnessComponent`, `ProjectionRow`, `HarnessProjection`).
- Create: `validtr-engine/estimator/__init__.py`, `validtr-engine/estimator/projection.py` — pure projection math + cost assembly.
- Create: `validtr-engine/estimator/harness_report.py` — parse/validate `harness-report.json`.
- Create: `validtr-engine/estimator/tokenizer.py` — `count_tokens(text, provider)` abstraction + per-provider impls.
- Modify: `validtr-engine/provisioner/compose_generator.py` — agent emits `harness-report.json`.
- Modify: `validtr-engine/provisioner/templates/agent-base.Dockerfile` — add `tiktoken`.
- Modify: `validtr-engine/orchestrator.py` — read report, fold measured usage, build projection, set on `FinalResult`.
- Modify: `validtr-engine/models/score.py` — add `harness_projection` to `FinalResult`.
- Modify: `validtr-engine/api/routes/run.py` — add `harness_projection` to `RunResponse`.
- Modify: `validtr-cli/internal/engine/client.go`, `validtr-cli/cmd/run.go` — projection block in result box.
- Modify: `validtr-ui/src/api/types.ts`, `validtr-ui/src/components/RunResultCard.tsx` — projection panel.
- Create: tests under `validtr-engine/tests/` for each engine module.

---

## Task 1: Projection data models

**Files:**
- Create: `validtr-engine/models/projection.py`
- Test: `validtr-engine/tests/test_projection_models.py`

- [ ] **Step 1: Write the failing test**

```python
# validtr-engine/tests/test_projection_models.py
from models.projection import HarnessComponent, ProjectionRow, HarnessProjection


def test_models_construct_with_defaults():
    comp = HarnessComponent(kind="mcp_server", name="filesystem", tokens=1840)
    row = ProjectionRow(preset="Standard", turns=10, est_input_tokens=1, est_output_tokens=2, est_total_tokens=3)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_projection_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.projection'`

- [ ] **Step 3: Write minimal implementation**

```python
# validtr-engine/models/projection.py
"""Models for agent-harness token projection."""

from pydantic import BaseModel, Field


class HarnessComponent(BaseModel):
    """Per-component token attribution for the harness overhead."""

    kind: str  # "system_prompt" | "mcp_server" | "skill"
    name: str
    tokens: int = 0


class ProjectionRow(BaseModel):
    """Projected usage for one preset workflow size."""

    preset: str
    turns: int
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    est_total_tokens: int = 0
    est_cost: str = "unavailable"


class HarnessProjection(BaseModel):
    """Forward-looking token/cost projection for the validated harness."""

    overhead_tokens: int = 0
    avg_output_tokens_per_turn: int = 0
    components: list[HarnessComponent] = Field(default_factory=list)
    rows: list[ProjectionRow] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_projection_models.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add validtr-engine/models/projection.py validtr-engine/tests/test_projection_models.py
git commit -m "feat(projection): add harness projection models"
```

---

## Task 2: Projection math (growing-context)

**Files:**
- Create: `validtr-engine/estimator/__init__.py` (empty), `validtr-engine/estimator/projection.py`
- Test: `validtr-engine/tests/test_projection.py`

- [ ] **Step 1: Write the failing test**

```python
# validtr-engine/tests/test_projection.py
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
    assert presets["Light"]["est_output_tokens"] == 3 * projection.DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN


def test_project_total_is_input_plus_output():
    rows = projection.project(overhead_tokens=1000, avg_output_per_turn=300)
    for r in rows:
        assert r["est_total_tokens"] == r["est_input_tokens"] + r["est_output_tokens"]


def test_heavier_preset_costs_more_tokens():
    rows = {r["preset"]: r["est_total_tokens"] for r in projection.project(1000, 300)}
    assert rows["Light"] < rows["Standard"] < rows["Heavy"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_projection.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'estimator'`

- [ ] **Step 3: Write minimal implementation**

```python
# validtr-engine/estimator/__init__.py
```

```python
# validtr-engine/estimator/projection.py
"""Pure growing-context token projection for the agent harness."""

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_projection.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add validtr-engine/estimator/__init__.py validtr-engine/estimator/projection.py validtr-engine/tests/test_projection.py
git commit -m "feat(projection): growing-context token projection math"
```

---

## Task 3: Assemble priced HarnessProjection

**Files:**
- Modify: `validtr-engine/estimator/projection.py`
- Test: `validtr-engine/tests/test_projection.py` (add)

- [ ] **Step 1: Write the failing test**

```python
# add to validtr-engine/tests/test_projection.py
from models.projection import HarnessComponent
from estimator.projection import build_projection

CATALOG = {"anthropic/claude-sonnet-4": {"input": 3e-06, "output": 1.5e-05}}


def test_build_projection_prices_rows():
    proj = build_projection(
        overhead_tokens=1000,
        avg_output_per_turn=300,
        components=[HarnessComponent(kind="system_prompt", name="system", tokens=1000)],
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        catalog=CATALOG,
    )
    light = next(r for r in proj.rows if r.preset == "Light")
    expected = light.est_input_tokens * 3e-06 + light.est_output_tokens * 1.5e-05
    assert light.est_cost == f"${expected:.4f}"
    assert proj.overhead_tokens == 1000
    assert proj.components[0].name == "system"


def test_build_projection_unavailable_cost_when_unpriced():
    proj = build_projection(
        overhead_tokens=1000, avg_output_per_turn=300, components=[],
        provider="anthropic", model="unknown-model", catalog=CATALOG,
    )
    assert all(r.est_cost == "unavailable" for r in proj.rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_projection.py::test_build_projection_prices_rows -q`
Expected: FAIL with `ImportError: cannot import name 'build_projection'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to validtr-engine/estimator/projection.py
from models.projection import HarnessComponent, HarnessProjection, ProjectionRow
from providers import pricing


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
            cost = raw["est_input_tokens"] * rates["input"] + raw["est_output_tokens"] * rates["output"]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_projection.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add validtr-engine/estimator/projection.py validtr-engine/tests/test_projection.py
git commit -m "feat(projection): assemble priced HarnessProjection"
```

---

## Task 4: Harness report parsing

**Files:**
- Create: `validtr-engine/estimator/harness_report.py`
- Test: `validtr-engine/tests/test_harness_report.py`

- [ ] **Step 1: Write the failing test**

```python
# validtr-engine/tests/test_harness_report.py
import json
import os

from estimator.harness_report import HarnessReport, read_harness_report

SAMPLE = {
    "harness_overhead_tokens": 4213,
    "components": [
        {"kind": "system_prompt", "name": "system", "tokens": 412},
        {"kind": "mcp_server", "name": "filesystem", "tokens": 1840},
    ],
    "measured_input_tokens": 8123,
    "measured_output_tokens": 1004,
    "avg_output_tokens_per_turn": 251,
    "tokenizer": "anthropic",
}


def test_read_valid_report(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        json.dump(SAMPLE, f)
    report = read_harness_report(path)
    assert isinstance(report, HarnessReport)
    assert report.harness_overhead_tokens == 4213
    assert report.measured_total_tokens == 8123 + 1004
    assert report.components[1].name == "filesystem"


def test_missing_file_returns_none(tmp_path):
    assert read_harness_report(os.path.join(tmp_path, "nope.json")) is None


def test_malformed_file_returns_none(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        f.write("{not json")
    assert read_harness_report(path) is None


def test_partial_report_fills_defaults(tmp_path):
    path = os.path.join(tmp_path, "harness-report.json")
    with open(path, "w") as f:
        json.dump({"harness_overhead_tokens": 100}, f)
    report = read_harness_report(path)
    assert report.harness_overhead_tokens == 100
    assert report.measured_total_tokens == 0
    assert report.components == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_harness_report.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'estimator.harness_report'`

- [ ] **Step 3: Write minimal implementation**

```python
# validtr-engine/estimator/harness_report.py
"""Parsing for the in-container harness-report.json artifact."""

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from models.projection import HarnessComponent

logger = logging.getLogger(__name__)


class HarnessReport(BaseModel):
    """Token telemetry emitted by the agent for harness projection."""

    harness_overhead_tokens: int = 0
    components: list[HarnessComponent] = Field(default_factory=list)
    measured_input_tokens: int = 0
    measured_output_tokens: int = 0
    avg_output_tokens_per_turn: int = 0
    tokenizer: str = ""

    @property
    def measured_total_tokens(self) -> int:
        return self.measured_input_tokens + self.measured_output_tokens


def read_harness_report(path: str) -> HarnessReport | None:
    """Read and validate a harness report. Returns None if missing/malformed."""
    try:
        with open(path) as f:
            data = json.load(f)
        return HarnessReport.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as e:
        logger.warning("Could not read harness report %s: %s", path, e)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_harness_report.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add validtr-engine/estimator/harness_report.py validtr-engine/tests/test_harness_report.py
git commit -m "feat(projection): harness-report.json parsing"
```

---

## Task 5: Tokenizer abstraction

**Files:**
- Create: `validtr-engine/estimator/tokenizer.py`
- Test: `validtr-engine/tests/test_tokenizer.py`

- [ ] **Step 1: Write the failing test**

```python
# validtr-engine/tests/test_tokenizer.py
from estimator import tokenizer


def test_approx_count_is_chars_over_four():
    # Fallback approximation: ~4 chars/token, min 1 for non-empty.
    assert tokenizer.approx_count("") == 0
    assert tokenizer.approx_count("a" * 8) == 2
    assert tokenizer.approx_count("abc") == 1  # rounds up to at least 1


def test_count_tokens_unknown_provider_uses_approx():
    text = "x" * 40
    assert tokenizer.count_tokens(text, provider="mystery") == tokenizer.approx_count(text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_tokenizer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'estimator.tokenizer'`

- [ ] **Step 3: Write minimal implementation**

```python
# validtr-engine/estimator/tokenizer.py
"""Token counting for harness components.

Runs in-container where the provider client/tiktoken is available. Falls back to
a character-based approximation when a precise tokenizer is unavailable.
"""

import logging
import math

logger = logging.getLogger(__name__)


def approx_count(text: str) -> int:
    """~4 chars/token approximation; at least 1 token for non-empty text."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def count_tokens(text: str, provider: str) -> int:
    """Count tokens for `text` using the provider's tokenizer; fall back to approx.

    OpenAI uses local tiktoken. Anthropic/Gemini precise counts are network calls
    and are done by the agent via its live client; here we provide tiktoken +
    approximation so the function is usable engine-side too.
    """
    if provider == "openai":
        try:
            import tiktoken

            enc = tiktoken.get_encoding("o200k_base")
            return len(enc.encode(text))
        except Exception as e:  # tiktoken missing or encode error
            logger.debug("tiktoken unavailable, approximating: %s", e)
            return approx_count(text)
    return approx_count(text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_tokenizer.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add validtr-engine/estimator/tokenizer.py validtr-engine/tests/test_tokenizer.py
git commit -m "feat(projection): tokenizer abstraction with approx fallback"
```

---

## Task 6: Agent emits harness-report.json

**Files:**
- Modify: `validtr-engine/provisioner/compose_generator.py` (agent loop template — the `_write_agent_loop` string)
- Modify: `validtr-engine/provisioner/templates/agent-base.Dockerfile`
- Test: `validtr-engine/tests/test_harness_report_builder.py`

Extract the report-building logic into a pure helper so it can be tested without a container.

- [ ] **Step 1: Write the failing test**

```python
# validtr-engine/tests/test_harness_report_builder.py
from estimator.harness_report import build_report_dict


def test_build_report_dict_sums_components():
    report = build_report_dict(
        system_prompt_tokens=400,
        mcp_tool_tokens={"filesystem": 1840, "github": 900},
        skill_tokens={"k8skill": 1961},
        measured_input=8000,
        measured_output=1000,
        turns=4,
        tokenizer="anthropic",
    )
    assert report["harness_overhead_tokens"] == 400 + 1840 + 900 + 1961
    assert report["measured_input_tokens"] == 8000
    assert report["avg_output_tokens_per_turn"] == 250  # 1000 / 4
    kinds = {(c["kind"], c["name"]) for c in report["components"]}
    assert ("mcp_server", "github") in kinds
    assert ("skill", "k8skill") in kinds


def test_build_report_dict_zero_turns_no_div_by_zero():
    report = build_report_dict(100, {}, {}, 0, 0, turns=0, tokenizer="openai")
    assert report["avg_output_tokens_per_turn"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_harness_report_builder.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_report_dict'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to validtr-engine/estimator/harness_report.py
def build_report_dict(
    system_prompt_tokens: int,
    mcp_tool_tokens: dict[str, int],
    skill_tokens: dict[str, int],
    measured_input: int,
    measured_output: int,
    turns: int,
    tokenizer: str,
) -> dict:
    """Build the harness-report.json payload from counted components + usage."""
    components = [{"kind": "system_prompt", "name": "system", "tokens": system_prompt_tokens}]
    components += [{"kind": "mcp_server", "name": n, "tokens": t} for n, t in mcp_tool_tokens.items()]
    components += [{"kind": "skill", "name": n, "tokens": t} for n, t in skill_tokens.items()]
    overhead = sum(c["tokens"] for c in components)
    avg_output = (measured_output // turns) if turns > 0 else 0
    return {
        "harness_overhead_tokens": overhead,
        "components": components,
        "measured_input_tokens": measured_input,
        "measured_output_tokens": measured_output,
        "avg_output_tokens_per_turn": avg_output,
        "tokenizer": tokenizer,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_harness_report_builder.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Wire the agent loop to emit the report**

In `validtr-engine/provisioner/compose_generator.py`, inside the `_write_agent_loop` template string, after the agent finishes its generation loop and before exit, add logic that: (a) calls `tools/list` on each connected MCP server and counts tokens of the JSON schemas; (b) counts the system prompt tokens; (c) counts skill body tokens; (d) writes `/workspace/output/harness-report.json` using the same field names as `build_report_dict`. Use the in-container provider client for counting where available (Anthropic `client.messages.count_tokens`, OpenAI `tiktoken`, Gemini `client.models.count_tokens`), falling back to `len(text)//4`.

Because the agent loop is an embedded string (not imported), replicate the small counting/writing inline; keep field names identical to `build_report_dict` output so `read_harness_report` parses it.

- [ ] **Step 6: Add tiktoken to the agent base image**

In `validtr-engine/provisioner/templates/agent-base.Dockerfile`, add `tiktoken` to the `pip install` list:

```dockerfile
RUN pip install --no-cache-dir \
    anthropic \
    openai \
    google-genai \
    httpx \
    pydantic \
    tiktoken
```

- [ ] **Step 7: Commit**

```bash
git add validtr-engine/estimator/harness_report.py validtr-engine/tests/test_harness_report_builder.py validtr-engine/provisioner/compose_generator.py validtr-engine/provisioner/templates/agent-base.Dockerfile
git commit -m "feat(projection): agent emits harness-report.json; add tiktoken"
```

---

## Task 7: Engine integration — fold usage + build projection

**Files:**
- Modify: `validtr-engine/models/score.py` (add `harness_projection` to `FinalResult`)
- Modify: `validtr-engine/orchestrator.py`
- Test: `validtr-engine/tests/test_orchestrator_projection.py`

- [ ] **Step 1: Write the failing test (pure folding helper)**

```python
# validtr-engine/tests/test_orchestrator_projection.py
from estimator.harness_report import HarnessReport
from estimator.projection import projection_from_report

CATALOG = {"anthropic/claude-sonnet-4": {"input": 3e-06, "output": 1.5e-05}}


def test_projection_from_report_builds_rows():
    report = HarnessReport(
        harness_overhead_tokens=1000,
        measured_input_tokens=8000,
        measured_output_tokens=1000,
        avg_output_tokens_per_turn=250,
    )
    proj = projection_from_report(report, provider="anthropic", model="claude-sonnet-4-20250514", catalog=CATALOG)
    assert proj.overhead_tokens == 1000
    assert {r.preset for r in proj.rows} == {"Light", "Standard", "Heavy"}
    assert proj.rows[0].est_cost.startswith("$")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_orchestrator_projection.py -q`
Expected: FAIL with `ImportError: cannot import name 'projection_from_report'`

- [ ] **Step 3: Add the helper + FinalResult field**

```python
# add to validtr-engine/estimator/projection.py
from estimator.harness_report import HarnessReport


def projection_from_report(
    report: HarnessReport, provider: str, model: str, catalog: dict
) -> HarnessProjection:
    return build_projection(
        overhead_tokens=report.harness_overhead_tokens,
        avg_output_per_turn=report.avg_output_tokens_per_turn or None,
        components=report.components,
        provider=provider,
        model=model,
        catalog=catalog,
    )
```

```python
# in validtr-engine/models/score.py, add to FinalResult (import HarnessProjection at top)
from models.projection import HarnessProjection
# ... within class FinalResult(BaseModel):
    harness_projection: HarnessProjection = Field(default_factory=HarnessProjection)
```

- [ ] **Step 4: Wire orchestrator**

In `validtr-engine/orchestrator.py`, in the telemetry block added by the earlier telemetry PR (after `best_result` is built and `total_tokens`/`total_cost` are set):

```python
# Read the in-container harness report (MCP path only). It both closes the
# in-container token gap and feeds the harness projection.
from estimator.harness_report import read_harness_report
from estimator.projection import projection_from_report
import os as _os

report = None
if best and best.artifacts is not None:
    report_path = _os.path.join(
        executor.compose_gen.output_base, f"{run_id}-{best.attempt_number}",
        "workspace", "output", "harness-report.json",
    )
    report = read_harness_report(report_path)

if report is not None:
    # Fold the agent's in-container usage into the run totals.
    best_result.total_tokens += report.measured_total_tokens
    catalog = pricing.load_catalog()
    best_result.harness_projection = projection_from_report(
        report, provider=provider, model=(model or llm.model), catalog=catalog
    )
```

Note: cleanup runs after each attempt today; for this read to succeed, move the best attempt's `executor.cleanup(...)` so the best run dir survives until after the report is read (or skip cleanup for the best attempt and clean it at the end). Implement: track `best_attempt_run_id` and defer its cleanup to the end of `run_task`.

- [ ] **Step 5: Run tests**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_orchestrator_projection.py tests/test_projection.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add validtr-engine/estimator/projection.py validtr-engine/models/score.py validtr-engine/orchestrator.py validtr-engine/tests/test_orchestrator_projection.py
git commit -m "feat(projection): fold in-container usage and build projection in orchestrator"
```

---

## Task 8: API surfacing

**Files:**
- Modify: `validtr-engine/api/routes/run.py`
- Test: `validtr-engine/tests/test_run_response_projection.py`

- [ ] **Step 1: Write the failing test**

```python
# validtr-engine/tests/test_run_response_projection.py
from api.routes.run import RunResponse


def test_run_response_has_projection_field():
    resp = RunResponse(
        run_id="abc", score=90.0, passed=False, total_attempts=1, best_attempt=1,
        stack=__import__("api.routes.run", fromlist=["StackResponse"]).StackResponse(),
        dimensions=[], attempts=[], artifact_count=0, artifacts={},
    )
    # default empty projection present and serializable
    assert resp.harness_projection.rows == []
    assert "harness_projection" in resp.model_dump()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_run_response_projection.py -q`
Expected: FAIL with `AttributeError`/validation error (no `harness_projection`)

- [ ] **Step 3: Add field + populate**

In `validtr-engine/api/routes/run.py`: import `HarnessProjection` from `models.projection`, add to `RunResponse`:

```python
    harness_projection: HarnessProjection = Field(default_factory=HarnessProjection)
```

and in the `RunResponse(...)` construction at the end of `api_run_task`, add:

```python
        harness_projection=result.harness_projection,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd validtr-engine && ../.venv/bin/python -m pytest tests/test_run_response_projection.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add validtr-engine/api/routes/run.py validtr-engine/tests/test_run_response_projection.py
git commit -m "feat(projection): expose harness_projection on RunResponse"
```

---

## Task 9: CLI surfacing

**Files:**
- Modify: `validtr-cli/internal/engine/client.go`
- Modify: `validtr-cli/cmd/run.go`

- [ ] **Step 1: Add response types**

In `client.go`, add structs and fields:

```go
// ProjectionRow holds a projected workflow size.
type ProjectionRow struct {
	Preset         string `json:"preset"`
	Turns          int    `json:"turns"`
	EstTotalTokens int    `json:"est_total_tokens"`
	EstCost        string `json:"est_cost"`
}

// HarnessProjection holds the token/cost projection.
type HarnessProjection struct {
	OverheadTokens int             `json:"overhead_tokens"`
	Rows           []ProjectionRow `json:"rows"`
}
```

Add to `RunResult`:

```go
	HarnessProjection HarnessProjection `json:"harness_projection"`
```

- [ ] **Step 2: Render in printResult**

In `cmd/run.go` `printResult`, after the telemetry line, add:

```go
	if len(result.HarnessProjection.Rows) > 0 {
		fmt.Println("│")
		fmt.Printf("│  Harness token projection (per-turn overhead: %d tokens)\n", result.HarnessProjection.OverheadTokens)
		for _, r := range result.HarnessProjection.Rows {
			fmt.Printf("│    %-9s %2d turns  %8d tokens  %s\n", r.Preset, r.Turns, r.EstTotalTokens, r.EstCost)
		}
	}
```

- [ ] **Step 3: Build + vet**

Run: `cd validtr-cli && gofmt -w cmd/run.go internal/engine/client.go && go build ./... && go vet ./...`
Expected: no output (success)

- [ ] **Step 4: Commit**

```bash
git add validtr-cli/internal/engine/client.go validtr-cli/cmd/run.go
git commit -m "feat(projection): render harness projection in CLI result box"
```

---

## Task 10: UI surfacing

**Files:**
- Modify: `validtr-ui/src/api/types.ts`
- Modify: `validtr-ui/src/components/RunResultCard.tsx`

- [ ] **Step 1: Add types**

In `types.ts`, add and extend `RunResponse` (optional for stored-run compatibility):

```ts
export interface ProjectionRow {
  preset: string;
  turns: number;
  est_total_tokens: number;
  est_cost: string;
}

export interface HarnessProjection {
  overhead_tokens: number;
  rows: ProjectionRow[];
}
```

Add to `RunResponse`:

```ts
  harness_projection?: HarnessProjection;
```

- [ ] **Step 2: Render panel**

In `RunResultCard.tsx`, before the closing `</div>`, add a panel guarded by `result.harness_projection?.rows?.length`:

```tsx
{result.harness_projection?.rows?.length ? (
  <>
    <div className="border-t border-border" />
    <div>
      <h4 className="text-xs font-mono text-text-secondary mb-2">
        Harness token projection · {result.harness_projection.overhead_tokens.toLocaleString()} tokens/turn overhead
      </h4>
      <table className="w-full text-xs font-mono text-text-muted">
        <tbody>
          {result.harness_projection.rows.map((r) => (
            <tr key={r.preset}>
              <td className="py-0.5">{r.preset}</td>
              <td className="py-0.5">{r.turns} turns</td>
              <td className="py-0.5 text-right text-text-secondary">{r.est_total_tokens.toLocaleString()} tok</td>
              <td className="py-0.5 text-right text-text-secondary">{r.est_cost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </>
) : null}
```

- [ ] **Step 3: Typecheck**

Run: `cd validtr-ui && node_modules/.bin/tsc --noEmit -p tsconfig.app.json`
Expected: no output (success)

- [ ] **Step 4: Commit**

```bash
git add validtr-ui/src/api/types.ts validtr-ui/src/components/RunResultCard.tsx
git commit -m "feat(projection): harness projection panel in RunResultCard"
```

---

## Task 11: Docs + full verification

**Files:**
- Modify: `README.md` (Web UI / results section — brief mention of projection)
- Modify: `docs/concepts/scoring.md` or a new `docs/concepts/harness-projection.md` (document the model + assumptions)

- [ ] **Step 1: Document the projection model and assumptions**

Add a short section describing: preset sizes (3/10/25), the growing-context model, that overhead is measured from real introspection, and that values are estimates. State `DEFAULT_AVG_OUTPUT_TOKENS_PER_TURN` and `AVG_TOOL_RESULT_TOKENS_PER_TURN` are tunable.

- [ ] **Step 2: Full verification**

Run:
```bash
cd validtr-engine && ../.venv/bin/python -m pytest -q
cd ../validtr-cli && go build ./... && go vet ./... && go test ./...
cd ../validtr-ui && node_modules/.bin/tsc --noEmit -p tsconfig.app.json
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/
git commit -m "docs(projection): document harness token projection"
```

---

## Self-Review notes

- **Spec coverage:** capture (Task 6) · tokenizer (Task 5) · projection math + cost (Tasks 2–3) · report parsing (Task 4) · fold-in gap close + orchestrator (Task 7) · API/CLI/UI (Tasks 8–10) · assumptions/docs (Task 11). All spec sections mapped.
- **Cleanup interaction:** Task 7 Step 4 explicitly defers the best attempt's cleanup so the report file survives to be read — otherwise the per-attempt cleanup added in the retry-and-cleanup PR would delete it first.
- **Direct fast-path:** no `harness-report.json` is produced; `harness_projection` stays the default empty (rows = []), and the CLI/UI guards (`len(rows) > 0`) simply render nothing. Acceptable per spec.
- **Type consistency:** `harness-report.json` field names match across `build_report_dict`, `HarnessReport`, and the agent emitter; `ProjectionRow`/`HarnessProjection` field names match across engine model, API, CLI structs, and TS interfaces.
