"""
cms_rates.py — Fetches real CPT reimbursement data from CMS Medicare open data.

Source: CMS Medicare Physician & Other Practitioners - by Geography and Service
https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners

Uses National-level rows to get a single aggregated payment and service volume
per CPT code (two rows per code: facility + non-facility — weighted average taken).

CPT codes are read from policy_cpt_map.yaml so coverage stays in sync with
the watchlist automatically — no hardcoding here.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests
import yaml

logger = logging.getLogger(__name__)

# CMS Medicare Physician & Other Practitioners – by Geography and Service
# Discovered via https://data.cms.gov/data.json
_CMS_DATASET_URL = (
    "https://data.cms.gov/data-api/v1/dataset/"
    "6fea9d79-0129-4e4c-b1b8-23cd86a4f435/data"
)
_CMS_TIMEOUT = 15


def _extract_cpt_meta(policy_cpt_map_path: str) -> dict[str, dict]:
    """
    Return {cpt_code: {service_line, payer}} from policy_cpt_map.yaml.
    First payer/service_line seen wins for codes shared across policies.
    """
    path = Path(policy_cpt_map_path)
    if not path.exists():
        logger.warning("policy_cpt_map.yaml not found at %s", path)
        return {}

    raw = yaml.safe_load(path.read_text()) or {}
    cpt_meta: dict[str, dict] = {}
    for policy_key, policy_data in raw.get("policies", {}).items():
        payer = policy_key.split(":")[0]
        service_line = policy_data.get("service_line", "General")
        for cpt in policy_data.get("cpt_codes", []):
            cpt_str = str(cpt)
            if cpt_str not in cpt_meta:
                cpt_meta[cpt_str] = {"service_line": service_line, "payer": payer}
    return cpt_meta


def _fetch_national_rate(cpt: str) -> tuple[float, int] | None:
    """
    Fetch national average Medicare payment and annual service volume for one CPT code.

    The dataset has two national rows per code (facility / non-facility).
    We compute a service-volume-weighted average payment and sum the volumes.

    Returns (avg_reimbursement_usd, claim_count_90d) or None on failure.
    """
    try:
        resp = requests.get(
            _CMS_DATASET_URL,
            params={
                "filter[HCPCS_Cd]": cpt,
                "filter[Rndrng_Prvdr_Geo_Desc]": "National",
                "size": 10,
            },
            timeout=_CMS_TIMEOUT,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None

        total_services = 0
        weighted_payment = 0.0
        for row in rows:
            try:
                srvcs = int(row.get("Tot_Srvcs") or 0)
                payment = float(row.get("Avg_Mdcr_Pymt_Amt") or 0)
                weighted_payment += payment * srvcs
                total_services += srvcs
            except (TypeError, ValueError):
                continue

        if total_services == 0:
            return None

        avg_reimbursement = round(weighted_payment / total_services, 2)
        claim_count_90d = max(1, total_services // 4)
        return avg_reimbursement, claim_count_90d

    except Exception as exc:
        logger.warning("CMS API request failed for CPT %s: %s", cpt, exc)
        return None


def build_claims_ref_rows(policy_cpt_map_path: str) -> list[tuple]:
    """
    Build rows for claims_ref by:
      1. Reading all CPT codes from policy_cpt_map.yaml
      2. Fetching real national Medicare payment data from CMS for each code

    Returns list of (cpt, service_line, avg_reimbursement_usd, claim_count_90d, payer).
    Codes with no CMS data are skipped and logged as warnings.
    """
    cpt_meta = _extract_cpt_meta(policy_cpt_map_path)
    if not cpt_meta:
        logger.error("No CPT codes found in policy_cpt_map.yaml — claims_ref will be empty.")
        return []

    logger.info("Fetching CMS Medicare national rates for %d CPT codes...", len(cpt_meta))
    rows = []
    missing = []

    for cpt, meta in cpt_meta.items():
        result = _fetch_national_rate(cpt)
        if result is None:
            missing.append(cpt)
            logger.warning("No CMS national data for CPT %s (%s) — skipping.", cpt, meta["service_line"])
            continue
        avg_reimbursement, claim_count_90d = result
        rows.append((cpt, meta["service_line"], avg_reimbursement, claim_count_90d, meta["payer"]))
        logger.info(
            "CPT %s (%s): $%.2f avg Medicare payment, %d claims/90d",
            cpt, meta["service_line"], avg_reimbursement, claim_count_90d,
        )

    if missing:
        logger.warning(
            "CMS returned no national data for %d code(s): %s",
            len(missing), missing,
        )

    logger.info("Built %d claims_ref rows from CMS data.", len(rows))
    return rows
