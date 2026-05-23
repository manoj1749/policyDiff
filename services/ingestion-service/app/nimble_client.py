from __future__ import annotations

import logging
import re
import time
from html import unescape
from typing import Any

import requests

from app.settings import get_settings

logger = logging.getLogger(__name__)


def fetch_policy(url: str, source_type: str) -> dict[str, Any]:
    settings = get_settings()
    extract_timeout = (
        settings.nimble_pdf_extract_timeout_seconds
        if source_type == "pdf"
        else settings.nimble_html_extract_timeout_seconds
    )
    payload = {
        "url": url,
        "render_js": source_type == "html",
        "ai_stealth": True,
        "extract_type": "text",
        "timeout": extract_timeout,
    }
    headers = {
        "Authorization": f"Bearer {settings.nimble_api_key}",
        "Content-Type": "application/json",
    }

    last_error = "Unknown Nimble error"
    for attempt in range(1, settings.nimble_max_retries + 1):
        try:
            response = requests.post(
                settings.nimble_api_url,
                json=payload,
                headers=headers,
                timeout=settings.nimble_request_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            last_error = _format_request_error(exc)
            logger.warning(
                "Nimble fetch failed for %s on attempt %s/%s: %s",
                url,
                attempt,
                settings.nimble_max_retries,
                last_error,
            )
            if attempt < settings.nimble_max_retries and _should_retry(exc):
                time.sleep(settings.nimble_retry_backoff_seconds * attempt)
                continue
            return {
                "raw_extract": "",
                "status": "FAILED",
                "error": last_error,
                "source_type": source_type,
                "attempts": attempt,
            }

        error_reason = _detect_error_response(body)
        if error_reason:
            last_error = error_reason
            logger.warning(
                "Nimble returned an error page for %s on attempt %s/%s: %s",
                url,
                attempt,
                settings.nimble_max_retries,
                last_error,
            )
            return {
                "raw_extract": "",
                "status": "FAILED",
                "error": last_error,
                "source_type": source_type,
                "attempts": attempt,
            }

        raw_extract = _extract_text(body)
        if raw_extract:
            return {
                "raw_extract": raw_extract,
                "status": "SUCCESS",
                "error": "",
                "source_type": source_type,
                "attempts": attempt,
            }

        last_error = "Nimble returned no extractable policy text"
        logger.warning(
            "Nimble returned empty text for %s on attempt %s/%s",
            url,
            attempt,
            settings.nimble_max_retries,
        )
        if attempt < settings.nimble_max_retries:
            time.sleep(settings.nimble_retry_backoff_seconds * attempt)
            continue

    return {
        "raw_extract": "",
        "status": "FAILED",
        "error": last_error,
        "source_type": source_type,
        "attempts": settings.nimble_max_retries,
    }


def _extract_text(payload: dict[str, Any]) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    candidates = (
        payload.get("raw_extract"),
        payload.get("text"),
        data.get("text"),
        data.get("markdown"),
        _html_to_text(data.get("html")) if isinstance(data.get("html"), str) else None,
        payload.get("result", {}).get("text") if isinstance(payload.get("result"), dict) else None,
        payload.get("html_text"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return ""


def _html_to_text(html: str) -> str:
    cleaned = html
    for pattern in (
        r"(?is)<script.*?>.*?</script>",
        r"(?is)<style.*?>.*?</style>",
        r"(?is)<noscript.*?>.*?</noscript>",
    ):
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</(p|div|section|article|li|h1|h2|h3|h4|h5|h6|tr)>", "\n", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _detect_error_response(payload: dict[str, Any]) -> str | None:
    status_code = payload.get("status_code")
    final_url = str(payload.get("url", "") or "")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    html = data.get("html") if isinstance(data.get("html"), str) else ""
    preview = _html_to_text(html)[:1000].lower() if html else ""

    if isinstance(status_code, int) and status_code >= 400:
        return f"Nimble fetched an upstream error page (status_code={status_code})"
    if "error-page" in final_url.lower():
        return f"Nimble was redirected to an error page: {final_url}"
    if "404 not found" in preview or "page not found" in preview:
        return "Nimble fetched a page-not-found response instead of policy content"
    return None


def _should_retry(exc: requests.RequestException) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return False


def _format_request_error(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"{exc.response.status_code} Server Error: {exc.response.reason} for url: {exc.response.url}"
    return str(exc)
