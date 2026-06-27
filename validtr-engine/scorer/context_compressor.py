"""Optional artifact compression for the completeness judge, via headroom.

headroom (PyPI: `headroom-ai[all]`) does semantic token compression instead of the
blind per-file truncation `_summarize_artifacts_for_judge` does today, which can cut a
file off mid-function and confuse the judge. It pulls in a large transitive dependency
tree (torch, transformers, sentence-transformers...), so it's opt-in via the
`compress` extra and the VALIDTR_COMPRESS_ARTIFACTS=1 env var, not a default dependency.
Without it (or the env var), this module is a no-op and the caller's own truncation
logic runs unchanged.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import headroom as _headroom
except ImportError:
    _headroom = None


def compression_enabled() -> bool:
    import os
    return _headroom is not None and os.environ.get("VALIDTR_COMPRESS_ARTIFACTS") == "1"


def compress_text(text: str, model_limit: int) -> str | None:
    """Compress a single block of text down to roughly model_limit tokens.

    Returns None if compression is unavailable/disabled or fails, so the caller
    falls back to its own truncation logic.
    """
    if not compression_enabled():
        return None

    try:
        result = _headroom.compress(
            messages=[{"role": "user", "content": text}],
            model_limit=model_limit,
            optimize=True,
        )
        return result.messages[0]["content"]
    except Exception as e:
        logger.warning("headroom compression failed, falling back to truncation: %s", e)
        return None
