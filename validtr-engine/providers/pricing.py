"""Model pricing via OpenRouter, with a local TTL cache.

OpenRouter publishes per-token prices for every model at a public, unauthenticated
endpoint, so validtr never hardcodes (and never has to hand-maintain) rates. The
catalog is fetched once and cached locally; cost is computed from the per-model
token usage recorded by UsageTracker. Models that can't be matched report no cost
rather than a wrong one.
"""

import json
import logging
import os
import re
import time
import urllib.request

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_CACHE_TTL_SECONDS = 24 * 3600

# validtr provider name -> OpenRouter provider slug
_PROVIDER_SLUG = {"anthropic": "anthropic", "openai": "openai", "gemini": "google"}

# Trailing version/date suffixes to strip when matching against OpenRouter ids
# (e.g. "claude-sonnet-4-20250514" -> "claude-sonnet-4").
_VERSION_SUFFIX = re.compile(r"-\d{8}$|-\d{4}-\d{2}-\d{2}$|-latest$")


def _default_cache_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".validtr", "pricing-openrouter.json")


def fetch_openrouter_catalog(timeout: float = 10.0) -> dict[str, dict[str, float]]:
    """Fetch the OpenRouter model catalog.

    Returns {model_id: {"input": rate, "output": rate}} with rates in USD per token.
    """
    with urllib.request.urlopen(OPENROUTER_MODELS_URL, timeout=timeout) as resp:  # noqa: S310 (trusted https URL)
        data = json.loads(resp.read().decode("utf-8"))

    catalog: dict[str, dict[str, float]] = {}
    for entry in data.get("data", []):
        model_id = entry.get("id")
        pricing = entry.get("pricing") or {}
        prompt = pricing.get("prompt")
        completion = pricing.get("completion")
        if not model_id or prompt is None or completion is None:
            continue
        try:
            catalog[model_id] = {"input": float(prompt), "output": float(completion)}
        except (TypeError, ValueError):
            continue
    return catalog


def load_catalog(
    cache_path: str | None = None,
    ttl: int = _CACHE_TTL_SECONDS,
    fetcher=fetch_openrouter_catalog,
) -> dict[str, dict[str, float]]:
    """Return the pricing catalog, using a fresh cache when available.

    Falls back to a stale cache, then to {} on any failure. Never raises — a
    pricing lookup must not break a run.
    """
    cache_path = cache_path or _default_cache_path()

    try:
        age = time.time() - os.stat(cache_path).st_mtime
        if age < ttl:
            with open(cache_path) as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError):
        pass

    try:
        catalog = fetcher()
    except Exception as e:  # network, parse, anything
        logger.warning("Could not fetch OpenRouter pricing: %s", e)
        try:
            with open(cache_path) as f:
                return json.load(f)  # stale is better than nothing
        except (OSError, json.JSONDecodeError):
            return {}

    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(catalog, f)
    except OSError as e:
        logger.warning("Could not write pricing cache %s: %s", cache_path, e)

    return catalog


def _candidate_ids(provider: str, model: str) -> list[str]:
    slug = _PROVIDER_SLUG.get(provider, provider)
    model = model.strip()
    candidates = [f"{slug}/{model}"]
    stripped = _VERSION_SUFFIX.sub("", model)
    if stripped != model:
        candidates.append(f"{slug}/{stripped}")
    return [c.lower() for c in candidates]


def resolve_rates(
    provider: str, model: str, catalog: dict[str, dict[str, float]]
) -> dict[str, float] | None:
    """Return per-token {"input","output"} rates for (provider, model), or None."""
    if not catalog:
        return None
    lower = {k.lower(): v for k, v in catalog.items()}
    for cid in _candidate_ids(provider, model):
        if cid in lower:
            return lower[cid]
    return None


def compute_cost(
    provider: str,
    by_model: dict[str, dict[str, int]],
    catalog: dict[str, dict[str, float]],
) -> float | None:
    """Compute total USD cost from per-model token usage.

    Returns None if no model in the usage could be priced (so callers can show
    "unavailable" rather than a misleading $0.00).
    """
    total = 0.0
    priced_any = False
    for model, usage in by_model.items():
        rates = resolve_rates(provider, model, catalog)
        if rates is None:
            logger.debug("No OpenRouter price for %s/%s", provider, model)
            continue
        total += usage.get("input", 0) * rates["input"]
        total += usage.get("output", 0) * rates["output"]
        priced_any = True
    return total if priced_any else None
