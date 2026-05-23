from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.clickhouse_repo import ClickHouseRepo
from app.config_loader import load_watchlist
from app.scheduler import build_scheduler, get_watchlist_path, process_policy, run_ingestion_once


@asynccontextmanager
async def lifespan(_: FastAPI):
    repo = ClickHouseRepo()
    try:
        repo.ping()
    except Exception as exc:
        raise RuntimeError(f"ClickHouse startup check failed: {exc}") from exc

    scheduler = build_scheduler()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="ingestion-service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "ingestion-service", "status": "ok"}


@app.post("/ingest/run-once")
def ingest_run_once() -> dict[str, object]:
    return run_ingestion_once()


@app.post("/ingest/policy/{payer}/{policy_id}")
def ingest_policy(payer: str, policy_id: str) -> dict[str, object]:
    policies = load_watchlist(get_watchlist_path())
    target = next((policy for policy in policies if policy.payer == payer and policy.policy_id == policy_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Policy not found in watchlist")
    return process_policy(target, ClickHouseRepo())


@app.get("/ingest/pending-diffs")
def list_pending_diffs() -> list[dict[str, object]]:
    return ClickHouseRepo().list_pending_diffs()
