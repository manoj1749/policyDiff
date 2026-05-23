"""
seed_demo_diff.py — Inserts a realistic PENDING diff_candidates row for demo/testing.

Simulates Engineer A detecting a UHC cardiac-MRI policy change.
Run this when you want to test the classifier without Engineer A's service:

    python scripts/seed_demo_diff.py

Then trigger classification:
    curl -X POST http://localhost:8002/classify/run-once
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import clickhouse_connect
from app.config_loader import settings

OLD_TEXT = """
CARDIAC MRI — COVERAGE CRITERIA (Effective January 2024)

UnitedHealthcare covers Cardiac MRI (CPT 75561) for members who meet ALL of the following:

1. The member has a confirmed diagnosis of cardiomyopathy or myocarditis.
2. An echocardiogram has been performed within the past 12 months.
3. The ordering physician is a board-certified cardiologist.
4. The service is medically necessary and not duplicative of recent imaging.

PRIOR AUTHORIZATION REQUIRED: Yes.

EXCLUSIONS:
- Routine screening in asymptomatic members.
- Members with implanted non-MRI-compatible devices.
""".strip()

NEW_TEXT = """
CARDIAC MRI — COVERAGE CRITERIA (Effective May 2026)

UnitedHealthcare covers Cardiac MRI (CPT 75561) for members who meet ALL of the following:

1. The member has a confirmed diagnosis of cardiomyopathy or myocarditis.
2. An echocardiogram has been performed within the past 12 months.
3. The ordering physician is a board-certified cardiologist.
4. The service is medically necessary and not duplicative of recent imaging.
5. Member must have completed a cardiac stress test within the past 6 months,
   with documented results submitted at the time of prior authorization.

PRIOR AUTHORIZATION REQUIRED: Yes.

EXCLUSIONS:
- Routine screening in asymptomatic members.
- Members with implanted non-MRI-compatible devices.
- Members who have not completed the required cardiac stress test.
""".strip()


def main() -> None:
    diff_id = str(uuid.uuid4())

    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
    )

    client.insert(
        "policydiff.diff_candidates",
        [
            [
                diff_id,
                "UHC",
                "cardiac-mri",
                "Cardiac MRI Coverage Policy",
                "https://www.uhcprovider.com/en/policies-protocols/b-d/cardiac-mri.html",
                "html",
                "Cardiology",
                111111111,      # old_hash (fake)
                222222222,      # new_hash (fake)
                OLD_TEXT,
                NEW_TEXT,
                ["75557", "75559", "75561"],
                "PENDING",
            ]
        ],
        column_names=[
            "diff_id",
            "payer",
            "policy_id",
            "policy_title",
            "url",
            "source_type",
            "service_line",
            "old_hash",
            "new_hash",
            "old_text",
            "new_text",
            "default_cpt_codes",
            "status",
        ],
    )

    print(f"✓ Inserted demo PENDING diff_candidate")
    print(f"  diff_id  : {diff_id}")
    print(f"  payer    : UHC")
    print(f"  policy_id: cardiac-mri")
    print(f"\nTo classify it, run:")
    print(f"  curl -X POST http://localhost:8002/classify/run-once")
    print(f"  # or: curl -X POST http://localhost:8002/classify/diff/{diff_id}")


if __name__ == "__main__":
    main()
