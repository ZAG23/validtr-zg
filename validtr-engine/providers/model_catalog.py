"""Live LLM model catalog, backed by cascadeflow's model registry when available.

Mirrors the pattern in `providers/pricing.py`: models and their deprecation status
change faster than this codebase gets updated, so retry upgrade-paths and the
recommendation prompt should read from a live registry instead of a hardcoded list.
cascadeflow (https://pypi.org/project/cascadeflow/) publishes exactly this kind of
registry. It's an optional dependency — if it isn't installed, callers fall back to
a small static list so behavior degrades gracefully rather than breaking.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import cascadeflow as _cascadeflow
except ImportError:
    _cascadeflow = None

# validtr provider name -> cascadeflow provider slug
_PROVIDER_SLUG = {"anthropic": "anthropic", "openai": "openai", "gemini": "google"}

# Used only when cascadeflow isn't installed, or its registry has nothing for a
# provider. Kept intentionally small — this is a fallback, not a source of truth.
_FALLBACK_MODELS = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-8"],
    "openai": ["gpt-4o-mini", "gpt-4o", "o3"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro"],
}


def _registry():
    if _cascadeflow is None:
        return None
    try:
        return _cascadeflow.get_default_registry()
    except Exception as e:
        logger.warning("Could not load cascadeflow model registry: %s", e)
        return None


def list_models(provider: str) -> list[dict]:
    """Return known models for a provider as plain dicts, cheapest first.

    Each dict has at least {"name", "deprecated"}; entries from cascadeflow also
    include "cost" and "context_window". Deprecated models are excluded.
    """
    registry = _registry()
    if registry is not None:
        slug = _PROVIDER_SLUG.get(provider, provider)
        try:
            entries = registry.list_by_provider(slug)
        except Exception as e:
            logger.warning("cascadeflow list_by_provider(%s) failed: %s", slug, e)
            entries = []

        models = [
            {
                "name": e.name,
                "deprecated": bool(getattr(e, "deprecated", False)),
                "cost": getattr(e, "cost", None),
                "context_window": getattr(e, "context_window", None),
            }
            for e in entries
        ]
        active = [m for m in models if not m["deprecated"]]
        if active:
            active.sort(key=lambda m: (m["cost"] is None, m["cost"]))
            return active

    return [{"name": name, "deprecated": False, "cost": None, "context_window": None}
            for name in _FALLBACK_MODELS.get(provider, [])]


def upgrade_path(provider: str) -> list[str]:
    """Return model names for a provider, weakest/cheapest first — used to pick
    the next model up when a retry needs a stronger one."""
    return [m["name"] for m in list_models(provider)]


def is_deprecated(provider: str, model: str) -> bool:
    """Best-effort check; returns False (assume current) if unknown."""
    registry = _registry()
    if registry is None:
        return False
    slug = _PROVIDER_SLUG.get(provider, provider)
    try:
        entry = registry.get(model)
    except Exception:
        return False
    if entry is None or getattr(entry, "provider", slug) != slug:
        return False
    return bool(getattr(entry, "deprecated", False))


def format_for_prompt() -> str:
    """Render the live catalog as text for injection into the recommendation prompt.

    Falls back to a short static blurb if cascadeflow isn't installed or returns
    nothing, so the prompt never ends up empty.
    """
    lines = []
    for provider in ("anthropic", "openai", "gemini"):
        models = list_models(provider)
        if not models:
            continue
        names = ", ".join(m["name"] for m in models)
        lines.append(f"- {provider}: {names}")

    if lines:
        return "\n".join(lines)

    return (
        "- anthropic: claude-sonnet-4-6 (fast, strong default), claude-opus-4-8 (most capable)\n"
        "- openai: gpt-4o-mini, gpt-4o, o3\n"
        "- gemini: gemini-2.5-flash (fastest/cheapest), gemini-2.5-pro"
    )
