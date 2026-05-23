"""
seed_claims_ref.py — Inserts reference claims data into policydiff.claims_ref.

Run once after applying the ClickHouse schema:
    python scripts/seed_claims_ref.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow importing app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import clickhouse_connect
from app.config_loader import settings

SEED_ROWS = [
    # (cpt, service_line, avg_reimbursement_usd, claim_count_90d, payer)
    ("75557", "Cardiology",   1800.0,  75,  "UHC"),
    ("75559", "Cardiology",   2100.0,  65,  "UHC"),
    ("75561", "Cardiology",   2200.0,  90,  "UHC"),
    ("93306", "Cardiology",    700.0, 220,  "UHC"),
    ("93454", "Cardiology",   4200.0,  40,  "Cigna"),
    ("73221", "Radiology",    1240.0, 120,  "Aetna"),
    ("73721", "Radiology",    1840.0, 180,  "Aetna"),
    ("72141", "Orthopedics",  1580.0, 210,  "Humana"),
    ("72148", "Orthopedics",  1650.0, 240,  "Humana"),
    ("71046", "Radiology",     285.0, 300,  "Aetna"),
]


def main() -> None:
    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
    )

    client.insert(
        "policydiff.claims_ref",
        SEED_ROWS,
        column_names=["cpt", "service_line", "avg_reimbursement_usd", "claim_count_90d", "payer"],
    )

    print(f"✓ Inserted {len(SEED_ROWS)} rows into policydiff.claims_ref")

    # Quick verification
    result = client.query("SELECT count() AS n FROM policydiff.claims_ref")
    for row in result.named_results():
        print(f"  Total rows in claims_ref: {row['n']}")


if __name__ == "__main__":
    main()
