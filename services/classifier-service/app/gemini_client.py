"""
gemini_client.py — Sends prompts to Gemini 2.0 Flash with Datadog LLM tracing.
Uses the current google-genai SDK (google.genai).
"""
from __future__ import annotations

import json
import logging
import re
import time

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from app.config_loader import settings
from app.datadog_setup import llm

logger = logging.getLogger(__name__)

# Configure Gemini client once at import time.
_client = genai.Client(api_key=settings.gemini_api_key)


@llm(model_name=settings.gemini_model, model_provider="google", ml_app="policydiff")
def call_gemini(prompt: str) -> str:
    """
    Send a prompt to Gemini and return the raw text response.
    Decorated with @llm so every call creates a Datadog LLM span.
    Manual LLMObs.annotate adds input/output so the span is visible
    in the Datadog LLM Observability dashboard.
    """
    try:
        from ddtrace.llmobs import LLMObs
        LLMObs.annotate(
            input_data=[{"role": "user", "content": prompt}],
        )
    except Exception:
        pass  # never block classification if Datadog annotation fails

    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    result_text = response.text

    try:
        from ddtrace.llmobs import LLMObs
        LLMObs.annotate(
            output_data=[{"role": "assistant", "content": result_text}],
        )
    except Exception:
        pass

    return result_text



def _extract_json(raw: str) -> dict:
    """
    Parse JSON from the model response, stripping markdown fences if present.
    Raises ValueError if parsing fails.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


_STRICT_SUFFIX = (
    "\n\nCRITICAL: Your response must be a single valid JSON object with no extra text, "
    "no markdown fences, and no commentary."
)

_RATE_LIMIT_EXCEPTIONS = (genai_errors.ClientError,)


def _call_with_backoff(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini with exponential backoff on 429 rate-limit errors."""
    delay = 5
    for attempt in range(max_retries):
        try:
            return call_gemini(prompt)
        except Exception as exc:
            exc_str = str(exc)
            is_rate_limit = (
                isinstance(exc, _RATE_LIMIT_EXCEPTIONS)
                and ("429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str)
            )
            if is_rate_limit and attempt < max_retries - 1:
                logger.warning(
                    "Gemini rate limited (429). Waiting %ds before retry %d/%d…",
                    delay, attempt + 1, max_retries - 1,
                )
                time.sleep(delay)
                delay *= 2
            else:
                raise
    raise RuntimeError("Gemini call failed after max retries")  # unreachable


def call_gemini_with_retry(prompt: str) -> dict:
    """
    Call Gemini and parse the JSON response.
    - Retries on 429 rate limits with exponential backoff (via _call_with_backoff)
    - Retries once with a stricter prompt suffix if JSON parsing fails
    Raises RuntimeError after all attempts are exhausted.
    """
    # First attempt (with 429 backoff)
    try:
        raw = _call_with_backoff(prompt)
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "Gemini JSON parse failed on first attempt: %s. Retrying with strict prompt.", exc
        )

    # Second attempt — stricter prompt (with 429 backoff)
    try:
        raw = _call_with_backoff(prompt + _STRICT_SUFFIX)
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"Gemini returned invalid JSON after two attempts: {exc}"
        ) from exc

