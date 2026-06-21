"""Token counting for harness components.

Runs in-container where the provider client/tiktoken is available. Falls back to
a character-based approximation when a precise tokenizer is unavailable.
"""

import logging
import math

logger = logging.getLogger(__name__)


def approx_count(text: str) -> int:
    """~4 chars/token approximation; at least 1 token for non-empty text."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def count_tokens(text: str, provider: str) -> int:
    """Count tokens for `text` using the provider's tokenizer; fall back to approx.

    OpenAI uses local tiktoken. Anthropic/Gemini precise counts are network calls
    and are done by the agent via its live client; here we provide tiktoken +
    approximation so the function is usable engine-side too.
    """
    if provider == "openai":
        try:
            import tiktoken

            enc = tiktoken.get_encoding("o200k_base")
            return len(enc.encode(text))
        except Exception as e:  # tiktoken missing or encode error
            logger.debug("tiktoken unavailable, approximating: %s", e)
            return approx_count(text)
    return approx_count(text)
