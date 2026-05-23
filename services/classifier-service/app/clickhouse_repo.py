"""
clickhouse_repo.py — All ClickHouse read/write operations for classifier-service.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import clickhouse_connect

from app.config_loader import settings

logger = logging.getLogger(__name__)


def _client():
    """Create a new ClickHouse client for each call (thread-safe, low overhead)."""
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
    )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get_pending_candidates(limit: int | None = None) -> list[dict]:
    """Fetch diff_candidates with status = 'PENDING', oldest first."""
    batch = limit if limit is not None else settings.batch_size
    query = f"""
        SELECT
            toString(diff_id)  AS diff_id,
            toString(created_at) AS created_at,
            payer,
            policy_id,
            policy_title,
            url,
            source_type,
            service_line,
            old_text,
            new_text,
            default_cpt_codes,
            status
        FROM policydiff.diff_candidates
        WHERE status = 'PENDING'
        ORDER BY created_at ASC
        LIMIT {int(batch)}
    """
    client = _client()
    result = client.query(query)
    rows = []
    for row in result.named_results():
        rows.append(dict(row))
    return rows


def get_candidate_by_id(diff_id: str) -> dict | None:
    """Fetch a single diff_candidate by UUID."""
    query = """
        SELECT
            toString(diff_id)    AS diff_id,
            toString(created_at) AS created_at,
            payer,
            policy_id,
            policy_title,
            url,
            source_type,
            service_line,
            old_text,
            new_text,
            default_cpt_codes,
            status
        FROM policydiff.diff_candidates
        WHERE diff_id = {diff_id:String}
        LIMIT 1
    """
    client = _client()
    result = client.query(query, parameters={"diff_id": diff_id})
    rows = list(result.named_results())
    return dict(rows[0]) if rows else None


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------


def query_revenue_at_risk(cpt_codes: list[str]) -> float:
    """Sum annualized revenue at risk for given CPT codes from claims_ref."""
    if not cpt_codes:
        return 0.0
    codes_csv = ", ".join(f"'{c}'" for c in cpt_codes)
    query = f"""
        SELECT sum(avg_reimbursement_usd * claim_count_90d * 4) AS revenue
        FROM policydiff.claims_ref
        WHERE cpt IN ({codes_csv})
    """
    client = _client()
    result = client.query(query)
    rows = list(result.named_results())
    if rows and rows[0].get("revenue") is not None:
        return float(rows[0]["revenue"])
    return 0.0


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def insert_change_event(event: dict[str, Any]) -> str:
    """Insert a classified event into change_events. Returns the event_id."""
    event_id = str(uuid.uuid4())
    client = _client()
    client.insert(
        "policydiff.change_events",
        [
            [
                event_id,
                event.get("diff_id", ""),
                event.get("payer", ""),
                event.get("policy_id", ""),
                event.get("policy_title", ""),
                event.get("url", ""),
                event.get("service_line", ""),
                event.get("change_type", ""),
                float(event.get("confidence", 0.0)),
                event.get("changed_clause", ""),
                event.get("change_summary", ""),
                event.get("clinical_impact", ""),
                event.get("cpt_codes_affected", []),
                float(event.get("revenue_at_risk_usd", 0.0)),
                event.get("cited_md_url", ""),
                event.get("cited_markdown", ""),
                event.get("datadog_trace_id", ""),
                event.get("status", "PUBLISHED"),
            ]
        ],
        column_names=[
            "event_id",
            "diff_id",
            "payer",
            "policy_id",
            "policy_title",
            "url",
            "service_line",
            "change_type",
            "confidence",
            "changed_clause",
            "change_summary",
            "clinical_impact",
            "cpt_codes_affected",
            "revenue_at_risk_usd",
            "cited_md_url",
            "cited_markdown",
            "datadog_trace_id",
            "status",
        ],
    )
    logger.info("Inserted change_event %s for diff %s.", event_id, event.get("diff_id"))
    return event_id


def mark_processed(diff_id: str) -> None:
    """Update diff_candidates status to PROCESSED."""
    client = _client()
    client.command(
        """
        ALTER TABLE policydiff.diff_candidates
        UPDATE status = 'PROCESSED', processed_at = now(), error_message = ''
        WHERE diff_id = {diff_id:String}
        """,
        parameters={"diff_id": diff_id},
    )
    logger.info("Marked diff %s as PROCESSED.", diff_id)


def mark_error(diff_id: str, error_message: str) -> None:
    """Update diff_candidates status to ERROR."""
    client = _client()
    client.command(
        """
        ALTER TABLE policydiff.diff_candidates
        UPDATE status = 'ERROR', error_message = {error_message:String}
        WHERE diff_id = {diff_id:String}
        """,
        parameters={"diff_id": diff_id, "error_message": error_message[:2000]},
    )
    logger.warning("Marked diff %s as ERROR: %s", diff_id, error_message)


def insert_classification_error(
    diff_id: str,
    payer: str,
    policy_id: str,
    error_stage: str,
    error_message: str,
) -> None:
    """Log a classification failure to classification_errors."""
    client = _client()
    client.insert(
        "policydiff.classification_errors",
        [[diff_id, payer, policy_id, error_stage, error_message[:2000]]],
        column_names=["diff_id", "payer", "policy_id", "error_stage", "error_message"],
    )
