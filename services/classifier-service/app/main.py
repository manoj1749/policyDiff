"""
main.py — FastAPI entry point for the PolicyDiff classifier-service.

Endpoints:
  GET  /health
  POST /classify/run-once
  POST /classify/diff/{diff_id}
  GET  /classify/pending

Background APScheduler loop calls process_pending_diffs() every
CLASSIFIER_POLL_INTERVAL_SECONDS.
"""
from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException

# On Vercel, persistent background threads don't survive between requests.
# Vercel Cron calls POST /classify/run-once on the configured schedule instead.
_ON_VERCEL = bool(os.getenv("VERCEL"))

from app.classifier import classify_diff
from app.clickhouse_repo import (
    get_candidate_by_id,
    get_pending_candidates,
    insert_change_event,
    insert_classification_error,
    mark_error,
    mark_processed,
)
from app.config_loader import settings
from app.datadog_setup import init_datadog, workflow
from app.revenue_impact import compute_revenue_at_risk
from app.senso_publisher import publish_to_senso

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core pipeline — single diff processing
# ---------------------------------------------------------------------------


def process_one_diff(candidate: dict) -> dict:
    """
    Full pipeline for one diff_candidates row:
      1. Classify with Gemini (traced via Datadog @llm)
      2. Compute revenue at risk
      3. Publish to Senso/cited.md
      4. Insert change_event
      5. Mark diff_candidates PROCESSED

    Returns a summary dict. Raises on unrecoverable errors.
    """
    diff_id = candidate["diff_id"]

    # --- Step 1: Gemini classification ---
    try:
        classification = classify_diff(candidate)
    except Exception as exc:
        error_msg = f"Gemini classification failed: {exc}"
        insert_classification_error(
            diff_id=diff_id,
            payer=candidate.get("payer", ""),
            policy_id=candidate.get("policy_id", ""),
            error_stage="GEMINI_CLASSIFICATION",
            error_message=error_msg,
        )
        mark_error(diff_id, error_msg)
        raise RuntimeError(error_msg) from exc

    # Guard: UNSUPPORTED changed_clause — do not publish to Senso
    if classification.get("changed_clause") == "UNSUPPORTED":
        logger.warning("Diff %s returned UNSUPPORTED changed_clause. Marking NEEDS_REVIEW.", diff_id)
        mark_error(diff_id, "UNSUPPORTED: Gemini could not identify a specific changed clause.")
        raise RuntimeError("UNSUPPORTED changed_clause — skipped Senso publish.")

    # --- Step 2: Revenue at risk ---
    revenue = compute_revenue_at_risk(
        cpt_codes=classification.get("cpt_codes_affected", []),
        change_type=classification["change_type"],
    )

    # --- Step 3: Senso publish ---
    event_payload = {
        **candidate,
        **classification,
        "revenue_at_risk_usd": revenue,
        "datadog_trace_id": "",  # populated by ddtrace automatically via span context
    }
    cited_md_url, cited_markdown = publish_to_senso(event_payload)

    event_payload["cited_md_url"] = cited_md_url
    event_payload["cited_markdown"] = cited_markdown
    event_payload["status"] = "PUBLISHED" if cited_md_url else "CLASSIFIED_NOT_PUBLISHED"

    # --- Step 4: Insert change_event ---
    event_id = insert_change_event(event_payload)

    # --- Step 5: Mark PROCESSED ---
    mark_processed(diff_id)

    return {
        "diff_id": diff_id,
        "event_id": event_id,
        "change_type": classification["change_type"],
        "revenue_at_risk_usd": revenue,
        "cited_md_url": cited_md_url,
        "status": event_payload["status"],
    }


# ---------------------------------------------------------------------------
# Batch processing (called by scheduler and /classify/run-once)
# ---------------------------------------------------------------------------


@workflow(name="process_pending_diffs", ml_app="policydiff")
def process_pending_diffs(limit: int | None = None) -> dict:
    """
    Fetch up to `limit` (or CLASSIFIER_BATCH_SIZE) pending diff candidates and
    process each one. Decorated with @workflow for Datadog tracing.
    """
    candidates = get_pending_candidates(limit=limit)
    processed = 0
    published = 0
    errors = 0

    for candidate in candidates:
        try:
            result = process_one_diff(candidate)
            processed += 1
            if result.get("cited_md_url"):
                published += 1
        except Exception as exc:
            errors += 1
            logger.error(
                "Failed to process diff %s: %s\n%s",
                candidate.get("diff_id"),
                exc,
                traceback.format_exc(),
            )

    logger.info(
        "Batch complete — processed=%d, published=%d, errors=%d.",
        processed, published, errors,
    )
    return {"processed": processed, "published": published, "errors": errors}


# ---------------------------------------------------------------------------
# APScheduler
# ---------------------------------------------------------------------------

_scheduler = BackgroundScheduler()


def _scheduled_job() -> None:
    logger.info("Scheduler: running process_pending_diffs.")
    process_pending_diffs()


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init Datadog, optionally start scheduler. Shutdown: stop scheduler."""
    init_datadog(ml_app=settings.dd_llmobs_ml_app)
    if _ON_VERCEL:
        logger.info("Running on Vercel — in-process scheduler disabled; using Vercel Cron.")
    else:
        _scheduler.add_job(
            _scheduled_job,
            "interval",
            seconds=settings.poll_interval_seconds,
            id="classify_poll",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info(
            "Classifier scheduler started (interval=%ds).", settings.poll_interval_seconds
        )
    yield
    if not _ON_VERCEL:
        _scheduler.shutdown(wait=False)
        logger.info("Classifier scheduler stopped.")


app = FastAPI(
    title="PolicyDiff — Classifier Service",
    description="Classifies payer policy diffs with Gemini, computes revenue impact, and publishes to Senso/cited.md.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
def health():
    return {"service": "classifier-service", "status": "ok"}


@app.post("/classify/run-once", tags=["Classification"])
def run_once():
    """
    Synchronously process up to CLASSIFIER_BATCH_SIZE pending diff candidates.
    """
    result = process_pending_diffs()
    return result


@app.post("/classify/diff/{diff_id}", tags=["Classification"])
def classify_single(diff_id: str):
    """
    Process a single diff candidate by UUID.
    """
    candidate = get_candidate_by_id(diff_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"diff_id {diff_id} not found.")
    if candidate.get("status") != "PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"diff_id {diff_id} has status '{candidate['status']}', not PENDING.",
        )
    try:
        result = process_one_diff(candidate)
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/classify/pending", tags=["Debug"])
def list_pending():
    """
    Debug endpoint — returns the current PENDING diff candidates.
    """
    candidates = get_pending_candidates(limit=50)
    return [
        {
            "diff_id": c["diff_id"],
            "payer": c["payer"],
            "policy_id": c["policy_id"],
            "created_at": c["created_at"],
        }
        for c in candidates
    ]
