"""
luminai_optional.py — Optional Luminai webhook routing module.

Routes a policy change alert to the appropriate service-line workflow queue.
If ENABLE_LUMINAI=false (default), the endpoint returns a graceful disabled
message without breaking the rest of the application.

For demo: uses httpbin.org/post if no real Luminai webhook is configured.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)

ENABLE_LUMINAI = os.getenv("ENABLE_LUMINAI", "false").lower() == "true"
LUMINAI_WEBHOOK_URL = os.getenv("LUMINAI_WEBHOOK_URL", "https://httpbin.org/post")

# Routing table from README Section 9
SERVICE_LINE_ROUTES: Dict[str, str] = {
    "Cardiology":   "Cardiology prior authorization team",
    "Radiology":    "Imaging authorization / radiology billing team",
    "Orthopedics":  "Orthopedics prior authorization team",
    "Neurology":    "Neurology service-line admin",
    "Oncology":     "Oncology authorization / revenue-cycle team",
}
DEFAULT_ROUTE = "General revenue cycle management team"


def is_enabled() -> bool:
    return ENABLE_LUMINAI


def resolve_route(service_line: str) -> str:
    return SERVICE_LINE_ROUTES.get(service_line, DEFAULT_ROUTE)


async def send_alert(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sends a workflow alert payload to the configured Luminai webhook.

    Returns a dict with status and the webhook response summary.
    """
    service_line = event.get("service_line", "Unknown")
    route = resolve_route(service_line)

    payload = {
        "workflow_type": "policy_change_alert",
        "priority": "HIGH",
        "route_to": route,
        "payer": event.get("payer", ""),
        "policy_id": event.get("policy_id", ""),
        "summary": event.get("change_summary", ""),
        "revenue_at_risk_usd": event.get("revenue_at_risk_usd", 0),
        "cited_md_url": event.get("cited_md_url", ""),
        "action_required": event.get("recommended_action", "Review policy change and update workflows."),
    }

    logger.info("Sending Luminai alert to %s for route '%s'", LUMINAI_WEBHOOK_URL, route)

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(LUMINAI_WEBHOOK_URL, json=payload)
        resp.raise_for_status()
        logger.info("Luminai webhook responded %s", resp.status_code)

    return {
        "status": "ROUTED",
        "message": f"Alert routed to '{route}' via Luminai webhook.",
        "routed_to": route,
        "webhook_url": LUMINAI_WEBHOOK_URL,
    }
