"""
seed_claims_ref.py — Seeds claims_ref if empty. Safe to run multiple times.

    python scripts/seed_claims_ref.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clickhouse_repo import seed_claims_ref_if_empty

if __name__ == "__main__":
    seeded = seed_claims_ref_if_empty()
    if not seeded:
        print("claims_ref already populated — nothing to do.")
