"""
classifier.py — Orchestrates Gemini classification for a single diff candidate.
"""
from __future__ import annotations

import logging

from app.config_loader import settings
from app.gemini_client import call_gemini_with_retry

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {
    "change_type",
    "confidence",
    "changed_clause",
    "summary",
    "clinical_impact",
    "cpt_codes_affected",
    "recommended_action",
    "markdown_title",
}

_VALID_CHANGE_TYPES = {"TIGHTENING", "LOOSENING", "SCOPE_CHANGE", "STYLISTIC"}


def _build_prompt(candidate: dict) -> str:
    """Fill the classification prompt template with candidate fields."""
    template = settings.classification_prompt_template
    if not template:
        raise RuntimeError("Classification prompt template is empty. Check prompts/classification_prompt.md.")

    # Truncate very long texts to keep within Gemini context limits (~30k tokens each)
    old_text = (candidate.get("old_text") or "")[:25000]
    new_text = (candidate.get("new_text") or "")[:25000]

    return (
        template
        .replace("{{payer}}", candidate.get("payer", ""))
        .replace("{{policy_id}}", candidate.get("policy_id", ""))
        .replace("{{policy_title}}", candidate.get("policy_title", ""))
        .replace("{{service_line}}", candidate.get("service_line", ""))
        .replace("{{old_text}}", old_text)
        .replace("{{new_text}}", new_text)
    )


def _validate_and_normalize(result: dict, candidate: dict) -> dict:
    """
    Validate Gemini's output and apply fallbacks:
    - Enforce valid change_type
    - Fill missing CPT codes from policy_cpt_map.yaml
    - Normalize field names
    """
    # Ensure all required keys are present (fill with safe defaults if missing)
    for key in _REQUIRED_KEYS:
        if key not in result:
            result[key] = "" if key != "cpt_codes_affected" else []

    # Enforce valid change_type
    if result["change_type"] not in _VALID_CHANGE_TYPES:
        logger.warning(
            "Gemini returned unknown change_type '%s'; defaulting to STYLISTIC.",
            result["change_type"],
        )
        result["change_type"] = "STYLISTIC"

    # Clamp confidence to [0, 1]
    try:
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    # Ensure cpt_codes_affected is a list of strings
    if not isinstance(result["cpt_codes_affected"], list):
        result["cpt_codes_affected"] = []
    result["cpt_codes_affected"] = [str(c) for c in result["cpt_codes_affected"]]

    # CPT fallback: if Gemini returned no codes, use policy_cpt_map.yaml
    if not result["cpt_codes_affected"]:
        fallback = settings.get_fallback_cpts(
            candidate.get("payer", ""), candidate.get("policy_id", "")
        )
        if fallback:
            logger.info(
                "Gemini returned no CPT codes for %s/%s — using fallback: %s",
                candidate.get("payer"),
                candidate.get("policy_id"),
                fallback,
            )
            result["cpt_codes_affected"] = fallback

    # Rename "summary" → "change_summary" to match change_events schema
    result["change_summary"] = result.pop("summary", result.get("change_summary", ""))

    return result


def classify_diff(candidate: dict) -> dict:
    """
    Main entry point. Takes a diff_candidates row dict and returns a classification dict.

    Raises RuntimeError if Gemini fails after retries.
    """
    prompt = _build_prompt(candidate)
    raw_result = call_gemini_with_retry(prompt)
    result = _validate_and_normalize(raw_result, candidate)

    logger.info(
        "Classified diff %s as %s (confidence=%.2f).",
        candidate.get("diff_id"),
        result["change_type"],
        result["confidence"],
    )
    return result
