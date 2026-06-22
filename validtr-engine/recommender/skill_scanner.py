"""Security scanning of fetched skills via NVIDIA SkillSpector.

SkillSpector (https://github.com/NVIDIA/SkillSpector) scores agent-skill content for
prompt-injection / supply-chain risk on a 0-100 scale. It is not published on PyPI, so
it can't be a normal dependency — install it yourself (see its README: `make install`,
git checkout, or Docker) onto the engine's PYTHONPATH to enable scanning. Without it,
this module is a no-op and skills are surfaced unscanned, exactly like before this
integration existed.

Scanning is opt-in via VALIDTR_SCAN_SKILLS=1, since it shells out to a LangGraph
pipeline that may itself call an LLM (`use_llm=True`) and can be slow.
"""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

try:
    from skillspector import graph as _skillspector_graph
except ImportError:
    _skillspector_graph = None

# Skills scoring at or above this are dropped from the catalog.
_RISK_THRESHOLD = 70


def scanning_enabled() -> bool:
    """Whether skill scanning should run at all (requires opt-in + the package)."""
    return _skillspector_graph is not None and os.environ.get("VALIDTR_SCAN_SKILLS") == "1"


def scan(name: str, content: str) -> dict | None:
    """Scan one skill's content. Returns {"risk_score": int, "severity": str} or None
    if scanning is unavailable/disabled or the scan itself fails — callers should treat
    None as "unknown, don't block"."""
    if not scanning_enabled():
        return None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix=f"skill-{name}-", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = _skillspector_graph.invoke({
                "input_path": path,
                "output_format": "json",
                "use_llm": True,
            })
        finally:
            os.unlink(path)

        return {
            "risk_score": result.get("risk_score", 0),
            "severity": result.get("severity", "UNKNOWN"),
        }
    except Exception as e:
        logger.warning("SkillSpector scan failed for %s: %s", name, e)
        return None


def is_high_risk(scan_result: dict | None) -> bool:
    """True only when a scan actually ran and scored above the risk threshold."""
    if scan_result is None:
        return False
    return scan_result.get("risk_score", 0) >= _RISK_THRESHOLD
