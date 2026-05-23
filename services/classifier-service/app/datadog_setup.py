"""
datadog_setup.py — Initializes Datadog LLM Observability.

Imported once at service startup (before any Gemini calls).
Exports the @llm and @workflow decorators for use in other modules.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from ddtrace.llmobs import LLMObs
    from ddtrace.llmobs.decorators import llm, workflow  # noqa: F401 — re-exported

    _DD_AVAILABLE = True
except ImportError:
    _DD_AVAILABLE = False
    logger.warning(
        "ddtrace not installed. Datadog LLM Observability will be disabled. "
        "Install with: pip install ddtrace"
    )

    # Provide no-op decorators so the rest of the code doesn't need to branch.
    def llm(*args, **kwargs):  # type: ignore[override]
        def decorator(fn):
            return fn
        return decorator if args and callable(args[0]) else decorator  # type: ignore[return-value]

    def workflow(*args, **kwargs):  # type: ignore[override]
        def decorator(fn):
            return fn
        return decorator if args and callable(args[0]) else decorator  # type: ignore[return-value]


def init_datadog(ml_app: str = "policydiff") -> None:
    """Call once at application startup to activate LLM Observability."""
    if not _DD_AVAILABLE:
        logger.info("Skipping Datadog LLM Observability init (ddtrace not installed).")
        return
    try:
        LLMObs.enable(ml_app=ml_app)
        logger.info("Datadog LLM Observability enabled (ml_app=%s).", ml_app)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to enable Datadog LLM Observability: %s", exc)
