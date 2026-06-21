"""Tests for the UsageTracker provider wrapper."""

import pytest

from providers.base import CompletionResponse, LLMProvider
from providers.usage import UsageTracker


class FakeProvider(LLMProvider):
    """Provider that returns canned responses and records call counts."""

    def __init__(self, responses):
        self._responses = list(responses)
        self._i = 0
        self.complete_calls = 0
        self.complete_json_calls = 0

    @property
    def default_model(self) -> str:
        return "fake-model"

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"

    def _next(self) -> CompletionResponse:
        resp = self._responses[self._i]
        self._i += 1
        return resp

    async def complete(self, messages, tools=None, temperature=0.0, max_tokens=4096, json_mode=False):
        self.complete_calls += 1
        return self._next()

    async def complete_json(self, messages, temperature=0.0, max_tokens=4096):
        self.complete_json_calls += 1
        return self._next()


@pytest.mark.asyncio
async def test_accumulates_tokens_across_calls():
    inner = FakeProvider([
        CompletionResponse(input_tokens=100, output_tokens=50, model="m1"),
        CompletionResponse(input_tokens=10, output_tokens=5, model="m1"),
    ])
    tracker = UsageTracker(inner)
    await tracker.complete(messages=[])
    await tracker.complete(messages=[])
    assert tracker.input_tokens == 110
    assert tracker.output_tokens == 55
    assert tracker.total_tokens == 165


@pytest.mark.asyncio
async def test_per_model_breakdown():
    inner = FakeProvider([
        CompletionResponse(input_tokens=100, output_tokens=50, model="m1"),
        CompletionResponse(input_tokens=200, output_tokens=20, model="m2"),
        CompletionResponse(input_tokens=1, output_tokens=1, model="m1"),
    ])
    tracker = UsageTracker(inner)
    await tracker.complete(messages=[])
    await tracker.complete(messages=[])
    await tracker.complete(messages=[])
    assert tracker.by_model == {
        "m1": {"input": 101, "output": 51},
        "m2": {"input": 200, "output": 20},
    }


@pytest.mark.asyncio
async def test_complete_json_is_tracked_once():
    inner = FakeProvider([CompletionResponse(input_tokens=7, output_tokens=3, model="m1")])
    tracker = UsageTracker(inner)
    await tracker.complete_json(messages=[])
    assert inner.complete_json_calls == 1
    assert inner.complete_calls == 0  # no double-dispatch through complete()
    assert tracker.total_tokens == 10


@pytest.mark.asyncio
async def test_falls_back_to_inner_model_when_response_model_blank():
    inner = FakeProvider([CompletionResponse(input_tokens=5, output_tokens=5, model="")])
    tracker = UsageTracker(inner)
    await tracker.complete(messages=[])
    assert "fake-model" in tracker.by_model


def test_proxies_identity_properties():
    inner = FakeProvider([])
    tracker = UsageTracker(inner)
    assert tracker.provider_name == "fake"
    assert tracker.model == "fake-model"
    assert tracker.default_model == "fake-model"
