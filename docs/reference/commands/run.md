# `validtr run`

Run task analysis, recommendation, execution, testing, scoring, and retries.

## Usage

```bash
validtr run "Build a FastAPI app with JWT auth" --provider anthropic --model claude-sonnet-4-6
```

## Flags

- `--provider`: `anthropic`, `openai`, `gemini`
- `--model`: **required** — model id (validtr has no default model)
- `--compare`: comma-separated providers
- `--dry-run`: recommendation only
- `--max-attempts`: retry limit
- `--score-threshold`: pass threshold
- `--timeout`: execution timeout seconds

## Modes

## Single provider

```bash
validtr run "Build a CLI in Go" --provider openai --model gpt-4o
```

## Compare

```bash
validtr run "Build CRUD API" --compare anthropic,openai,gemini --model <shared-model-id>
```

Behavior:

- providers run sequentially
- provider with missing API key is skipped
- the single `--model` id is applied to every provider, so compare currently
  only works for a model id the providers share; per-provider model selection
  is a planned follow-up

## Dry-run

```bash
validtr run "Automate PR code reviews" --provider anthropic --model claude-sonnet-4-6 --dry-run
```

Behavior:

- no execution or test containers
- returns analyzed task + recommended stack

## Environment

- provider API key must be set for selected provider
- optional `TAVILY_API_KEY` enriches recommendation search
