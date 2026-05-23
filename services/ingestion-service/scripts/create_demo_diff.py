from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.clickhouse_repo import ClickHouseRepo
from app.config_loader import load_watchlist
from app.hash_utils import compute_version_hash
from app.scheduler import get_watchlist_path


TARGET_PAYER = "Aetna"
TARGET_POLICY_ID = "cpb-0761"


def main() -> None:
    repo = ClickHouseRepo()
    policies = load_watchlist(get_watchlist_path())
    policy = next(
        item for item in policies if item.payer == TARGET_PAYER and item.policy_id == TARGET_POLICY_ID
    )
    previous = repo.get_latest_policy_version(policy.payer, policy.policy_id)
    if previous is None:
        raise RuntimeError(
            f"No existing version found for {policy.payer}/{policy.policy_id}. "
            "Run live ingestion or seed demo versions first."
        )

    new_text = (
        "MAGNETIC RESONANCE IMAGING OF THE EXTREMITIES\n"
        "Coverage applies when x-ray is inconclusive.\n"
        "New requirement: six weeks of conservative therapy must be documented.\n"
        "CPT 73221 73721"
    )
    new_hash = compute_version_hash(new_text)
    old_hash = int(previous["version_hash"])
    if new_hash == old_hash:
        raise RuntimeError("Demo diff text produced the same hash as the previous version.")

    repo.insert_policy_version(
        {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "policy_title": policy.policy_title,
            "url": policy.url,
            "source_type": policy.source_type,
            "version_hash": new_hash,
            "normalized_text": new_text,
            "raw_extract": new_text,
            "extraction_status": "SUCCESS",
            "extraction_error": "",
        }
    )
    diff_id = repo.insert_diff_candidate(
        {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "policy_title": policy.policy_title,
            "url": policy.url,
            "source_type": policy.source_type,
            "service_line": policy.service_line,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "old_text": previous["normalized_text"],
            "new_text": new_text,
            "default_cpt_codes": policy.default_cpt_codes,
            "status": "PENDING",
        }
    )
    print(
        {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "diff_id": diff_id,
            "result": "DIFF_CREATED",
        }
    )


if __name__ == "__main__":
    main()
