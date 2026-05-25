# PolicyDiff

AI-powered payer policy change detection for healthcare denial prevention.

Healthcare payers (UnitedHealthcare, Aetna, Cigna, Humana) frequently update their Clinical Policy Bulletins, prior authorization rules, and medical-necessity criteria. Hospitals typically discover these changes weeks later — after claims start getting denied. PolicyDiff monitors those documents automatically, classifies every change with Gemini AI, computes annualized revenue at risk per CPT code, and surfaces the results in a live dashboard.

---

## Architecture

```
Nimble (web scraping)
        ↓
ingestion-service     — fetches + normalizes payer policy docs, detects version changes, writes diff_candidates
        ↓
classifier-service    — Gemini 2.5 Flash classifies each diff, computes revenue impact, publishes evidence briefs
        ↓
api-dashboard-service — FastAPI + Next.js dashboard, live change feed, revenue risk breakdown
```

All three services share a single ClickHouse database.

---

## Services

| Service | Port | Responsibility |
|---|---|---|
| `ingestion-service` | 8001 | Nimble scraping, text normalization, diff detection |
| `classifier-service` | 8002 | Gemini classification, revenue impact, Senso publishing, Datadog tracing |
| `api-dashboard-service` | 8003 / 3000 | FastAPI read layer + Next.js dashboard |

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- ClickHouse (local via Homebrew or cloud)
- API keys: Gemini, Nimble, Datadog, Senso

### 1. Configure environment

```bash
cp .env.example .env
# Fill in: GEMINI_API_KEY, NIMBLE_API_KEY, DD_API_KEY, SENSO_API_KEY
# For cloud ClickHouse: set CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_SECURE=true
```

### 2. Set up ClickHouse schema

```bash
# Apply schemas in order
for f in infra/clickhouse/*.sql; do
  clickhouse client --query "$(cat $f)"
done
```

Or for cloud ClickHouse, apply each file via the HTTP interface.

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

### 4. Seed reference data

```bash
cd services/classifier-service && source .venv/bin/activate
python3 scripts/seed_claims_ref.py
```

### 5. Start all services

```bash
bash start_services.sh
```

Then open:
- **Dashboard** → http://localhost:3000
- **Classifier API docs** → http://localhost:8002/docs
- **Dashboard API docs** → http://localhost:8003/docs

---

## Key Endpoints

### Classifier (`classifier-service`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health |
| `POST` | `/classify/run-once` | Process all pending diffs |
| `POST` | `/classify/diff/{diff_id}` | Classify a specific diff |
| `GET` | `/classify/pending` | List pending diff candidates |

### Dashboard backend (`api-dashboard-service`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health |
| `GET` | `/api/changes` | Live change feed |
| `GET` | `/api/risk-summary` | Revenue at risk by payer / service line |
| `GET` | `/api/system-status` | Pipeline health snapshot |
| `POST` | `/api/demo/trigger` | Seed and classify a demo event |

---

## Environment Variables

| Variable | Service | Description |
|---|---|---|
| `CLICKHOUSE_HOST` | All | ClickHouse hostname |
| `CLICKHOUSE_PORT` | All | 8123 (HTTP) or 8443 (HTTPS) |
| `CLICKHOUSE_SECURE` | All | `true` for cloud/TLS |
| `NIMBLE_API_KEY` | Ingestion | Nimble web scraping key |
| `GEMINI_API_KEY` | Classifier | Google AI Studio key |
| `GEMINI_MODEL` | Classifier | Default: `gemini-2.5-flash` |
| `DD_API_KEY` | Classifier | Datadog API key |
| `DD_SITE` | Classifier | e.g. `us5.datadoghq.com` |
| `DD_LLMOBS_AGENTLESS_ENABLED` | Classifier | `1` for local dev (no Agent) |
| `SENSO_API_KEY` | Classifier | Senso knowledge base key |
| `SENSO_ORG_HANDLE` | Classifier | Your Senso org slug |

---

## ClickHouse Schema

| Table | Owner | Description |
|---|---|---|
| `policy_sources` | Ingestion | Payer policy watchlist |
| `policy_versions` | Ingestion | Full versioned policy snapshots |
| `diff_candidates` | Ingestion | Detected changes awaiting classification |
| `ingestion_runs` | Ingestion | Run history and stats |
| `claims_ref` | Classifier | CPT code reimbursement reference data |
| `change_events` | Classifier | Classified changes with revenue impact |
| `classification_errors` | Classifier | Failed classification attempts |

---

## Observability

Every Gemini call is traced in **Datadog LLM Observability** with:
- Workflow span: `process_pending_diffs`
- LLM span: `call_gemini` — model, provider, input prompt, output
- Manual annotations for token-level visibility with the `google-genai` SDK

To view traces: [app.datadoghq.com](https://app.datadoghq.com) → LLM Observability → `policydiff`

---

## Demo

Use the **Trigger Demo** button on the dashboard or call `POST /api/demo/trigger` to seed a sample UHC Cardiac MRI policy change and run it through the full classification pipeline. The event appears in the feed in real time.

---

## Logs

```bash
tail -f /tmp/policydiff-classifier.log
tail -f /tmp/policydiff-dashboard.log
tail -f /tmp/policydiff-frontend.log
```

---

## Stop All Services

```bash
pkill -f 'uvicorn app.main:app' && pkill -f 'next.*dev'
```
