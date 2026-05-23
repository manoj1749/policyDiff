"""
schemas.py — Pydantic models for api-dashboard-service.

All response shapes match the contracts defined in the Engineer C README.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Change event list item (GET /api/changes)
# ---------------------------------------------------------------------------

class ChangeEventSummary(BaseModel):
    event_id: str
    created_at: str
    payer: str
    policy_id: str
    policy_title: str
    service_line: str
    change_type: str
    confidence: float
    change_summary: str
    clinical_impact: str
    cpt_codes_affected: List[str]
    revenue_at_risk_usd: float
    cited_md_url: str
    status: str


# ---------------------------------------------------------------------------
# Change event detail (GET /api/changes/{event_id})
# ---------------------------------------------------------------------------

class ChangeEventDetail(BaseModel):
    event_id: str
    payer: str
    policy_id: str
    policy_title: str
    url: str
    service_line: str
    change_type: str
    confidence: float
    changed_clause: str
    change_summary: str
    clinical_impact: str
    cpt_codes_affected: List[str]
    revenue_at_risk_usd: float
    recommended_action: str
    cited_md_url: str
    cited_markdown: str


# ---------------------------------------------------------------------------
# Risk summary (GET /api/risk-summary)
# ---------------------------------------------------------------------------

class ChangeTypeSummary(BaseModel):
    change_type: str
    count: int
    revenue_at_risk_usd: float


class ServiceLineSummary(BaseModel):
    service_line: str
    count: int
    revenue_at_risk_usd: float


class PayerSummary(BaseModel):
    payer: str
    count: int
    revenue_at_risk_usd: float


class RiskSummary(BaseModel):
    total_revenue_at_risk_usd: float
    by_change_type: List[ChangeTypeSummary]
    by_service_line: List[ServiceLineSummary]
    by_payer: List[PayerSummary]


# ---------------------------------------------------------------------------
# System status (GET /api/system-status)
# ---------------------------------------------------------------------------

class SystemStatus(BaseModel):
    pending_diffs: int
    processed_diffs_today: int
    latest_ingestion_run: str
    latest_change_event: str
    senso_published_count: int
    datadog_enabled: bool


# ---------------------------------------------------------------------------
# Demo trigger (POST /api/demo/trigger)
# ---------------------------------------------------------------------------

class DemoTriggerResponse(BaseModel):
    status: str
    message: str


# ---------------------------------------------------------------------------
# x402 optional export
# ---------------------------------------------------------------------------

class X402Details(BaseModel):
    scheme: str = "exact"
    network: str = "base-sepolia"
    maxAmountRequired: str
    asset: str
    payTo: str
    description: str


class X402PaymentRequired(BaseModel):
    error: str
    x402: X402Details


class ExportPDFResponse(BaseModel):
    status: str
    download_url: str


# ---------------------------------------------------------------------------
# Luminai optional routing
# ---------------------------------------------------------------------------

class RouteAlertResponse(BaseModel):
    status: str
    message: str
    routed_to: str
    webhook_url: str
