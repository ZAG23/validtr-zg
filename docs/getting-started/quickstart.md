# Quickstart

## 1. Start the engine

```bash
cd validtr-engine
source .venv/bin/activate
uvicorn api.server:app --host 127.0.0.1 --port 4041
```

## 2. Run your first task

`--model` is required — validtr has no default model. Pass a current model id for
your provider (e.g. `claude-sonnet-4-6`, `claude-opus-4-8`).

```bash
./validtr run "Build a FastAPI web app with JWT auth" --provider anthropic --model claude-sonnet-4-6
```

## 3. Optional modes

```bash
# Recommend only, no Docker execution
./validtr run "Automate PR reviews" --provider anthropic --model claude-sonnet-4-6 --dry-run
```

> `--compare` currently applies a single `--model` id to every provider, so it
> only works when the providers share a model id. Per-provider model selection
> is a planned follow-up.
