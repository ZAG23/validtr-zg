# UI Setup

## Prerequisites

- **Node.js 18+** and npm
- The Python engine running at `localhost:4041` (see [Quickstart](/getting-started/quickstart))

## Install

```bash
cd validtr-ui
npm install
```

## Start the Dev Server

```bash
cd validtr-ui
npm run dev
```

Open **http://localhost:4040** in your browser.

The Vite dev server proxies API requests (`/api/*` and `/health`) to the engine at `localhost:4041` automatically, so no CORS configuration is needed during development.

## Production Build

```bash
cd validtr-ui
npm run build
```

Output is written to `validtr-ui/dist/`. These static files can be served by any HTTP server or embedded into the Go CLI binary via `go:embed`.

## API Key Configuration

The UI needs an API key for the selected LLM provider. You can either:

1. **Paste it in the UI** — the API key field is next to the provider selector on the dashboard. Keys are not stored; they are sent per-request only.

2. **Set it on the engine** — export the environment variable in the shell where uvicorn runs:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."
```

If neither is provided, the engine returns a `401` with a message indicating which variable to set.
