# PolicyDiff — Engineer C README
## API + Dashboard + Integration Service

**Owner:** Engineer C  
**Microservice name:** `api-dashboard-service`  
**Primary responsibility:** Build the FastAPI read layer, Next.js dashboard, demo trigger controls, Senso markdown viewer integration, optional x402 export flow, and optional Luminai webhook routing.

---

## 1. Overall project context

PolicyDiff is a payer-policy monitoring system that helps hospitals prevent denials before they happen.

The full system is split across three engineers:

```text
Engineer A — ingestion-service
Nimble fetches payer policies, normalizes HTML/PDF text, stores versions, creates diff_candidates.

Engineer B — classifier-service
Gemini classifies the diff, computes revenue impact, publishes markdown to Senso/cited.md, traces with Datadog, writes change_events.

Engineer C — api-dashboard-service
Reads change_events, displays the operational dashboard, links to Senso markdown, supports optional x402 export and optional Luminai webhook routing.
```

Your service is the **user-facing layer**. The judges should understand the whole project by looking at your dashboard.

---

## 2. What you are building

You are building:

1. A FastAPI backend that reads from ClickHouse.
2. A Next.js dashboard that refreshes live.
3. A change feed showing classified payer policy changes.
4. A risk summary showing annualized revenue at risk by payer, service line, and change type.
5. A Senso/cited.md markdown integration so users can open generated evidence briefs.
6. A debug demo trigger that can create a full sample flow if live scraping is slow.
7. Optional x402 payment flow for exporting an evidence packet as PDF.
8. Optional Luminai webhook routing to simulate workflow handoff.

Important: x402 remains optional because the final plan does not require payment gating for the core MVP. If implemented, use it for **PDF export** or **full evidence export**, not for blocking the main dashboard.

---

## 3. Service boundary

### You own

```text
services/api-dashboard-service/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── clickhouse_repo.py
│   │   ├── schemas.py
│   │   ├── evidence_export.py
│   │   ├── x402_optional.py
│   │   ├── luminai_optional.py
│   │   └── demo_trigger.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── changes/[eventId]/page.tsx
│   │   └── markdown/[eventId]/page.tsx
│   ├── components/
│   │   ├── ChangeFeed.tsx
│   │   ├── RiskSummaryCards.tsx
│   │   ├── RevenueRiskChart.tsx
│   │   ├── EvidencePanel.tsx
│   │   ├── SensoMarkdownLink.tsx
│   │   └── OptionalX402ExportButton.tsx
│   ├── lib/
│   │   └── api.ts
│   └── package.json
└── README.md
```

### You read from

- `change_events`
- `diff_candidates` for debugging only
- `ingestion_runs` for status cards only

### You optionally write to

- `workflow_alerts` if Luminai optional routing is implemented
- no core pipeline tables

### You do not own

- Nimble scraping
- Gemini classification
- Senso publishing logic
- Datadog instrumentation of LLM calls

---

## 4. Dashboard goals

The dashboard must answer these questions clearly:

1. What policy changed?
2. Which payer changed it?
3. Was it a tightening, loosening, scope change, or stylistic edit?
4. Which service line is affected?
5. Which CPT codes are affected?
6. How much annualized revenue is at risk?
7. What action should the hospital team take?
8. Where is the Senso/cited.md markdown evidence brief?

---

## 5. Required frontend views

### 5.1 Home dashboard

Route:

```text
/
```

Components:

- total revenue at risk card,
- number of policy changes detected,
- high-risk tightening count,
- revenue at risk by service line,
- revenue at risk by change type,
- live change feed,
- system status panel.

### 5.2 Change detail page

Route:

```text
/changes/[eventId]
```

Show:

- payer,
- policy title,
- policy URL,
- change type,
- confidence,
- changed clause,
- clinical impact,
- affected CPT codes,
- revenue at risk,
- recommended action,
- Senso/cited.md link,
- optional “Export evidence as PDF” button.

### 5.3 Senso markdown viewer/link

Route:

```text
/markdown/[eventId]
```

This page should display either:

1. embedded stored `cited_markdown` from ClickHouse, or
2. a prominent link to `cited_md_url`.

The dashboard must make it obvious that Senso generated a public citeable markdown artifact.

---

## 6. FastAPI API contracts

Your backend runs on port `8003`.

### `GET /health`

```json
{
  "service": "api-dashboard-service",
  "status": "ok"
}
```

### `GET /api/changes`

Returns latest classified change events.

Query params:

```text
limit: int = 50
change_type: optional string
payer: optional string
service_line: optional string
```

Response:

```json
[
  {
    "event_id": "uuid",
    "created_at": "2026-05-23 12:05:00",
    "payer": "UHC",
    "policy_id": "cardiac-mri",
    "policy_title": "Cardiac MRI Coverage Policy",
    "service_line": "Cardiology",
    "change_type": "TIGHTENING",
    "confidence": 0.92,
    "change_summary": "UHC added a stress test prerequisite before cardiac MRI approval.",
    "clinical_impact": "Cardiology prior-auth staff must attach stress test documentation.",
    "cpt_codes_affected": ["75561"],
    "revenue_at_risk_usd": 261000,
    "cited_md_url": "https://cited.md/policydiff/uhc-cardiac-mri-tightening",
    "status": "PUBLISHED"
  }
]
```

### `GET /api/changes/{event_id}`

Returns one event with full evidence details.

Response:

```json
{
  "event_id": "uuid",
  "payer": "UHC",
  "policy_id": "cardiac-mri",
  "policy_title": "Cardiac MRI Coverage Policy",
  "url": "https://...",
  "service_line": "Cardiology",
  "change_type": "TIGHTENING",
  "confidence": 0.92,
  "changed_clause": "Member must have completed a cardiac stress test within the past 6 months.",
  "change_summary": "UHC added a stress test prerequisite before cardiac MRI approval.",
  "clinical_impact": "Prior-auth staff must collect recent stress test documentation.",
  "cpt_codes_affected": ["75561"],
  "revenue_at_risk_usd": 261000,
  "recommended_action": "Update cardiology prior authorization checklist.",
  "cited_md_url": "https://cited.md/policydiff/uhc-cardiac-mri-tightening",
  "cited_markdown": "# UHC Cardiac MRI Policy Tightened..."
}
```

### `GET /api/risk-summary`

Response:

```json
{
  "total_revenue_at_risk_usd": 913000,
  "by_change_type": [
    {"change_type": "TIGHTENING", "count": 3, "revenue_at_risk_usd": 850000},
    {"change_type": "SCOPE_CHANGE", "count": 1, "revenue_at_risk_usd": 63000}
  ],
  "by_service_line": [
    {"service_line": "Cardiology", "count": 2, "revenue_at_risk_usd": 500000},
    {"service_line": "Orthopedics", "count": 1, "revenue_at_risk_usd": 260000}
  ],
  "by_payer": [
    {"payer": "UHC", "count": 2, "revenue_at_risk_usd": 400000}
  ]
}
```

### `GET /api/system-status`

Response:

```json
{
  "pending_diffs": 0,
  "processed_diffs_today": 4,
  "latest_ingestion_run": "2026-05-23 12:00:00",
  "latest_change_event": "2026-05-23 12:05:00",
  "senso_published_count": 4,
  "datadog_enabled": true
}
```

### `POST /api/demo/trigger`

This endpoint is for demo fallback only. It should create or trigger a known cardiac MRI change if the live pipeline is slow.

Best implementation:

- call Engineer A `/ingest/policy/UHC/cardiac-mri`, or
- insert a demo `diff_candidates` row, then call Engineer B `/classify/run-once`.

Response:

```json
{
  "status": "DEMO_TRIGGERED",
  "message": "Demo diff submitted. Refresh dashboard in 10 seconds."
}
```

---

## 7. Frontend refresh interval

Use this default:

```text
FRONTEND_REFRESH_INTERVAL_SECONDS=10
```

Behavior:

- home dashboard refreshes every 10 seconds,
- detail page refreshes only on manual reload,
- during demo, use a visible “Last updated at” timestamp.

---

## 8. Optional x402 flow

Keep x402 optional, but implement it if time allows because it is a strong demo add-on.

Do **not** block the main evidence trail. The core app should work without payment.

Recommended optional flow:

```text
Free dashboard:
- change summary
- revenue impact
- cited.md link

Optional x402 action:
- pay $2 USDC to export a polished PDF evidence packet
```

Endpoint:

```text
GET /api/changes/{event_id}/export-pdf
```

If no payment header:

```json
{
  "error": "Payment required for PDF export",
  "x402": {
    "scheme": "exact",
    "network": "base-sepolia",
    "maxAmountRequired": "2000000",
    "asset": "USDC_BASE_SEPOLIA_CONTRACT",
    "payTo": "wallet_address",
    "description": "PolicyDiff PDF evidence export"
  }
}
```

If payment header exists:

```json
{
  "status": "PAID",
  "download_url": "/api/changes/{event_id}/export-pdf/download"
}
```

For hackathon demo, you may accept any non-empty `X-Payment` header as a mocked payment proof, but label it clearly as demo verification.

---

## 9. Optional Luminai webhook routing

Luminai routing is optional. If implemented, it simulates sending the alert to the affected service line workflow queue.

Who receives the alert?

| Service line | Routed to |
|---|---|
| Cardiology | Cardiology prior authorization team |
| Radiology | Imaging authorization / radiology billing team |
| Orthopedics | Orthopedics prior authorization team |
| Neurology | Neurology service-line admin |
| Oncology | Oncology authorization / revenue-cycle team |
| Unknown | General revenue cycle management team |

Endpoint:

```text
POST /api/changes/{event_id}/route-alert
```

Payload to Luminai webhook:

```json
{
  "workflow_type": "policy_change_alert",
  "priority": "HIGH",
  "route_to": "Cardiology prior authorization team",
  "payer": "UHC",
  "policy_id": "cardiac-mri",
  "summary": "UHC added a stress test prerequisite before cardiac MRI approval.",
  "revenue_at_risk_usd": 261000,
  "cited_md_url": "https://cited.md/policydiff/uhc-cardiac-mri-tightening",
  "action_required": "Update prior authorization checklist before next submission."
}
```

For demo, use RequestBin or httpbin if there is no real Luminai webhook.

---

## 10. ClickHouse queries

### Recent changes

```sql
SELECT
  event_id,
  created_at,
  payer,
  policy_id,
  policy_title,
  service_line,
  change_type,
  confidence,
  change_summary,
  clinical_impact,
  cpt_codes_affected,
  revenue_at_risk_usd,
  cited_md_url,
  status
FROM policydiff.change_events
ORDER BY created_at DESC
LIMIT {limit:UInt32};
```

### Risk by change type

```sql
SELECT
  change_type,
  count() AS count,
  sum(revenue_at_risk_usd) AS revenue_at_risk_usd
FROM policydiff.change_events
GROUP BY change_type
ORDER BY revenue_at_risk_usd DESC;
```

### Risk by service line

```sql
SELECT
  service_line,
  count() AS count,
  sum(revenue_at_risk_usd) AS revenue_at_risk_usd
FROM policydiff.change_events
GROUP BY service_line
ORDER BY revenue_at_risk_usd DESC;
```

### Senso publish count

```sql
SELECT count()
FROM policydiff.change_events
WHERE cited_md_url != '';
```

---

## 11. Docker Compose guidance

Do not create a reverse dependency between ingestion and classifier.

Recommended shape:

```yaml
services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    ports:
      - "8123:8123"
      - "9000:9000"

  ingestion-service:
    build: ./services/ingestion-service
    depends_on:
      - clickhouse
    ports:
      - "8001:8001"

  classifier-service:
    build: ./services/classifier-service
    depends_on:
      - clickhouse
    ports:
      - "8002:8002"
    command: ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002

  api-dashboard-service:
    build: ./services/api-dashboard-service/backend
    depends_on:
      - clickhouse
    ports:
      - "8003:8003"

  frontend:
    build: ./services/api-dashboard-service/frontend
    depends_on:
      - api-dashboard-service
    ports:
      - "3000:3000"
```

---

## 12. Environment variables

Backend:

```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DB=policydiff

FRONTEND_REFRESH_INTERVAL_SECONDS=10

# Optional x402
ENABLE_X402=false
WALLET_ADDRESS=your_wallet
X402_PRICE_USDC=2000000

# Optional Luminai
ENABLE_LUMINAI=false
LUMINAI_WEBHOOK_URL=https://httpbin.org/post
```

Frontend:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8003
NEXT_PUBLIC_REFRESH_INTERVAL_SECONDS=10
```

---

## 13. UI design requirements

Use a clean dark dashboard.

Minimum visual sections:

```text
Header:
  PolicyDiff — Payer Policy Change Monitor
  Last refreshed timestamp

Metric cards:
  Total annualized revenue at risk
  Number of tightening changes
  Number of Senso citeables published
  Pending diffs

Charts:
  Revenue at risk by service line
  Revenue at risk by change type

Feed:
  One card per change event
  Badge color by change type
  Senso/cited.md link visible
  View details button
```

Badge colors:

```text
TIGHTENING: red
LOOSENING: green
SCOPE_CHANGE: amber
STYLISTIC: gray
```

---

## 14. Integration checklist

- [ ] `/api/changes` returns real `change_events` rows.
- [ ] `/api/risk-summary` aggregates revenue correctly.
- [ ] Dashboard refreshes every 10 seconds.
- [ ] Every change card shows Senso/cited.md link if available.
- [ ] Change detail page shows full evidence.
- [ ] Demo trigger works or gracefully explains what to run.
- [ ] Optional x402 export does not block core app.
- [ ] Optional Luminai routing sends payload to RequestBin/httpbin.
- [ ] Docker Compose starts services without circular dependencies.

---

## 15. Demo script for your part

1. Open dashboard.
2. Show total revenue at risk.
3. Click “Trigger Demo Change” if needed.
4. Wait 10 seconds.
5. Show new `TIGHTENING` card.
6. Open detail page.
7. Click Senso/cited.md link.
8. Optional: click “Export PDF with x402” and show 402 response.
9. Optional: click “Route Alert” and show webhook request.

---

## 16. Definition of done

Engineer C is done when:

1. FastAPI reads from ClickHouse successfully.
2. Next.js dashboard shows real `change_events` data.
3. Dashboard refresh interval is set to 10 seconds.
4. Senso/cited.md links are visible and clickable.
5. Detail page displays changed clause, CPT codes, clinical impact, and revenue risk.
6. Optional x402 export is either implemented or clearly disabled without breaking the app.
7. Optional Luminai routing is either implemented or clearly disabled without breaking the app.
8. The whole repo can run with Docker Compose without circular dependencies.

Your success metric is simple: **a judge should understand PolicyDiff’s value in 30 seconds by looking at your dashboard.**
