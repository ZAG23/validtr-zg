# Providers

The engine supports three provider adapters through a common interface.

## Supported Providers

- `anthropic`
- `openai`
- `gemini`

There are no default models. A model must be specified explicitly via `--model`
(CLI) or `model` (API request); omitting it raises an error.

## Env Vars

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`

## Unified Interface

All providers implement:

- `complete(messages, tools, temperature, max_tokens, json_mode)`
- `complete_json(...)`

Unified response fields:

- `content`
- `tool_calls`
- `input_tokens`
- `output_tokens`
- `model`
- `stop_reason`

## Provider-Specific Notes

### Anthropic

- Uses `anthropic.AsyncAnthropic`.
- JSON mode is steered via a system-prompt instruction (the model is asked to
  return only a JSON object), and markdown code fences are stripped from the
  response. Assistant-message prefill is **not** used — current Claude models
  reject it (the conversation must end with a user message).

### OpenAI

- Uses `openai.AsyncOpenAI` chat completions.
- JSON mode uses `response_format={"type": "json_object"}`.

### Gemini

- Uses `google.genai` client.
- JSON mode sets `response_mime_type="application/json"`.

## Unknown Provider Handling

`get_provider(...)` raises `ValueError` for unsupported provider names, and also
when no model is supplied (there is no default model).
