#!/usr/bin/env bash
# ============================================================
# PolicyDiff — start_services.sh
# Starts all three services from a single terminal.
# All services read from the root .env (single source of truth).
# ============================================================

set -a
source "$(dirname "$0")/.env"
set +a

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Kill any stale instances first ───────────────────────────
echo "Stopping any previous PolicyDiff processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next.*dev" 2>/dev/null
pkill -f "next-server" 2>/dev/null
# Force-free ports 8002, 8003, 3000
for port in 8002 8003 3000; do
  pid=$(lsof -ti:$port 2>/dev/null)
  [ -n "$pid" ] && kill -9 $pid 2>/dev/null && echo "  Freed :$port (pid $pid)"
done
sleep 2

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " PolicyDiff — starting all services"
echo " Env: $ROOT/.env"
echo " ClickHouse: $CLICKHOUSE_HOST"
echo " Model: $GEMINI_MODEL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Classifier (Engineer B) :8002 ────────────────────────────
echo ""
echo "▶  Starting classifier-service on :8002..."
cd "$ROOT/services/classifier-service"
source .venv/bin/activate
DD_SITE="$DD_SITE" DD_API_KEY="$DD_API_KEY" \
DD_LLMOBS_ENABLED="$DD_LLMOBS_ENABLED" \
DD_LLMOBS_AGENTLESS_ENABLED="$DD_LLMOBS_AGENTLESS_ENABLED" \
DD_LLMOBS_ML_APP="$DD_LLMOBS_ML_APP" \
ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port 8002 \
  >> /tmp/policydiff-classifier.log 2>&1 &
CLASSIFIER_PID=$!
echo "   PID $CLASSIFIER_PID  →  /tmp/policydiff-classifier.log"

# ── Dashboard backend (Engineer C) :8003 ─────────────────────
echo "▶  Starting api-dashboard-service on :8003..."
cd "$ROOT/services/api-dashboard-service/backend"
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8003 \
  >> /tmp/policydiff-dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "   PID $DASHBOARD_PID  →  /tmp/policydiff-dashboard.log"

# ── Dashboard frontend :3000 ──────────────────────────────────
echo "▶  Starting Next.js frontend on :3000..."
cd "$ROOT/services/api-dashboard-service/frontend"
npm run dev >> /tmp/policydiff-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   PID $FRONTEND_PID  →  /tmp/policydiff-frontend.log"

# ── Health check ─────────────────────────────────────────────
echo ""
echo "Waiting for services to boot..."
sleep 8

PASS=0
for port in 8002 8003 3000; do
  if curl -s "http://localhost:$port" > /dev/null 2>&1 || \
     curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
    echo "  ✓ :$port  up"
    ((PASS++))
  else
    echo "  ✗ :$port  not responding yet (check log above)"
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Dashboard → http://localhost:3000"
echo " Classifier API → http://localhost:8002/docs"
echo " Dashboard API → http://localhost:8003/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To stop all services:"
echo "  pkill -f 'uvicorn app.main:app' && pkill -f 'next.*dev'"
echo ""
echo "Logs:"
echo "  tail -f /tmp/policydiff-classifier.log"
echo "  tail -f /tmp/policydiff-dashboard.log"
echo "  tail -f /tmp/policydiff-frontend.log"

wait
