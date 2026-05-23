# PolicyDiff — `classifier-service`

> **Owner:** Engineer B  
> **Port:** `8002`  
> **Purpose:** Read pending policy diffs from ClickHouse → classify with Gemini → compute revenue impact → publish to Senso/cited.md → write `change_events` → trace with Datadog LLM Observability.

---

## Quick Start

```bash
# 1. Copy and fill in your API keys
cp .env.example .env

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Apply ClickHouse schemas (run from repo root)
cat ../../infra/clickhouse/001_ingestion_schema.sql | curl -s http://localhost:8123 --data-binary @-
cat ../../infra/clickhouse/002_classifier_schema.sql | curl -s http://localhost:8123 --data-binary @-

# 4. Seed reference data
python scripts/seed_claims_ref.py

# 5. Seed a demo diff candidate (no Engineer A required)
python scripts/seed_demo_diff.py

# 6. Start the service
ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/classify/run-once` | Process up to `CLASSIFIER_BATCH_SIZE` pending diffs |
| `POST` | `/classify/diff/{diff_id}` | Process one diff by UUID |
| `GET` | `/classify/pending` | Debug — list pending candidates |

### Example

```bash
# Trigger classification
curl -X POST http://localhost:8002/classify/run-once

# Expected response
{"processed": 1, "published": 1, "errors": 0}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Required. Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Model to use |
| `SENSO_API_KEY` | — | Required for Senso publish |
| `SENSO_ORG_HANDLE` | `policydiff` | Senso org slug |
| `DD_API_KEY` | — | Required for Datadog tracing |
| `DD_LLMOBS_ENABLED` | `1` | Enable LLM Observability |
| `CLICKHOUSE_HOST` | `localhost` | ClickHouse host |
| `CLASSIFIER_BATCH_SIZE` | `5` | Max diffs per poll cycle |
| `CLASSIFIER_POLL_INTERVAL_SECONDS` | `60` | Polling interval (use `10` for demo) |

See `.env.example` for the full list.

---

## Architecture

```
APScheduler (every N seconds)
    └── process_pending_diffs()  [@workflow → Datadog trace]
            └── process_one_diff(candidate)
                    ├── classify_diff()           [classifier.py]
                    │       └── call_gemini()     [@llm → Datadog LLM span]
                    ├── compute_revenue_at_risk()  [revenue_impact.py]
                    ├── publish_to_senso()         [senso_publisher.py]
                    ├── insert_change_event()      [clickhouse_repo.py]
                    └── mark_processed()           [clickhouse_repo.py]
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests do **not** require a live ClickHouse or Gemini connection.

---

## Datadog LLM Observability

The service **must** be started with `ddtrace-run` to emit traces:

```bash
ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Each Gemini call produces a Datadog LLM span visible in **APM → LLM Observability**.

---

## Senso/cited.md

Each successfully classified change publishes a markdown brief to Senso.  
The `cited_md_url` is stored in `change_events.cited_md_url` and displayed by Engineer C's dashboard.

If Senso is unavailable, the event is saved with `status = CLASSIFIED_NOT_PUBLISHED` — no data is lost.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Gemini returns invalid JSON | Retries once with stricter prompt; then logs to `classification_errors` and marks `ERROR` |
| `changed_clause = UNSUPPORTED` | Skips Senso publish, marks `ERROR`/`NEEDS_REVIEW` |
| Senso publish fails | Saves event with `cited_md_url = ''`, `status = CLASSIFIED_NOT_PUBLISHED` |
| `STYLISTIC` change | Writes event with `revenue_at_risk_usd = 0` |
