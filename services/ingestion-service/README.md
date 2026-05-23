# ingestion-service

FastAPI microservice for policy ingestion, normalization, version hashing, and diff candidate creation.

## Local run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Configuration

Create `.env` from `.env.example` in `services/ingestion-service/` and set the real values there. The application loads that file through `app/settings.py`.

If you are connecting to ClickHouse Cloud, use the full service hostname and set:

```text
CLICKHOUSE_SECURE=true
CLICKHOUSE_VERIFY=true
CLICKHOUSE_PORT=8443
```

The app validates ClickHouse during startup and will fail fast if the configured backend is unreachable.

## Demo data

```powershell
python scripts\seed_demo_versions.py
python scripts\seed_changed_cardiac_mri.py
```

## Environment

```text
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DB=policydiff
CLICKHOUSE_SECURE=false
CLICKHOUSE_VERIFY=true
NIMBLE_API_KEY=your_key
NIMBLE_API_URL=https://api.nimbleway.com/v1/extract
POLL_INTERVAL_MINUTES=30
WATCHLIST_PATH=./config/watchlist.yaml
```
