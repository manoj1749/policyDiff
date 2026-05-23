"""
revenue_impact.py — Computes annualized revenue at risk from claims_ref data.
"""
from __future__ import annotations

import logging

from app.clickhouse_repo import query_revenue_at_risk

logger = logging.getLogger(__name__)

# Only these change types represent revenue risk.
_RISK_CHANGE_TYPES = {"TIGHTENING", "SCOPE_CHANGE"}


def compute_revenue_at_risk(cpt_codes: list[str], change_type: str) -> float:
    """
    Annualized revenue at risk formula:
        sum(avg_reimbursement_usd * claim_count_90d * 4)

    Returns 0 for LOOSENING and STYLISTIC.
    """
    if change_type not in _RISK_CHANGE_TYPES:
        logger.debug(
            "change_type=%s — no revenue risk computed (returning 0).", change_type
        )
        return 0.0

    if not cpt_codes:
        logger.debug("No CPT codes provided — revenue at risk = 0.")
        return 0.0

    revenue = query_revenue_at_risk(cpt_codes)
    logger.info(
        "Revenue at risk for CPTs %s (change_type=%s): $%.2f",
        cpt_codes,
        change_type,
        revenue,
    )
    return revenue
