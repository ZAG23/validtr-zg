# Dashboard

The dashboard is the main page of the UI, available at `/`.

## Layout

The page is split into two sections:

- **Left** — task input form and result display
- **Right** — recent runs list

## Submitting a Task

1. Enter a task description in the text area.
2. Select a provider (Anthropic, OpenAI, or Gemini).
3. Enter an API key if one is not set on the engine.
4. Click **Run Validation**.

Click **Options** to expand advanced settings:

| Option | Default | Description |
|---|---|---|
| Model override | _(provider default)_ | Specific model ID to use |
| Max retries | 1 | Number of retry attempts if score is below threshold |
| Score threshold | 90 | Minimum score before retrying |
| Timeout | 300s | Maximum execution time per attempt |
| Dry run | off | Recommend a stack without executing |

## Result Display

After a run completes, the result card shows:

- **Score gauge** — circular visualization of the composite score (0–100), color-coded by range
- **Score breakdown** — bar chart of individual dimensions (test passing, execution, syntax validity, completeness) with their weighted scores
- **Stack info** — the recommended LLM, framework, MCP servers, and skills
- **Attempt timeline** — if retries occurred, shows each attempt with its score and adjustment notes
- **Artifacts** — list of generated file names

## Recent Runs

The right sidebar shows previous runs stored in the browser's localStorage (up to 50). Click any run to reload its result into the main display.

Run history persists across page reloads but is local to the browser — it is not synced to the engine or shared between devices.

## Running State

While a task is executing, the form displays:

- Elapsed time counter
- A **Cancel** button that aborts the request
- An animated progress indicator

Runs can take several minutes depending on task complexity and provider response time.
