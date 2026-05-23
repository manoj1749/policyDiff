from __future__ import annotations

from app.clickhouse_repo import ClickHouseRepo
from app.config_loader import load_watchlist
from app.hash_utils import compute_version_hash
from app.scheduler import get_watchlist_path


SEED_TEXT = {
    ("UHC", "cardiac-mri"): "COVERAGE CRITERIA\n1. Cardiac MRI is covered for established cardiomyopathy.\nCPT 75557 75559 75561",
    ("Aetna", "cpb-0761"): "MAGNETIC RESONANCE IMAGING OF THE EXTREMITIES\nCoverage applies when x-ray is inconclusive.\nCPT 73221 73721",
    ("Cigna", "cardiac-imaging"): "CARDIAC IMAGING GUIDELINES\nPrior authorization required for advanced imaging.\nCPT 93306 93454 75561",
    ("Humana", "mri-spine"): "MRI SPINE CLINICAL CRITERIA\nMRI spine is indicated for neurologic deficit.\nCPT 72141 72148 72156 72158",
}


def main() -> None:
    repo = ClickHouseRepo()
    policies = load_watchlist(get_watchlist_path())
    repo.sync_policy_sources([policy.to_source_row() for policy in policies])

    for policy in policies:
        key = (policy.payer, policy.policy_id)
        raw_text = SEED_TEXT.get(
            key,
            f"{policy.policy_title}\nCoverage criteria seeded for demo.\nCPT {' '.join(policy.default_cpt_codes)}",
        )
        normalized_text = raw_text.strip()
        repo.insert_policy_version(
            {
                "payer": policy.payer,
                "policy_id": policy.policy_id,
                "policy_title": policy.policy_title,
                "url": policy.url,
                "source_type": policy.source_type,
                "version_hash": compute_version_hash(normalized_text),
                "normalized_text": normalized_text,
                "raw_extract": raw_text,
                "extraction_status": "SUCCESS",
                "extraction_error": "",
            }
        )


if __name__ == "__main__":
    main()

