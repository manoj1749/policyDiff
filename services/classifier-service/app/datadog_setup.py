"""
datadog_setup.py — Initializes Datadog LLM Observability.

Imported once at service startup (before any Gemini calls).
Exports the @llm and @workflow decorators for use in other modules.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ── Pre-seed env vars so ddtrace's lazy readers pick them up ──────────────────
# ddtrace reads several DD_* vars at import time via its own config system.
# Setting them explicitly here (before any ddtrace import) ensures they are
# visible regardless of how the process was launched (ddtrace-run vs direct).
def _seed_dd_env() -> None:
    _defaults = {
        "DD_LLMOBS_ENABLED": "1",
        "DD_LLMOBS_AGENTLESS_ENABLED": "1",
        "DD_LLMOBS_ML_APP": os.getenv("DD_LLMOBS_ML_APP", "policydiff"),
        "DD_SITE": os.getenv("DD_SITE", "us5.datadoghq.com"),
        "DD_API_KEY": os.getenv("DD_API_KEY", ""),
    }
    for key, val in _defaults.items():
        if val:
            os.environ[key] = val

_seed_dd_env()

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

    api_key = os.getenv("DD_API_KEY", "")
    site = os.getenv("DD_SITE", "us5.datadoghq.com")

    if not api_key:
        logger.warning("DD_API_KEY not set — Datadog LLM Observability will not send traces.")
        return

    try:
        LLMObs.enable(
            ml_app=ml_app,
            api_key=api_key,
            site=site,
            agentless_enabled=True,
        )
        logger.info(
            "Datadog LLM Observability enabled (ml_app=%s, site=%s, agentless=True).",
            ml_app, site,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to enable Datadog LLM Observability: %s", exc)
