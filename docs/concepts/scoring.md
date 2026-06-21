# Scoring

After the recommended stack executes a task, validtr scores the output to measure how well the stack actually performed. The validation score is a weighted composite of four dimensions, each capturing a different quality signal.

## What the Score Means

The validation score (0–100) is a quality measurement of the output, not a confidence level. A score of 55 means the stack produced something that partially works — maybe it ran without errors and the code is syntactically valid, but the generated tests failed and the LLM judge found missing requirements. A score of 95+ means the output is production-quality with only minor non-deterministic variance.

The score drives the retry loop. If it falls below the threshold (default 95), the engine analyzes which dimensions scored low, adjusts the stack accordingly, and tries again.

## Dimensions

### Test Passing (40%)

The largest weight. After execution, validtr generates tests from the task spec and output artifacts, then runs them in an isolated container. This dimension reflects the pass rate.

A low test-passing score means the output doesn't satisfy the requirements that were extracted from the task description. This might indicate the stack needs a different MCP server, a stronger model, or a different prompt strategy.

### Execution (25%)

Did the task run to completion without errors? This is a binary signal — the stack either produced output successfully or it crashed.

A zero here typically means a dependency issue, a missing tool, or a framework incompatibility. The retry controller responds by adjusting the provisioned environment.

### Syntax Validity (15%)

Are the output files syntactically valid? For code tasks, validtr parses Python files, checks imports, and verifies the code can be loaded without syntax errors.

This catches cases where the LLM produced malformed code — unclosed brackets, invalid syntax, broken imports.

### Completeness (20%)

An LLM-as-judge assessment. A separate LLM call evaluates the output against the original task description and success criteria, scoring how thoroughly the requirements were fulfilled.

This catches gaps that automated tests might miss — for example, the task asked for JWT auth but the output only has basic password auth. The judge never sees the agent's reasoning or intermediate steps, only the final output.

## How the Score Drives Retries

The retry controller maps low-scoring dimensions to targeted adjustments:

| Low Dimension | Adjustment |
|---|---|
| Test passing | Add MCP servers, re-search for tools, adjust prompt strategy |
| Execution | Check dependencies, try different framework, fix environment |
| Syntax validity | Upgrade to a stronger model |
| Completeness | Upgrade model, add missing capabilities via MCP servers |

Each retry generates fresh tests, since a different stack may produce structurally different output.

## Task-Type Scorers

Currently only code tasks have a dedicated scorer. Other task types (infrastructure, research, automation) fall back to the code scorer. Dedicated scorers for other task types are planned — see the [roadmap](/roadmap/implemented-vs-roadmap).

| Task Type | Test Passing | Execution | Syntax/Validity | Completeness |
|---|---|---|---|---|
| Code | 40% | 25% | 15% | 20% |
| Infrastructure | 40% | — | 20% safety, 20% validity | 20% |
| Research | 30% + 40% LLM judge | — | 15% source quality | 15% coherence |
| Automation | 40% | 25% | — | 20% + 15% |

Only the code scorer row is implemented today. The other rows reflect the planned design.
