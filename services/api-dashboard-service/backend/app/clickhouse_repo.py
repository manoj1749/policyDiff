"""
clickhouse_repo.py — ClickHouse read layer for api-dashboard-service.

Connects to ClickHouse via clickhouse-connect and exposes query helpers
that map directly to the SQL contracts in the Engineer C README (Section 10).
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import clickhouse_connect

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_client() -> clickhouse_connect.driver.Client:
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "policydiff"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(columns: List[str], row: tuple) -> Dict[str, Any]:
    return dict(zip(columns, row))


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val)


def _safe_list(val: Any) -> List[str]:
    if isinstance(val, list):
        return [str(v) for v in val]
    return []


def _fmt_dt(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


# ---------------------------------------------------------------------------
# Recent change events
# ---------------------------------------------------------------------------

def fetch_changes(
    limit: int = 50,
    change_type: Optional[str] = None,
    payer: Optional[str] = None,
    service_line: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return recent change events, optionally filtered."""
    client = get_client()

    conditions = []
    params: Dict[str, Any] = {"limit": limit}

    if change_type:
        conditions.append("change_type = {change_type:String}")
        params["change_type"] = change_type
    if payer:
        conditions.append("payer = {payer:String}")
        params["payer"] = payer
    if service_line:
        conditions.append("service_line = {service_line:String}")
        params["service_line"] = service_line

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            toString(event_id)   AS event_id,
            created_at,
            payer,
            policy_id,
            policy_title,
            service_line,
            change_type,
            confidence,
            change_summary,
            clinical_impact,
            cpt_codes_affected,
            revenue_at_risk_usd,
            cited_md_url,
            status
        FROM policydiff.change_events
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {{limit:UInt32}}
    """

    result = client.query(query, parameters=params)
    rows = []
    for row in result.result_rows:
        r = _row_to_dict(result.column_names, row)
        rows.append({
            "event_id": _safe_str(r.get("event_id")),
            "created_at": _fmt_dt(r.get("created_at")),
            "payer": _safe_str(r.get("payer")),
            "policy_id": _safe_str(r.get("policy_id")),
            "policy_title": _safe_str(r.get("policy_title")),
            "service_line": _safe_str(r.get("service_line")),
            "change_type": _safe_str(r.get("change_type")),
            "confidence": float(r.get("confidence") or 0.0),
            "change_summary": _safe_str(r.get("change_summary")),
            "clinical_impact": _safe_str(r.get("clinical_impact")),
            "cpt_codes_affected": _safe_list(r.get("cpt_codes_affected")),
            "revenue_at_risk_usd": float(r.get("revenue_at_risk_usd") or 0.0),
            "cited_md_url": _safe_str(r.get("cited_md_url")),
            "status": _safe_str(r.get("status")),
        })
    return rows


# ---------------------------------------------------------------------------
# Single change event detail
# ---------------------------------------------------------------------------

def fetch_change_detail(event_id: str) -> Optional[Dict[str, Any]]:
    client = get_client()
    query = """
        SELECT
            toString(event_id)   AS event_id,
            payer,
            policy_id,
            policy_title,
            url,
            service_line,
            change_type,
            confidence,
            changed_clause,
            change_summary,
            clinical_impact,
            cpt_codes_affected,
            revenue_at_risk_usd,
            recommended_action,
            cited_md_url,
            cited_markdown
        FROM policydiff.change_events
        WHERE toString(event_id) = {event_id:String}
        LIMIT 1
    """
    result = client.query(query, parameters={"event_id": event_id})
    if not result.result_rows:
        return None
    row = result.result_rows[0]
    r = _row_to_dict(result.column_names, row)
    return {
        "event_id": _safe_str(r.get("event_id")),
        "payer": _safe_str(r.get("payer")),
        "policy_id": _safe_str(r.get("policy_id")),
        "policy_title": _safe_str(r.get("policy_title")),
        "url": _safe_str(r.get("url")),
        "service_line": _safe_str(r.get("service_line")),
        "change_type": _safe_str(r.get("change_type")),
        "confidence": float(r.get("confidence") or 0.0),
        "changed_clause": _safe_str(r.get("changed_clause")),
        "change_summary": _safe_str(r.get("change_summary")),    # required by ChangeEventDetail
        "clinical_impact": _safe_str(r.get("clinical_impact")),  # required by ChangeEventDetail
        "cpt_codes_affected": _safe_list(r.get("cpt_codes_affected")),
        "revenue_at_risk_usd": float(r.get("revenue_at_risk_usd") or 0.0),
        "recommended_action": _safe_str(r.get("recommended_action")),
        "cited_md_url": _safe_str(r.get("cited_md_url")),
        "cited_markdown": _safe_str(r.get("cited_markdown")),
    }


# ---------------------------------------------------------------------------
# Risk summary
# ---------------------------------------------------------------------------

def fetch_risk_summary() -> Dict[str, Any]:
    client = get_client()

    # Total
    total_result = client.query(
        "SELECT sum(revenue_at_risk_usd) FROM policydiff.change_events"
    )
    total = float((total_result.result_rows[0][0] or 0) if total_result.result_rows else 0)

    # By change type
    ct_result = client.query("""
        SELECT change_type, count() AS cnt, sum(revenue_at_risk_usd) AS rev
        FROM policydiff.change_events
        GROUP BY change_type
        ORDER BY rev DESC
    """)
    by_change_type = [
        {
            "change_type": row[0],
            "count": int(row[1]),
            "revenue_at_risk_usd": float(row[2] or 0),
        }
        for row in ct_result.result_rows
    ]

    # By service line
    sl_result = client.query("""
        SELECT service_line, count() AS cnt, sum(revenue_at_risk_usd) AS rev
        FROM policydiff.change_events
        GROUP BY service_line
        ORDER BY rev DESC
    """)
    by_service_line = [
        {
            "service_line": row[0],
            "count": int(row[1]),
            "revenue_at_risk_usd": float(row[2] or 0),
        }
        for row in sl_result.result_rows
    ]

    # By payer
    payer_result = client.query("""
        SELECT payer, count() AS cnt, sum(revenue_at_risk_usd) AS rev
        FROM policydiff.change_events
        GROUP BY payer
        ORDER BY rev DESC
    """)
    by_payer = [
        {
            "payer": row[0],
            "count": int(row[1]),
            "revenue_at_risk_usd": float(row[2] or 0),
        }
        for row in payer_result.result_rows
    ]

    return {
        "total_revenue_at_risk_usd": total,
        "by_change_type": by_change_type,
        "by_service_line": by_service_line,
        "by_payer": by_payer,
    }


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

def fetch_system_status() -> Dict[str, Any]:
    client = get_client()

    # Pending diffs
    pending_result = client.query(
        "SELECT count() FROM policydiff.diff_candidates WHERE status = 'PENDING'"
    )
    pending_diffs = int(pending_result.result_rows[0][0] or 0) if pending_result.result_rows else 0

    # Processed diffs today
    processed_result = client.query(
        "SELECT count() FROM policydiff.diff_candidates WHERE status = 'PROCESSED' AND toDate(processed_at) = today()"
    )
    processed_today = int(processed_result.result_rows[0][0] or 0) if processed_result.result_rows else 0

    # Latest ingestion run
    ingest_result = client.query(
        "SELECT max(started_at) FROM policydiff.ingestion_runs"
    )
    latest_ingestion = _fmt_dt(ingest_result.result_rows[0][0] if ingest_result.result_rows else None)

    # Latest change event
    event_result = client.query(
        "SELECT max(created_at) FROM policydiff.change_events"
    )
    latest_event = _fmt_dt(event_result.result_rows[0][0] if event_result.result_rows else None)

    # Senso published count
    senso_result = client.query(
        "SELECT count() FROM policydiff.change_events WHERE cited_md_url != ''"
    )
    senso_count = int(senso_result.result_rows[0][0] or 0) if senso_result.result_rows else 0

    return {
        "pending_diffs": pending_diffs,
        "processed_diffs_today": processed_today,
        "latest_ingestion_run": latest_ingestion or "N/A",
        "latest_change_event": latest_event or "N/A",
        "senso_published_count": senso_count,
        "datadog_enabled": bool(os.getenv("DD_API_KEY")),
    }
