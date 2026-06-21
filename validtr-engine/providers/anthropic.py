"""Anthropic Claude provider."""

import logging

import anthropic

from providers.base import CompletionResponse, LLMProvider, Message, ToolDefinition

logger = logging.getLogger(__name__)


def _strip_json_fences(text: str) -> str:
    """Remove surrounding markdown code fences from a JSON response."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped[3:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic's Claude models."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        super().__init__(api_key, model)
        # Pass api_key only if explicitly provided; otherwise the SDK
        # falls back to the ANTHROPIC_API_KEY environment variable.
        self.client = anthropic.AsyncAnthropic(
            **({"api_key": api_key} if api_key else {}),
        )

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """Convert our messages to Anthropic format. Returns (system, messages)."""
        system = None
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system = msg.content
            elif msg.role == "tool":
                api_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            elif msg.role == "assistant" and msg.tool_calls:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    })
                api_messages.append({"role": "assistant", "content": content})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        return system, api_messages

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert tools to Anthropic format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> CompletionResponse:
        system, api_messages = self._convert_messages(messages)

        # Anthropic has no schemaless JSON mode, and current Claude models reject
        # assistant-message prefill (the conversation must end with a user turn),
        # so steer JSON output via a system-prompt instruction instead.
        if json_mode:
            json_instruction = (
                "Respond with only a single valid JSON object. Do not include any "
                "text before or after the JSON, and do not wrap it in markdown code fences."
            )
            system = f"{system}\n\n{json_instruction}" if system else json_instruction

        kwargs: dict = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            response = await self.client.messages.create(**kwargs)
        except anthropic.APIError as e:
            logger.error("Anthropic API error: %s", e)
            raise

        # Parse response
        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        # Defensively strip markdown code fences so callers can json.loads() directly.
        if json_mode:
            content = _strip_json_fences(content)

        return CompletionResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            stop_reason=response.stop_reason or "",
        )
