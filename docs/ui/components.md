# UI Components

The UI is built from reusable components in `validtr-ui/src/components/`.

## Score Gauge

`ScoreGauge` renders a circular SVG gauge that fills proportionally to the score (0–100). The arc color reflects the score range:

- Green (>= 90)
- Yellow (>= 70)
- Red (< 70)

## Score Breakdown

`ScoreBreakdown` displays each scoring dimension as a horizontal bar with the score fraction (e.g., `37/40`). Each bar is color-coded by its fill percentage.

Dimensions for code tasks:

| Dimension | Weight |
|---|---|
| Test passing | 40 |
| Execution | 25 |
| Syntax validity | 15 |
| Completeness | 20 |

## Stack Card

`StackCard` displays the recommended stack: provider, model, framework, MCP servers (as tags), skills (as tags), and any adjustment notes from retries.

## Attempt Timeline

`AttemptTimeline` renders when a run has multiple attempts. Each node shows the attempt number, score, provider/model, and adjustment notes. The best attempt is highlighted.

## Run Form

`RunForm` handles task submission. It manages local state for all form fields and delegates execution to the `useRunTask` hook. The provider selector updates the API key placeholder to show the relevant environment variable name.

## Recent Runs List

`RecentRunsList` reads from the Zustand store and renders a clickable list of past runs. Each entry shows the run ID, task (truncated), score, provider, and relative timestamp.

## Layout

- `AppShell` — flex layout with sidebar and scrollable content area
- `Sidebar` — fixed navigation with engine online/offline indicator
