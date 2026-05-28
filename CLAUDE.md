# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

PolicyDiff is an AI-powered payer policy change detection system for healthcare denial prevention. It monitors Clinical Policy Bulletins from major payers (UHC, Aetna, Cigna, Humana), classifies every change with Gemini AI, computes annualized revenue at risk per CPT code, and surfaces results in a live dashboard.

## Architecture

Three Python microservices share a single ClickHouse database (`policydiff`):

```
Nimble (web scraping)
        ↓
ingestion-service (:8001)   — fetches + normalizes policy docs, detects version changes, writes diff_candidates
        ↓
classifier-service (:8002)  — Gemini classifies each diff, computes revenue impact, publishes to Senso
        ↓
api-dashboard-service (:8003 + :3000) — FastAPI read layer + Next.js dashboard
```

**Data flow across services:**
1. Ingestion fetches each policy URL via Nimble API → normalizes text → SHA-1 hashes it → if hash changed, writes a row to `diff_candidates` with `status=PENDING`
2. Classifier polls `diff_candidates` for PENDING rows → calls Gemini with a structured prompt → validates the JSON output → looks up CPT code revenue from `claims_ref` → publishes an evidence brief to Senso → inserts a row into `change_events` → marks the diff PROCESSED
3. Dashboard reads `change_events` and risk aggregations; `api-dashboard-service` serves both the FastAPI backend and proxies to the Next.js frontend

## Commands

### Start all services (local dev)

```bash
bash start_services.sh
# Logs: tail -f /tmp/policydiff-{classifier,dashboard,frontend}.log
# Stop: pkill -f 'uvicorn app.main:app' && pkill -f 'next.*dev'
```

### Start individual services

```bash
# Classifier (requires ddtrace-run for Datadog LLM Observability)
cd services/classifier-service && source .venv/bin/activate
ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002

# Dashboard backend
cd services/api-dashboard-service/backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8003

# Frontend
cd services/api-dashboard-service/frontend && npm run dev
```

### Run tests

```bash
# Classifier tests
cd services/classifier-service && source .venv/bin/activate && pytest

# Ingestion tests
cd services/ingestion-service && source .venv/bin/activate && pytest

# Single test file
pytest tests/test_classifier_schema.py

# Single test
pytest tests/test_classifier_schema.py::TestValidateAndNormalize::test_unknown_change_type_defaults_to_stylistic
```

### Docker (full stack)

```bash
docker-compose up --build
```

### Database setup

```bash
# Apply schemas in order (local ClickHouse via Homebrew)
for f in infra/clickhouse/*.sql; do clickhouse client --query "$(cat $f)"; done

# Seed CPT reference data (required before classifier can compute revenue)
cd services/classifier-service && source .venv/bin/activate
python3 scripts/seed_claims_ref.py
```

## Key Config Files

| File | Purpose |
|---|---|
| `.env` | Root env file — single source of truth, loaded by `start_services.sh` and all services |
| `services/ingestion-service/config/watchlist.yaml` | Policy watchlist: payer, policy_id, URL, source_type, service_line, CPT codes |
| `services/classifier-service/config/policy_cpt_map.yaml` | Fallback CPT codes by `payer:policy_id` when Gemini returns none |
| `services/classifier-service/prompts/classification_prompt.md` | Gemini prompt template — uses `{{payer}}`, `{{policy_id}}`, `{{old_text}}`, `{{new_text}}` placeholders |

## Critical Implementation Details

**Datadog init order:** `init_datadog()` is called at module import time in `classifier-service/app/main.py` — before any `@workflow`/`@llm` decorated function. Moving it into `lifespan()` only breaks tracing. The lifespan call is a safe no-op since `LLMObs.enable()` is idempotent.

**Classifier output contract:** Gemini must return a JSON object with keys: `change_type` (one of `TIGHTENING`/`LOOSENING`/`SCOPE_CHANGE`/`STYLISTIC`), `confidence` (0–1 float), `changed_clause`, `summary`, `clinical_impact`, `cpt_codes_affected` (list of strings), `recommended_action`, `markdown_title`. The key `summary` is renamed to `change_summary` in `_validate_and_normalize()` to match the ClickHouse schema.

**UNSUPPORTED guard:** If Gemini cannot identify a specific changed clause it returns `changed_clause="UNSUPPORTED"`. The classifier catches this, marks the diff `NEEDS_REVIEW`, and skips the Senso publish step.

**Vercel deployment mode:** When `VERCEL=1` is set, the APScheduler in-process polling loop is disabled. Vercel Cron calls `POST /classify/run-once` instead.

**Optional features (off by default):**
- `ENABLE_X402=true` — payment-gated PDF export via `GET /api/changes/{event_id}/export-pdf`
- `ENABLE_LUMINAI=true` — alert routing via `POST /api/changes/{event_id}/route-alert`

## ClickHouse Schema

| Table | Owner | Key columns |
|---|---|---|
| `policy_sources` | Ingestion | payer, policy_id, url, active |
| `policy_versions` | Ingestion | payer, policy_id, version_hash, normalized_text |
| `diff_candidates` | Ingestion | diff_id (UUID), status (PENDING/PROCESSED/ERROR/NEEDS_REVIEW), old_text, new_text |
| `ingestion_runs` | Ingestion | run_id, status, diffs_created |
| `claims_ref` | Classifier | cpt_code, avg_reimbursement_usd, annual_volume |
| `change_events` | Classifier | event_id, change_type, revenue_at_risk_usd, cited_md_url |
| `classification_errors` | Classifier | diff_id, error_stage, error_message |

---

## Behavioral Guidelines

### Think Before Coding

Before implementing, state assumptions explicitly. If multiple interpretations exist, present them — don't pick silently. If a simpler approach exists, say so and push back when warranted. If something is unclear, stop, name what's confusing, and ask.

### Simplicity First

Write the minimum code that solves the problem — nothing speculative. No features beyond what was asked, no abstractions for single-use code, no "flexibility" that wasn't requested, no error handling for impossible scenarios. If a solution could be half the size, rewrite it.

### Surgical Changes

Touch only what the request requires. Don't improve adjacent code, comments, or formatting. Match existing style even if you'd do it differently. If you notice unrelated dead code, mention it — don't delete it. Remove imports/variables/functions that *your* changes made unused, but leave pre-existing dead code alone unless asked. Every changed line should trace directly to the user's request.

### Goal-Driven Execution

Transform tasks into verifiable goals before starting. For multi-step tasks, state a brief plan with explicit verify steps:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```

For bug fixes: write a test that reproduces the bug, then make it pass. For refactors: confirm tests pass before and after. Clarifying questions come before implementation, not after mistakes.
