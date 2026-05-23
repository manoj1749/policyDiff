from __future__ import annotations

from app.clickhouse_repo import ClickHouseRepo
from app.config_loader import load_watchlist
from app.hash_utils import compute_version_hash
from app.scheduler import get_watchlist_path


def main() -> None:
    policies = load_watchlist(get_watchlist_path())
    policy = next(
        item for item in policies if item.payer == "UHC" and item.policy_id == "cardiac-mri"
    )
    normalized_text = (
        "COVERAGE CRITERIA\n"
        "1. Cardiac MRI is covered for established cardiomyopathy.\n"
        "2. New requirement: prior echocardiogram must be documented.\n"
        "CPT 75557 75559 75561"
    )
    repo = ClickHouseRepo()
    repo.insert_policy_version(
        {
            "payer": policy.payer,
            "policy_id": policy.policy_id,
            "policy_title": policy.policy_title,
            "url": policy.url,
            "source_type": policy.source_type,
            "version_hash": compute_version_hash(normalized_text),
            "normalized_text": normalized_text,
            "raw_extract": normalized_text,
            "extraction_status": "SUCCESS",
            "extraction_error": "",
        }
    )


if __name__ == "__main__":
    main()

