"""
demo_trigger.py — Smart demo trigger (zero-rate-limit simulation).

Strategy:
  1. Query real claims_ref + past change_events from ClickHouse
  2. Pick a payer/service_line/CPT combo not recently seen
  3. Simulate financially realistic revenue impact from claims data
  4. Generate realistic narrative using rich templates (no API needed)
  5. Try Gemini ONLY as an optional narrative enhancer — silently skip on failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

CLASSIFIER_SERVICE_URL = os.getenv("CLASSIFIER_SERVICE_URL", "http://localhost:8002")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ── Policy change scenario library ──────────────────────────────────────────
# Each scenario defines a realistic policy restriction by service line.
# Filled dynamically with real payer / CPT / revenue data from ClickHouse.

SCENARIO_TEMPLATES = [
    {
        "service_line": "Cardiology",
        "change_type": "TIGHTENING",
        "policy_id_tpl": "{payer_slug}-cardiac-prior-auth-{year}",
        "policy_title_tpl": "{payer} Cardiac Imaging Prior Authorization Update",
        "changed_clause_tpl": (
            "{payer} now requires a completed cardiology consultation note "
            "within 60 days before authorizing cardiac imaging procedures."
        ),
        "change_summary_tpl": (
            "{payer} tightened cardiac imaging prior auth by requiring a recent "
            "cardiology consult — affecting CPT {cpts}."
        ),
        "clinical_impact_tpl": (
            "Cardiology scheduling staff must attach the consulting cardiologist's "
            "note to every PA request for CPT {cpts}."
        ),
        "recommended_action_tpl": (
            "Update the cardiology PA checklist to require consult notes dated "
            "within 60 days. Audit pending cardiac imaging orders immediately."
        ),
        "cpt_hints": ["75561", "75563", "75565", "93306"],
    },
    {
        "service_line": "Radiology",
        "change_type": "TIGHTENING",
        "policy_id_tpl": "{payer_slug}-mri-conservative-therapy-{year}",
        "policy_title_tpl": "{payer} MRI Coverage — Conservative Therapy Prerequisite",
        "changed_clause_tpl": (
            "{payer} requires documented evidence of at least 6 weeks of conservative "
            "therapy (PT notes, chiropractic records, or pain management) "
            "prior to approving MRI of the spine or extremities."
        ),
        "change_summary_tpl": (
            "{payer} added a 6-week conservative therapy prerequisite for MRI "
            "authorization — impacting CPT {cpts}."
        ),
        "clinical_impact_tpl": (
            "Radiology schedulers must collect PT or chiropractic notes spanning "
            "≥6 weeks before submitting PA for CPT {cpts}."
        ),
        "recommended_action_tpl": (
            "Create a conservative therapy checklist in your EMR order workflow "
            "for all spine and extremity MRI orders."
        ),
        "cpt_hints": ["72141", "72148", "73221", "73721"],
    },
    {
        "service_line": "Orthopedics",
        "change_type": "TIGHTENING",
        "policy_id_tpl": "{payer_slug}-joint-replacement-criteria-{year}",
        "policy_title_tpl": "{payer} Joint Replacement Medical Necessity Criteria Update",
        "changed_clause_tpl": (
            "{payer} updated joint replacement criteria to require BMI < 40 "
            "and documented 3-month supervised weight management program "
            "for members with BMI ≥ 35."
        ),
        "change_summary_tpl": (
            "{payer} added BMI and weight management prerequisites for joint "
            "replacement — affecting CPT {cpts}."
        ),
        "clinical_impact_tpl": (
            "Surgical schedulers must collect BMI documentation and, where applicable, "
            "a 3-month weight management program completion letter."
        ),
        "recommended_action_tpl": (
            "Flag all pending joint replacement PA requests with BMI ≥ 35 "
            "for additional documentation review before submission."
        ),
        "cpt_hints": ["27447", "27130", "27487", "27486"],
    },
    {
        "service_line": "Radiology",
        "change_type": "LOOSENING",
        "policy_id_tpl": "{payer_slug}-ct-colonoscopy-expansion-{year}",
        "policy_title_tpl": "{payer} CT Colonoscopy Coverage Expansion",
        "changed_clause_tpl": (
            "{payer} expanded CT colonoscopy coverage to include members aged 45+ "
            "as a first-line colorectal cancer screening option, "
            "removing the prior optical colonoscopy requirement."
        ),
        "change_summary_tpl": (
            "{payer} loosened CT colonoscopy criteria — now covers age 45+ "
            "without requiring a prior failed optical colonoscopy (CPT {cpts})."
        ),
        "clinical_impact_tpl": (
            "Radiology teams can now schedule CT colonoscopy for eligible patients "
            "aged 45+ without a prior authorization denial history."
        ),
        "recommended_action_tpl": (
            "Update screening order pathways to offer CT colonoscopy as a "
            "first-line option for appropriate patients aged 45+."
        ),
        "cpt_hints": ["74263", "74261", "74262"],
    },
    {
        "service_line": "Neurology",
        "change_type": "TIGHTENING",
        "policy_id_tpl": "{payer_slug}-brain-mri-prerequisite-{year}",
        "policy_title_tpl": "{payer} Brain MRI Prior Authorization Update",
        "changed_clause_tpl": (
            "{payer} now requires a neurologist evaluation within 90 days "
            "before authorizing brain MRI for headache or cognitive symptoms."
        ),
        "change_summary_tpl": (
            "{payer} added a neurology evaluation prerequisite for brain MRI "
            "in headache/cognitive cases — affecting CPT {cpts}."
        ),
        "clinical_impact_tpl": (
            "Neuro imaging staff must attach the neurologist evaluation note "
            "when submitting PA for brain MRI in headache or cognitive decline cases."
        ),
        "recommended_action_tpl": (
            "Audit open brain MRI orders for headache/cognitive indications "
            "and collect neurologist evaluation notes before submission."
        ),
        "cpt_hints": ["70553", "70552", "70551"],
    },
]

PAYERS = ["Aetna", "Cigna", "Humana", "BCBS"]


def _get_ch_client():
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "policydiff"),
        secure=os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true",
        verify=os.getenv("CLICKHOUSE_VERIFY", "true").lower() == "true",
    )


async def trigger_via_pipeline() -> Dict[str, Any]:
    """Entry point — always uses data-driven simulation, optionally enhances with Gemini."""
    return await _data_driven_demo()


async def _data_driven_demo() -> Dict[str, Any]:
    """
    Simulate a new policy change using real ClickHouse data.
    No Gemini call required — all financial data comes from claims_ref.
    """
    client = _get_ch_client()

    # ── Step 1: find what payers already have recent events ────────
    recent = client.query("""
        SELECT payer, service_line, change_type
        FROM policydiff.change_events
        ORDER BY created_at DESC LIMIT 10
    """)
    recent_keys = {(r[0], r[1]) for r in recent.result_rows}

    # ── Step 2: pick a scenario not recently seen ──────────────────
    available = [
        s for s in SCENARIO_TEMPLATES
        if not any(
            (p, s["service_line"]) in recent_keys for p in PAYERS
        )
    ]
    scenario = random.choice(available if available else SCENARIO_TEMPLATES)

    # Pick a payer not recently seen for this service line
    used_payers = {r[0] for r in recent.result_rows}
    payer = next(
        (p for p in random.sample(PAYERS, len(PAYERS)) if p not in used_payers),
        random.choice(PAYERS),
    )
    payer_slug = payer.lower().replace(" ", "-")
    year = datetime.utcnow().year

    # ── Step 3: get real CPT revenue data from claims_ref ─────────
    cpt_hints = scenario["cpt_hints"]
    placeholder = ", ".join(f"'{c}'" for c in cpt_hints)
    claims = client.query(f"""
        SELECT cpt, avg_reimbursement_usd, claim_count_90d
        FROM policydiff.claims_ref
        WHERE cpt IN ({placeholder})
        ORDER BY avg_reimbursement_usd DESC
    """)

    if claims.result_rows:
        # Real data: use actual CPTs and revenue from claims_ref
        cpts = [r[0] for r in claims.result_rows[:3]]
        # Annualized revenue at risk (90-day count × 4 × avg reimbursement)
        revenue = sum(
            r[1] * r[2] * 4 for r in claims.result_rows[:3]
        )
    else:
        # Fallback: estimate from scenario hints
        cpts = cpt_hints[:2]
        revenue = random.uniform(500_000, 2_500_000)

    revenue = round(revenue, -3)  # round to nearest $1000
    cpts_str = ", ".join(cpts)

    # ── Step 4: render narrative from templates ────────────────────
    ctx = dict(payer=payer, payer_slug=payer_slug, year=year, cpts=cpts_str)
    policy_id = scenario["policy_id_tpl"].format(**ctx)
    policy_title = scenario["policy_title_tpl"].format(**ctx)
    changed_clause = scenario["changed_clause_tpl"].format(**ctx)
    change_summary = scenario["change_summary_tpl"].format(**ctx)
    clinical_impact = scenario["clinical_impact_tpl"].format(**ctx)
    recommended_action = scenario["recommended_action_tpl"].format(**ctx)
    change_type = scenario["change_type"]
    service_line = scenario["service_line"]
    confidence = round(random.uniform(0.87, 0.97), 2)

    cited_markdown = f"""# {policy_title}

## Summary
{payer} updated its {service_line} coverage policy effective {datetime.utcnow().strftime('%B %Y')}.
{change_summary}

## What Changed
{changed_clause}

## Affected CPT Codes
{chr(10).join(f'- {c}' for c in cpts)}

## Financial Impact
Estimated annualized revenue at risk: ${revenue:,.0f}
Based on {len(cpts)} CPT code(s) with real claims volume data.

## Clinical Operations Impact
{clinical_impact}

## Recommended Action
{recommended_action}

## Source
{payer} provider policy portal — {policy_id}
"""

    # ── Step 5: optionally enhance narrative with Gemini ──────────
    if GEMINI_API_KEY:
        try:
            cited_markdown = await _enhance_with_gemini(
                payer, policy_title, change_summary, cited_markdown
            )
        except Exception as exc:
            logger.info("Gemini enhancement skipped (%s) — using template.", exc)

    # ── Step 6: insert into change_events ─────────────────────────
    event_id = str(uuid.uuid4())
    now_dt = datetime.utcnow()

    client.insert(
        "policydiff.change_events",
        [[
            event_id, now_dt, str(uuid.uuid4()),
            payer, policy_id, policy_title,
            f"https://provider.{payer_slug}.com/policies/{policy_id}",
            service_line, change_type, confidence,
            changed_clause, change_summary, clinical_impact,
            cpts, revenue, "", cited_markdown,
            recommended_action, "demo-simulated", "PUBLISHED",
        ]],
        column_names=[
            "event_id", "created_at", "diff_id", "payer", "policy_id",
            "policy_title", "url", "service_line", "change_type", "confidence",
            "changed_clause", "change_summary", "clinical_impact",
            "cpt_codes_affected", "revenue_at_risk_usd", "cited_md_url",
            "cited_markdown", "recommended_action", "datadog_trace_id", "status",
        ],
    )

    logger.info(
        "Demo simulated: %s [%s] %s — $%s at risk (CPTs: %s)",
        payer, service_line, change_type, revenue, cpts_str,
    )

    return {
        "status": "DEMO_TRIGGERED",
        "message": (
            f"Simulated {change_type.lower()} by {payer} in {service_line} — "
            f"'{policy_title}' — ${revenue:,.0f} at risk. "
            f"Refresh in 3 seconds."
        ),
    }


async def _enhance_with_gemini(
    payer: str, title: str, summary: str, base_markdown: str
) -> str:
    """
    Optional: ask Gemini to enrich the cited_markdown narrative.
    Uses gemini-2.0-flash (higher RPD limit than 2.5 Flash).
    Silently returns base_markdown on any failure including rate limits.
    """
    enhance_model = "gemini-2.0-flash"  # 1500 RPD vs 20 RPD for 2.5 Flash
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{enhance_model}:generateContent?key={GEMINI_API_KEY}"
    )
    prompt = (
        f"You are a healthcare policy analyst. Improve the following policy change "
        f"brief for '{title}' by {payer}. Make it sound authoritative and clinical. "
        f"Keep the same structure and all financial numbers. Return only the markdown, no fences.\n\n"
        f"{base_markdown}"
    )

    async with httpx.AsyncClient(timeout=20.0) as http:
        resp = await http.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.5, "maxOutputTokens": 800},
        })
        if resp.status_code in (429, 503, 500):
            return base_markdown  # silently fall back
        resp.raise_for_status()
        raw = resp.json()
        return raw["candidates"][0]["content"]["parts"][0]["text"].strip()
