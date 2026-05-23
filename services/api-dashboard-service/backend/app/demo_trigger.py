"""
demo_trigger.py — Demo fallback trigger for api-dashboard-service.

Calls Engineer A's ingestion endpoint (or inserts seed data directly into
ClickHouse) to ensure the demo always has a visible TIGHTENING event even
when live scraping is slow.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

INGESTION_SERVICE_URL = os.getenv(
    "INGESTION_SERVICE_URL", "http://ingestion-service:8001"
)
CLASSIFIER_SERVICE_URL = os.getenv(
    "CLASSIFIER_SERVICE_URL", "http://classifier-service:8002"
)

# Hardcoded demo event that is inserted directly into ClickHouse as a fallback
DEMO_CHANGE_EVENT = {
    "event_id": str(uuid.uuid4()),
    "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    "diff_id": str(uuid.uuid4()),
    "payer": "UHC",
    "policy_id": "cardiac-mri",
    "policy_title": "Cardiac MRI Coverage Policy",
    "url": "https://www.uhcprovider.com/en/policies-protocols/b-d/cardiac-mri.html",
    "service_line": "Cardiology",
    "change_type": "TIGHTENING",
    "confidence": 0.92,
    "changed_clause": "Member must have completed a cardiac stress test within the past 6 months.",
    "change_summary": "UHC added a stress test prerequisite before cardiac MRI approval.",
    "clinical_impact": "Cardiology prior-auth staff must attach stress test documentation.",
    "cpt_codes_affected": ["75561"],
    "revenue_at_risk_usd": 261000.0,
    "recommended_action": "Update cardiology prior authorization checklist.",
    "cited_md_url": "https://cited.md/policydiff/uhc-cardiac-mri-tightening",
    "cited_markdown": """# UHC Cardiac MRI Policy Tightened — New Stress Test Requirement Added

## Summary
UnitedHealthcare updated its Cardiac MRI Coverage Policy to require proof of a completed cardiac stress test within the past 6 months before authorization will be granted.

## What Changed
A new prerequisite has been added: members must have documentation of a completed cardiac stress test within 6 months prior to the cardiac MRI request.

## Changed Clause
> Member must have completed a cardiac stress test within the past 6 months.

## Affected Codes
- 75561 — Cardiac MRI, morphology and function, without contrast material(s)

## Revenue Impact
Estimated annualized revenue at risk: $261,000

## Recommended Action
Update the cardiology prior authorization checklist to include recent stress test documentation as a required attachment.

## Source
Policy URL: https://www.uhcprovider.com/en/policies-protocols/b-d/cardiac-mri.html
""",
    "datadog_trace_id": "demo-trace-0001",
    "status": "PUBLISHED",
}


async def trigger_via_pipeline() -> Dict[str, Any]:
    """
    Attempt to trigger demo by calling Engineer A + B services.
    Falls back to direct ClickHouse insert if services are unreachable.
    """
    # Step 1: call Engineer A to ingest UHC cardiac-mri
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{INGESTION_SERVICE_URL}/ingest/policy/UHC/cardiac-mri"
            )
            logger.info("Engineer A responded: %s", resp.status_code)
    except Exception as exc:
        logger.warning("Engineer A unreachable: %s — will fall back to seed insert", exc)
        return await _seed_demo_event_directly()

    # Step 2: call Engineer B to classify
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{CLASSIFIER_SERVICE_URL}/classify/run-once"
            )
            logger.info("Engineer B responded: %s", resp.status_code)
    except Exception as exc:
        logger.warning("Engineer B unreachable: %s — using existing events", exc)

    return {
        "status": "DEMO_TRIGGERED",
        "message": "Demo diff submitted via ingestion + classifier pipeline. Refresh dashboard in 10 seconds.",
    }


async def _seed_demo_event_directly() -> Dict[str, Any]:
    """Insert a hardcoded demo change_event row directly into ClickHouse."""
    import clickhouse_connect  # imported lazily to avoid hard dep at module load

    try:
        client = clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            database=os.getenv("CLICKHOUSE_DB", "policydiff"),
        )

        ev = DEMO_CHANGE_EVENT.copy()
        ev["event_id"] = str(uuid.uuid4())  # fresh UUID each trigger
        ev["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        client.command(f"""
            INSERT INTO policydiff.change_events (
                event_id, created_at, diff_id, payer, policy_id, policy_title,
                url, service_line, change_type, confidence, changed_clause,
                change_summary, clinical_impact, cpt_codes_affected,
                revenue_at_risk_usd, recommended_action, cited_md_url,
                cited_markdown, datadog_trace_id, status
            ) VALUES (
                '{ev["event_id"]}',
                '{ev["created_at"]}',
                '{ev["diff_id"]}',
                '{ev["payer"]}',
                '{ev["policy_id"]}',
                '{ev["policy_title"]}',
                '{ev["url"]}',
                '{ev["service_line"]}',
                '{ev["change_type"]}',
                {ev["confidence"]},
                $${ev["changed_clause"]}$$,
                $${ev["change_summary"]}$$,
                $${ev["clinical_impact"]}$$,
                ['75561'],
                {ev["revenue_at_risk_usd"]},
                $${ev["recommended_action"]}$$,
                '{ev["cited_md_url"]}',
                $${ev["cited_markdown"]}$$,
                '{ev["datadog_trace_id"]}',
                '{ev["status"]}'
            )
        """)
        logger.info("Demo event seeded directly into ClickHouse: %s", ev["event_id"])
        return {
            "status": "DEMO_TRIGGERED",
            "message": "Demo event seeded directly. Refresh dashboard in 5 seconds.",
        }
    except Exception as exc:
        logger.error("Direct seed also failed: %s", exc)
        return {
            "status": "DEMO_FAILED",
            "message": f"Could not trigger demo: {exc}. Ensure ClickHouse is running.",
        }
