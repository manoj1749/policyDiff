# PolicyDiff

AI-powered payer policy change detection for healthcare denial prevention.

Healthcare payers (UnitedHealthcare, Aetna, Cigna, Humana) frequently update their Clinical Policy Bulletins, prior authorization rules, and medical-necessity criteria. Hospitals typically discover these changes weeks later — after claims start getting denied. PolicyDiff monitors those documents automatically, classifies every change with Gemini AI, computes annualized revenue at risk per CPT code using real CMS Medicare reimbursement data, and surfaces the results in a live dashboard.

---

## Architecture

```
Nimble (web scraping)
        ↓
ingestion-service     — fetches + normalizes payer policy docs, detects version changes, writes diff_candidates
        ↓
classifier-service    — Gemini 2.5 Flash classifies each diff, computes revenue impact, publishes evidence briefs to Senso
        ↓
api-dashboard-service — FastAPI read layer + Next.js dashboard with live change feed and revenue risk breakdown
```

All three services share a single ClickHouse database (cloud-hosted on Railway).

---

## Services

| Service | Port | Responsibility |
|---|---|---|
| `ingestion-service` | 8001 | Nimble scraping, text normalization, SHA-1 diff detection |
| `classifier-service` | 8002 | Gemini classification, revenue impact, Senso publishing, Datadog LLM tracing |
| `api-dashboard-service` | 8003 / 3000 | FastAPI read layer + Next.js dashboard |

---

## Deployment

Services are deployed on **Railway** with ClickHouse Cloud as the database.

### Classifier cron mode (Railway)

The classifier runs on Railway in one-shot mode via a custom start command:

```bash
python -c "from app.main import process_pending_diffs; import json; print(json.dumps(process_pending_diffs()))"
```

This bypasses FastAPI entirely. `seed_claims_ref_if_empty()` runs at the top of `process_pending_diffs()` so CMS data is always seeded before classification, regardless of how the service is invoked.

### Ingestion cron mode (Railway)

The ingestion service runs on a similar one-shot cron schedule to fetch and diff new policy versions.

---

## Quickstart (local dev)

### Prerequisites

- Python 3.11+
- Node.js 18+
- ClickHouse (cloud — set env vars below; local Homebrew install not recommended)
- API keys: Gemini, Nimble, Datadog, Senso

### 1. Configure environment

```bash
cp .env.example .env
# Fill in: GEMINI_API_KEY, NIMBLE_API_KEY, DD_API_KEY, SENSO_API_KEY
# ClickHouse cloud: CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_SECURE=true
# CLICKHOUSE_USER, CLICKHOUSE_PASSWORD, CLICKHOUSE_DB
```

### 2. Apply ClickHouse schema

```bash
for f in infra/clickhouse/*.sql; do
  clickhouse client \
    --host "$CLICKHOUSE_HOST" \
    --port "$CLICKHOUSE_PORT" \
    --secure \
    --user "$CLICKHOUSE_USER" \
    --password "$CLICKHOUSE_PASSWORD" \
    --query "$(cat $f)"
done
```

### 3. Install dependencies

```bash
# Classifier
cd services/classifier-service && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dashboard backend
cd services/api-dashboard-service/backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dashboard frontend
cd services/api-dashboard-service/frontend && npm install
```

### 4. Start all services

```bash
bash start_services.sh
```

- **Dashboard** → http://localhost:3000
- **Classifier API** → http://localhost:8002/docs
- **Dashboard API** → http://localhost:8003/docs

```bash
# Logs
tail -f /tmp/policydiff-classifier.log
tail -f /tmp/policydiff-dashboard.log
tail -f /tmp/policydiff-frontend.log

# Stop
pkill -f 'uvicorn app.main:app' && pkill -f 'next.*dev'
```

---

## Revenue Data — CMS Medicare

`claims_ref` is seeded automatically from the **CMS Medicare Physician & Other Practitioners by Geography and Service** dataset (open data, no API key required).

- Source: `data.cms.gov` — national-level rows, one per CPT code
- Computes a weighted average of facility + non-facility payment rates
- CPT codes are read from `services/classifier-service/config/policy_cpt_map.yaml` — no hardcoding
- Seeding runs automatically on service startup, on each scheduler tick, and at the top of every Railway cron invocation
- Manual trigger: `python3 scripts/seed_claims_ref.py` (idempotent — no-ops if data already present)

---

## Watchlist

`services/ingestion-service/config/watchlist.yaml` defines which policies are monitored.

- **20 policies** across UHC, Aetna, Cigna, Humana
- **11 currently active** (fetched on each ingestion run)
- Fields per entry: `payer`, `policy_id`, `policy_title`, `url`, `source_type`, `service_line`, `default_cpt_codes`, `active`

To add a policy: append an entry to `watchlist.yaml` and add a corresponding CPT fallback block to `policy_cpt_map.yaml`.

---

## Key Endpoints

### Classifier (`classifier-service` · :8002)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/classify/run-once` | Process all pending diffs (Vercel Cron / manual) |
| `POST` | `/classify/diff/{diff_id}` | Classify a specific diff |
| `GET` | `/classify/pending` | List pending diff candidates |

### Dashboard backend (`api-dashboard-service` · :8003)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/api/changes` | Live change feed (filterable) |
| `GET` | `/api/changes/{event_id}` | Single change event detail |
| `GET` | `/api/risk-summary` | Revenue at risk by payer / service line / change type |
| `GET` | `/api/system-status` | Pipeline health snapshot |
| `POST` | `/api/demo/trigger` | Seed and classify a demo event end-to-end |

---

## Environment Variables

| Variable | Service | Description |
|---|---|---|
| `CLICKHOUSE_HOST` | All | ClickHouse hostname |
| `CLICKHOUSE_PORT` | All | `8123` (HTTP) or `8443` (HTTPS) |
| `CLICKHOUSE_SECURE` | All | `true` for cloud / TLS |
| `CLICKHOUSE_USER` | All | ClickHouse username |
| `CLICKHOUSE_PASSWORD` | All | ClickHouse password |
| `CLICKHOUSE_DB` | All | Database name (default: `policydiff`) |
| `NIMBLE_API_KEY` | Ingestion | Nimble web scraping key |
| `GEMINI_API_KEY` | Classifier | Google AI Studio key |
| `GEMINI_MODEL` | Classifier | Default: `gemini-2.5-flash` |
| `DD_API_KEY` | Classifier | Datadog API key |
| `DD_SITE` | Classifier | e.g. `us5.datadoghq.com` |
| `DD_LLMOBS_AGENTLESS_ENABLED` | Classifier | `1` for agentless mode (no local DD Agent) |
| `SENSO_API_KEY` | Classifier | Senso knowledge base key |
| `SENSO_ORG_HANDLE` | Classifier | Your Senso org slug |
| `VERCEL` | Classifier | Set to `1` to disable in-process scheduler (Vercel Cron mode) |

---

## ClickHouse Schema

| Table | Owner | Key columns |
|---|---|---|
| `policy_sources` | Ingestion | `payer`, `policy_id`, `url`, `active` |
| `policy_versions` | Ingestion | `version_hash`, `normalized_text` |
| `diff_candidates` | Ingestion | `diff_id`, `status` (PENDING / PROCESSED / ERROR / NEEDS_REVIEW) |
| `ingestion_runs` | Ingestion | `run_id`, `status`, `diffs_created` |
| `claims_ref` | Classifier | `cpt_code`, `avg_reimbursement_usd`, `annual_volume` |
| `change_events` | Classifier | `event_id`, `change_type`, `revenue_at_risk_usd`, `cited_md_url` |
| `classification_errors` | Classifier | `diff_id`, `error_stage`, `error_message` |

Schema files: `infra/clickhouse/001_ingestion_schema.sql`, `002_classifier_schema.sql`, `003_dashboard_schema.sql`

---

## Classifier Output Schema

Gemini must return a JSON object with these keys:

| Key | Type | Description |
|---|---|---|
| `change_type` | string | `TIGHTENING` / `LOOSENING` / `SCOPE_CHANGE` / `STYLISTIC` |
| `confidence` | float | 0–1 |
| `changed_clause` | string | Exact clause that changed; `"UNSUPPORTED"` if not identifiable |
| `summary` | string | Renamed to `change_summary` in storage |
| `clinical_impact` | string | Plain-language impact on billing/ops |
| `cpt_codes_affected` | string[] | CPT codes affected by this change |
| `recommended_action` | string | What billing/coding teams should do |
| `markdown_title` | string | Title for the Senso evidence brief |

If `changed_clause = "UNSUPPORTED"`, the diff is marked `NEEDS_REVIEW` and skipped from Senso publishing.

---

## Observability

Every Gemini call is traced in **Datadog LLM Observability**:

- Workflow span: `process_pending_diffs`
- LLM span: `call_gemini` — model, provider, prompt, output, token counts
- ML app: `policydiff`

View traces: [app.datadoghq.com](https://app.datadoghq.com) → LLM Observability → `policydiff`

**Note:** `init_datadog()` must be called at module import time (before any `@workflow`/`@llm` decorators). It is called in `classifier-service/app/main.py` at the top level — do not move it into `lifespan()`.

---

## Demo

Click **Trigger Demo** on the dashboard or call `POST /api/demo/trigger` to seed a sample UHC Cardiac MRI policy change and run it through the full pipeline. The classified event appears in the feed within a few seconds.
