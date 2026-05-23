"""
main.py — FastAPI entrypoint for api-dashboard-service.

Runs on port 8003. Implements all API contracts from Engineer C README Section 6.
CORS is open for the Next.js frontend on port 3000.
"""

from __future__ import annotations

import io
import logging
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app import clickhouse_repo, demo_trigger, x402_optional, luminai_optional
from app.evidence_export import generate_evidence_pdf
from app.schemas import (
    ChangeEventDetail,
    ChangeEventSummary,
    DemoTriggerResponse,
    RiskSummary,
    RouteAlertResponse,
    SystemStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PolicyDiff API Dashboard Service",
    description="Read layer + dashboard API for payer policy change intelligence.",
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# CORS — allow Next.js frontend
# ---------------------------------------------------------------------------
_extra_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://frontend:3000",
        *_extra_origins,
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health_check():
    return {"service": "api-dashboard-service", "status": "ok"}


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

@app.get("/api/changes", response_model=List[ChangeEventSummary], tags=["changes"])
def get_changes(
    limit: int = Query(50, ge=1, le=500),
    change_type: Optional[str] = Query(None),
    payer: Optional[str] = Query(None),
    service_line: Optional[str] = Query(None),
):
    """
    Returns the latest classified change events, newest first.
    Optionally filtered by change_type, payer, or service_line.
    """
    try:
        rows = clickhouse_repo.fetch_changes(
            limit=limit,
            change_type=change_type,
            payer=payer,
            service_line=service_line,
        )
        return rows
    except Exception as exc:
        logger.exception("Failed to fetch changes")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get(
    "/api/changes/{event_id}",
    response_model=ChangeEventDetail,
    tags=["changes"],
)
def get_change_detail(event_id: str):
    """Returns a single change event with full evidence fields."""
    try:
        row = clickhouse_repo.fetch_change_detail(event_id)
    except Exception as exc:
        logger.exception("Failed to fetch change detail for %s", event_id)
        raise HTTPException(status_code=500, detail=str(exc))

    if row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return row


# ---------------------------------------------------------------------------
# Risk summary
# ---------------------------------------------------------------------------

@app.get("/api/risk-summary", response_model=RiskSummary, tags=["risk"])
def get_risk_summary():
    """Aggregated revenue-at-risk metrics for the dashboard summary cards."""
    try:
        return clickhouse_repo.fetch_risk_summary()
    except Exception as exc:
        logger.exception("Failed to fetch risk summary")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

@app.get("/api/system-status", response_model=SystemStatus, tags=["system"])
def get_system_status():
    """Pipeline health metrics shown in the dashboard header."""
    try:
        return clickhouse_repo.fetch_system_status()
    except Exception as exc:
        logger.exception("Failed to fetch system status")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Demo trigger
# ---------------------------------------------------------------------------

@app.post("/api/demo/trigger", response_model=DemoTriggerResponse, tags=["demo"])
async def trigger_demo():
    """
    Demo fallback endpoint. Creates a sample TIGHTENING event if the live
    pipeline is slow. Tries Engineer A + B first, then falls back to direct
    ClickHouse seed.
    """
    result = await demo_trigger.trigger_via_pipeline()
    return result


# ---------------------------------------------------------------------------
# Optional x402 PDF export
# ---------------------------------------------------------------------------

@app.get("/api/changes/{event_id}/export-pdf", tags=["export"])
async def export_pdf(
    event_id: str,
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
):
    """
    Optional x402 payment-gated PDF export.

    - If ENABLE_X402=false → returns 200 with a feature-disabled message.
    - If ENABLE_X402=true and no X-Payment header → returns 402-style JSON.
    - If X-Payment header present → generates and returns the PDF.
    """
    if not x402_optional.is_enabled():
        return JSONResponse(
            status_code=200,
            content={
                "status": "DISABLED",
                "message": "x402 PDF export is not enabled in this deployment. Set ENABLE_X402=true to activate.",
            },
        )

    is_paid, verification_note = x402_optional.verify_payment_header(x_payment)

    if not is_paid:
        return JSONResponse(
            status_code=402,
            content=x402_optional.build_payment_required_response(event_id),
        )

    # Fetch event and generate PDF
    try:
        row = clickhouse_repo.fetch_change_detail(event_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    try:
        pdf_bytes = generate_evidence_pdf(row)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="policydiff-{event_id}.pdf"',
            "X-Payment-Verification": verification_note,
        },
    )


# ---------------------------------------------------------------------------
# Optional Luminai alert routing
# ---------------------------------------------------------------------------

@app.post(
    "/api/changes/{event_id}/route-alert",
    response_model=RouteAlertResponse,
    tags=["routing"],
)
async def route_alert(event_id: str):
    """
    Optional Luminai workflow routing.

    - If ENABLE_LUMINAI=false → returns a graceful disabled response.
    - If enabled → posts alert payload to the Luminai webhook URL.
    """
    if not luminai_optional.is_enabled():
        return RouteAlertResponse(
            status="DISABLED",
            message="Luminai routing is not enabled. Set ENABLE_LUMINAI=true to activate.",
            routed_to="N/A",
            webhook_url="N/A",
        )

    try:
        row = clickhouse_repo.fetch_change_detail(event_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    try:
        result = await luminai_optional.send_alert(row)
        return result
    except Exception as exc:
        logger.exception("Luminai routing failed for event %s", event_id)
        raise HTTPException(status_code=502, detail=f"Luminai webhook error: {exc}")
