"""Usage-tracking wrapper around an LLMProvider.

Wrap a real provider once with UsageTracker and pass it everywhere in the
pipeline (analyzer, recommender, executor, test generator, scorer). Every
completion accumulates token usage, keyed by model so cost can be computed per
model afterwards.

Note: this only sees calls the engine makes through this provider. An agent
running inside a Docker/MCP container makes its own API calls, which the engine
cannot observe — those tokens are not counted here.
"""

from providers.base import CompletionResponse, LLMProvider, Message, ToolDefinition


class UsageTracker(LLMProvider):
    """Transparent proxy that accumulates token usage across all completions."""

    def __init__(self, inner: LLMProvider):
        # Intentionally does not call super().__init__: this proxy holds no
        # api_key/model of its own and delegates everything to the inner provider.
        self._inner = inner
        self.input_tokens = 0
        self.output_tokens = 0
        # model id -> {"input": int, "output": int}
        self.by_model: dict[str, dict[str, int]] = {}

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> CompletionResponse:
        resp = await self._inner.complete(
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
        self._record(resp)
        return resp

    async def complete_json(
        self,
        messages: list[Message],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> CompletionResponse:
        # Delegate to the inner provider's own complete_json (which may have
        # provider-specific JSON handling) rather than the base default.
        resp = await self._inner.complete_json(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._record(resp)
        return resp

    def _record(self, resp: CompletionResponse) -> None:
        self.input_tokens += resp.input_tokens
        self.output_tokens += resp.output_tokens
        model = resp.model or self._inner.model
        bucket = self.by_model.setdefault(model, {"input": 0, "output": 0})
        bucket["input"] += resp.input_tokens
        bucket["output"] += resp.output_tokens
