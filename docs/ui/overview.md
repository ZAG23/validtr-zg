# Web UI

The validtr web UI is a local dashboard for submitting tasks, viewing results, and browsing run history.

It runs at `http://localhost:4040` and communicates with the Python engine at `localhost:4041`.

## What You Can Do

- **Submit tasks** with a provider and API key
- **View results** including score gauge, dimension breakdown, and stack details
- **Browse run history** stored locally in the browser
- **Cancel in-progress runs** with real-time elapsed time tracking
- **Configure options** like model override, score threshold, max retries, and timeout

## Architecture

```
Browser (localhost:4040)
    │
    │  HTTP (proxied in dev, direct in prod)
    ▼
Python Engine (localhost:4041)
    │
    ▼
Docker, LLM APIs, MCP Registries
```

The UI is a standalone React application. In development, Vite proxies `/api` and `/health` requests to the engine. In production, the built assets can be served by the Go CLI binary or any static file server behind the engine.

## Tech Stack

| Technology | Purpose |
|---|---|
| React 19 | Component framework |
| TypeScript | Type safety |
| Tailwind CSS v4 | Styling |
| Zustand | State management with localStorage persistence |
| Vite 6 | Dev server and build tool |
| Recharts | Charts (used in comparison views) |
