"""Anthropic JSON mode must not use assistant prefill (rejected by Claude 4.6+)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from providers.anthropic import AnthropicProvider, _strip_json_fences


def _fake_response(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        model="claude-sonnet-4-6",
        stop_reason="end_turn",
    )


@pytest.fixture
def provider():
    p = AnthropicProvider(api_key="fake", model="claude-sonnet-4-6")
    # Replace the SDK client with a mock that records the create() kwargs.
    p.client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()))
    return p


@pytest.mark.asyncio
async def test_json_mode_does_not_append_assistant_prefill(provider):
    from providers.base import Message

    provider.client.messages.create.return_value = _fake_response('{"ok": true}')
    await provider.complete(messages=[Message(role="user", content="hi")], json_mode=True)

    kwargs = provider.client.messages.create.call_args.kwargs
    # No assistant prefill — the conversation must end with the user message.
    assert kwargs["messages"][-1]["role"] == "user"
    assert all(m["role"] != "assistant" for m in kwargs["messages"])
    # JSON is steered via a system-prompt instruction instead.
    assert "JSON" in kwargs["system"]


@pytest.mark.asyncio
async def test_json_mode_preserves_existing_system_prompt(provider):
    from providers.base import Message

    provider.client.messages.create.return_value = _fake_response('{"ok": true}')
    await provider.complete(
        messages=[Message(role="system", content="You are X."), Message(role="user", content="hi")],
        json_mode=True,
    )
    system = provider.client.messages.create.call_args.kwargs["system"]
    assert system.startswith("You are X.")
    assert "JSON" in system


@pytest.mark.asyncio
async def test_json_mode_strips_code_fences_from_response(provider):
    from providers.base import Message

    provider.client.messages.create.return_value = _fake_response('```json\n{"ok": true}\n```')
    resp = await provider.complete(messages=[Message(role="user", content="hi")], json_mode=True)
    assert resp.content == '{"ok": true}'


def test_strip_json_fences_plain_passthrough():
    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'
