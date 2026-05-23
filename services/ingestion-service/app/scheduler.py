from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler

from app.clickhouse_repo import ClickHouseRepo
from app.config_loader import PolicyConfig, load_watchlist
from app.hash_utils import compute_version_hash
from app.nimble_client import fetch_policy
from app.normalizer import normalize_policy_text
from app.settings import get_settings


FetchPolicyFn = Callable[[str, str], dict[str, Any]]
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_watchlist_path() -> Path:
    return get_settings().watchlist_path


def get_poll_interval_minutes() -> int:
    return get_settings().poll_interval_minutes


def process_policy(
    policy: PolicyConfig,
    repo: ClickHouseRepo,
    fetcher: FetchPolicyFn = fetch_policy,
) -> dict[str, Any]:
    fetched = fetcher(policy.url, policy.source_type)
    if fetched["status"] != "SUCCESS":
        logger.warning(
            "Fetch failed for %s/%s after %s attempt(s): %s",
            policy.payer,
            policy.policy_id,
            fetched.get("attempts", 1),
            fetched.get("error", "Unknown Nimble error"),
        )
        return {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "result": "FETCH_FAILED",
            "error": fetched.get("error", "Unknown Nimble error"),
        }

    normalized = normalize_policy_text(fetched["raw_extract"], policy.source_type)
    if not normalized:
        logger.warning("Normalized text empty for %s/%s", policy.payer, policy.policy_id)
        return {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "result": "EXTRACTION_EMPTY",
            "error": "Nimble returned no extractable policy text",
        }

    version_hash = compute_version_hash(normalized)
    previous = repo.get_latest_policy_version(policy.payer, policy.policy_id)
    version_row = {
        "payer": policy.payer,
        "policy_id": policy.policy_id,
        "policy_title": policy.policy_title,
        "url": policy.url,
        "source_type": policy.source_type,
        "version_hash": version_hash,
        "normalized_text": normalized,
        "raw_extract": fetched["raw_extract"],
        "extraction_status": "SUCCESS",
        "extraction_error": "",
    }

    if previous is None:
        repo.insert_policy_version(version_row)
        logger.info("Stored first version for %s/%s", policy.payer, policy.policy_id)
        return {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "result": "FIRST_VERSION_STORED",
            "new_hash": version_hash,
        }

    if int(previous["version_hash"]) == version_hash:
        logger.info("No change detected for %s/%s", policy.payer, policy.policy_id)
        return {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "result": "NO_CHANGE",
            "old_hash": int(previous["version_hash"]),
            "new_hash": version_hash,
        }

    repo.insert_policy_version(version_row)
    diff_id = repo.insert_diff_candidate(
        {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "policy_title": policy.policy_title,
            "url": policy.url,
            "source_type": policy.source_type,
            "service_line": policy.service_line,
            "old_hash": int(previous["version_hash"]),
            "new_hash": version_hash,
            "old_text": previous["normalized_text"],
            "new_text": normalized,
            "default_cpt_codes": policy.default_cpt_codes,
            "status": "PENDING",
        }
    )
    logger.info("Created diff candidate %s for %s/%s", diff_id, policy.payer, policy.policy_id)
    return {
        "payer": policy.payer,
        "policy_id": policy.policy_id,
        "result": "DIFF_CREATED",
        "diff_id": diff_id,
        "old_hash": int(previous["version_hash"]),
        "new_hash": version_hash,
    }


def run_ingestion_once(
    repo: ClickHouseRepo | None = None,
    fetcher: FetchPolicyFn = fetch_policy,
) -> dict[str, Any]:
    active_policies = [policy for policy in load_watchlist(get_watchlist_path()) if policy.active]
    repository = repo or ClickHouseRepo()
    repository.sync_policy_sources([policy.to_source_row() for policy in active_policies])
    run_meta = repository.create_ingestion_run()
    run_id = run_meta["run_id"]
    started_at = run_meta["started_at"]

    policies_succeeded = 0
    policies_failed = 0
    diffs_created = 0
    last_error = ""

    try:
        for policy in active_policies:
            outcome = process_policy(policy, repository, fetcher=fetcher)
            if outcome["result"] in {"FIRST_VERSION_STORED", "NO_CHANGE", "DIFF_CREATED"}:
                policies_succeeded += 1
                if outcome["result"] == "DIFF_CREATED":
                    diffs_created += 1
            else:
                policies_failed += 1
                last_error = f"{policy.payer}/{policy.policy_id}: {outcome.get('error', '')}"
        status = "SUCCESS" if policies_failed == 0 else "PARTIAL_SUCCESS"
        repository.finish_ingestion_run(
            run_id=run_id,
            started_at=started_at,
            policies_attempted=len(active_policies),
            policies_succeeded=policies_succeeded,
            policies_failed=policies_failed,
            diffs_created=diffs_created,
            status=status,
            error_message=last_error,
        )
        return {
            "run_id": run_id,
            "policies_attempted": len(active_policies),
            "policies_succeeded": policies_succeeded,
            "policies_failed": policies_failed,
            "diffs_created": diffs_created,
            "status": status,
        }
    except Exception as exc:
        repository.finish_ingestion_run(
            run_id=run_id,
            started_at=started_at,
            policies_attempted=len(active_policies),
            policies_succeeded=policies_succeeded,
            policies_failed=max(1, len(active_policies) - policies_succeeded),
            diffs_created=diffs_created,
            status="FAILED",
            error_message=str(exc),
        )
        raise


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.configure(timezone="UTC")
    scheduler.add_job(run_ingestion_once, "interval", minutes=get_poll_interval_minutes())
    return scheduler
