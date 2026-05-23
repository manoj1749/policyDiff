# PolicyDiff — api-dashboard-service

**Owner:** Engineer C  
**Port:** Backend `8003` · Frontend `3000`

## Quick Start

```bash
# 1. Clone & set up env
cp .env.example .env
# Fill in GEMINI_API_KEY, NIMBLE_API_KEY, SENSO_API_KEY, DD_API_KEY

# 2. Start everything
docker compose up --build

# 3. Open dashboard
open http://localhost:3000

# 4. Trigger demo event (if live scraping is slow)
curl -X POST http://localhost:8003/api/demo/trigger
```

## Backend Local Dev

```bash
cd services/api-dashboard-service/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

## Frontend Local Dev

```bash
cd services/api-dashboard-service/frontend
npm install
npm run dev   # http://localhost:3000
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/changes` | Recent change events (filter by type/payer/service_line) |
| GET | `/api/changes/{event_id}` | Full event detail |
| GET | `/api/risk-summary` | Aggregated revenue at risk |
| GET | `/api/system-status` | Pipeline health metrics |
| POST | `/api/demo/trigger` | Seed a demo TIGHTENING event |
| GET | `/api/changes/{event_id}/export-pdf` | Optional x402 PDF export |
| POST | `/api/changes/{event_id}/route-alert` | Optional Luminai routing |

## Optional Features

### x402 PDF Export
Set `ENABLE_X402=true` in `.env`. The endpoint will return a 402 with payment instructions.
For the hackathon demo, any non-empty `X-Payment` header is accepted as mock proof.

### Luminai Alert Routing
Set `ENABLE_LUMINAI=true` and `LUMINAI_WEBHOOK_URL=https://httpbin.org/post` (or your real URL).
