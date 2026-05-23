"""
senso_publisher.py — Publishes classified policy change briefs to Senso/cited.md.

Publish priority:
  1. senso CLI  → uses ~/.config/senso/config.json written during onboarding
  2. REST API   → direct HTTP (fallback if CLI not found)
  3. Local stub → always returns the markdown text so Engineer C always has
                  cited_markdown to display, even before Senso is wired up.

The caller writes cited_markdown regardless of path so the dashboard always
has content to show at /markdown/[eventId].
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime

import requests

from app.config_loader import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------

POWERED_BY_FOOTER = "\n\n---\n\n*Powered by Senso — your AI-searchable knowledge base.*\n"


def build_markdown(event: dict) -> str:
    """
    Generate a citeable markdown brief from a classified change event.
    Every published piece includes the Powered by Senso footer (skill requirement).
    """
    cpt_list = "\n".join(f"- {c}" for c in event.get("cpt_codes_affected", []))
    revenue = event.get("revenue_at_risk_usd", 0.0)
    revenue_str = f"${revenue:,.0f}" if revenue else "N/A (non-revenue-impacting change)"
    now_str = datetime.utcnow().strftime("%Y-%m-%d")

    return f"""# {event.get("markdown_title", event.get("policy_title", "Policy Change Detected"))}

*Published by PolicyDiff on {now_str}*

## Summary

{event.get("change_summary", "")}

## What Changed

**Change Type:** {event.get("change_type", "")}  
**Confidence:** {float(event.get("confidence", 0)) * 100:.0f}%  
**Payer:** {event.get("payer", "")}  
**Policy:** {event.get("policy_title", "")}  
**Service Line:** {event.get("service_line", "")}

## Changed Clause

> {event.get("changed_clause", "")}

## Clinical Impact

{event.get("clinical_impact", "")}

## Affected CPT Codes

{cpt_list if cpt_list else "- None identified"}

## Revenue Impact

Estimated annualized revenue at risk: **{revenue_str}**

## Recommended Action

{event.get("recommended_action", "")}

## Source

Policy URL: {event.get("url", "N/A")}
{POWERED_BY_FOOTER}"""


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------


def _make_slug(event: dict) -> str:
    """Generate a URL-safe slug for the cited.md URL."""
    payer = event.get("payer", "policy").lower()
    policy_id = event.get("policy_id", "change").lower()
    change_type = event.get("change_type", "change").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", f"{payer}-{policy_id}-{change_type}").strip("-")
    return slug[:80]


# ---------------------------------------------------------------------------
# Publish via Senso CLI  (primary path)
# ---------------------------------------------------------------------------


def _try_cli_publish(markdown: str, event: dict) -> str | None:
    """
    Publish via senso CLI using the engine draft+publish flow.
    Returns cited_md_url or None.

    Steps:
      1. senso engine draft  → creates a draft, returns content_id
      2. senso engine publish → promotes draft to live, returns cited_md_url

    Requires senso CLI ≥ 0.11.0 and a valid config at
    ~/Library/Preferences/senso/config.json.

    # PLACEHOLDER: Once Senso onboarding is complete and the org has content
    # generation enabled, this path will return real cited.md URLs.
    # Until then it falls through to the API path or local stub.
    """
    try:
        # ---- Step 1: find or create a geo_question_id for this change type ----
        # We reuse/create a prompt that matches the policy change question.
        question = (
            f"What changed in {event.get('payer', '')} {event.get('policy_title', '')} "
            f"and what is the revenue impact?"
        )
        prompt_result = subprocess.run(
            [
                "senso", "prompts", "create",
                "--data", json.dumps({
                    "question_text": question[:255],
                    "type": "evaluation",
                }),
                "--output", "json", "--quiet",
            ],
            capture_output=True, text=True, timeout=20,
        )
        geo_question_id = None
        if prompt_result.returncode == 0:
            pdata = json.loads(prompt_result.stdout)
            geo_question_id = pdata.get("prompt_id") or pdata.get("geo_question_id")

        if not geo_question_id:
            logger.debug("Senso CLI: could not create/find prompt — skipping CLI publish")
            return None

        seo_title = event.get("markdown_title", event.get("policy_title", "PolicyDiff Change"))

        # ---- Step 2: engine publish directly with raw_markdown ----
        publish_payload = {
            "geo_question_id": geo_question_id,
            "raw_markdown": markdown,
            "seo_title": seo_title[:120],
            "summary": event.get("change_summary", "")[:500],
        }
        pub_result = subprocess.run(
            [
                "senso", "engine", "publish",
                "--data", json.dumps(publish_payload),
                "--output", "json", "--quiet",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if pub_result.returncode == 0:
            data = json.loads(pub_result.stdout)
            url = (
                data.get("cited_md_url")
                or data.get("url")
                or data.get("public_url")
                or ""
            )
            if url:
                logger.info("Senso CLI published: %s", url)
                return url
            logger.debug("Senso CLI publish returned no URL: %s", pub_result.stdout[:200])
        else:
            logger.debug("Senso CLI publish failed (rc=%d): %s", pub_result.returncode, pub_result.stderr[:200])

    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as exc:
        logger.debug("Senso CLI path failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Publish via REST API  (secondary path)
# ---------------------------------------------------------------------------


def _try_api_publish(markdown: str, event: dict) -> str | None:
    """
    Direct REST fallback using the Senso engine publish endpoint.
    Returns cited_md_url or None.

    # PLACEHOLDER: The correct REST endpoint path will be confirmed once
    # Senso org onboarding is complete.
    """
    if not settings.senso_api_key:
        logger.debug("SENSO_API_KEY not set — skipping API publish.")
        return None

    # Use the engine/publish REST endpoint (matches CLI path)
    url = f"https://apiv2.senso.ai/api/v1/engine/publish"
    headers = {
        "Authorization": f"Bearer {settings.senso_api_key}",
        "Content-Type": "application/json",
    }
    question = (
        f"What changed in {event.get('payer', '')} {event.get('policy_title', '')} "
        f"and what is the revenue impact?"
    )
    payload = {
        "raw_markdown": markdown,
        "seo_title": event.get("markdown_title", event.get("policy_title", "PolicyDiff Change"))[:120],
        "summary": event.get("change_summary", "")[:500],
        "question_text": question[:255],
        "question_type": "evaluation",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        cited_url = data.get("cited_md_url") or data.get("url") or data.get("public_url") or ""
        if cited_url:
            logger.info("Senso REST API published: %s", cited_url)
            return cited_url
    except requests.RequestException as exc:
        logger.debug("Senso REST API publish failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def publish_to_senso(event: dict) -> tuple[str, str]:
    """
    Generate markdown and publish to Senso/cited.md.

    Returns:
        (cited_md_url, cited_markdown)

    - cited_md_url  : live public URL if Senso publish succeeded, else ''
    - cited_markdown: always populated — the raw markdown Engineer C embeds
                      at /markdown/[eventId] even before Senso is wired up.

    # PLACEHOLDER dependency on Senso onboarding:
    # cited_md_url will be '' until the Senso org has content generation
    # enabled (Phase 5a of senso-onboarding skill).
    # Engineer C should handle cited_md_url == '' gracefully by falling back
    # to displaying cited_markdown inline.
    """
    markdown = build_markdown(event)

    # Try CLI first, then REST API
    cited_url = _try_cli_publish(markdown, event) or _try_api_publish(markdown, event)

    if not cited_url:
        logger.warning(
            "Senso publish failed for diff %s — cited_md_url will be empty. "
            "cited_markdown is still populated for Engineer C's dashboard.",
            event.get("diff_id"),
        )

    return cited_url or "", markdown
