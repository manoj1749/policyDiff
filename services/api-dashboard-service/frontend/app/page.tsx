"use client";

import React, {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useState,
} from "react";
import {
  CHANGE_TYPE_META,
  fetchChanges,
  fetchRiskSummary,
  fetchSystemStatus,
  formatCurrency,
  REFRESH_INTERVAL_MS,
  triggerDemo,
  type ChangeEventSummary,
  type RiskSummary,
  type SystemStatus,
} from "@/lib/api";

const ZERO_RISK: RiskSummary = {
  total_revenue_at_risk_usd: 0,
  by_change_type: [],
  by_service_line: [],
  by_payer: [],
};

function computeRiskFromEvents(events: ChangeEventSummary[]): RiskSummary {
  const ctMap = new Map<string, { count: number; revenue: number }>();
  const slMap = new Map<string, { count: number; revenue: number }>();
  const pyMap = new Map<string, { count: number; revenue: number }>();
  let total = 0;
  for (const e of events) {
    const rev = e.revenue_at_risk_usd ?? 0;
    total += rev;
    const ct = ctMap.get(e.change_type) ?? { count: 0, revenue: 0 };
    ctMap.set(e.change_type, { count: ct.count + 1, revenue: ct.revenue + rev });
    const sl = slMap.get(e.service_line) ?? { count: 0, revenue: 0 };
    slMap.set(e.service_line, { count: sl.count + 1, revenue: sl.revenue + rev });
    const py = pyMap.get(e.payer) ?? { count: 0, revenue: 0 };
    pyMap.set(e.payer, { count: py.count + 1, revenue: py.revenue + rev });
  }
  const byRev = <T extends { revenue_at_risk_usd: number }>(arr: T[]) =>
    arr.sort((a, b) => b.revenue_at_risk_usd - a.revenue_at_risk_usd);
  return {
    total_revenue_at_risk_usd: total,
    by_change_type: byRev(
      [...ctMap.entries()].map(([change_type, { count, revenue }]) => ({
        change_type, count, revenue_at_risk_usd: revenue,
      }))
    ),
    by_service_line: byRev(
      [...slMap.entries()].map(([service_line, { count, revenue }]) => ({
        service_line, count, revenue_at_risk_usd: revenue,
      }))
    ),
    by_payer: byRev(
      [...pyMap.entries()].map(([payer, { count, revenue }]) => ({
        payer, count, revenue_at_risk_usd: revenue,
      }))
    ),
  };
}

import RevenueRiskChart from "@/components/RevenueRiskChart";
import ChangeFeed from "@/components/ChangeFeed";

export default function HomePage() {
  const [allChanges, setAllChanges] = useState<ChangeEventSummary[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [demoMessage, setDemoMessage] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);

  const [filterChangeType, setFilterChangeType] = useState("");
  const [filterPayer, setFilterPayer] = useState("");
  const [filterServiceLine, setFilterServiceLine] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [isCleared, setIsCleared] = useState(false);
  const [knownEventIds, setKnownEventIds] = useState<Set<string> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [changes, nextRisk, nextStatus] = await Promise.all([
        fetchChanges({ limit: 50 }),
        fetchRiskSummary(),
        fetchSystemStatus(),
      ]);
      startTransition(() => {
        setAllChanges(changes);
        setRisk(nextRisk);
        setStatus(nextStatus);
        setLastRefresh(new Date());
      });
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const payerOptions = Array.from(new Set(allChanges.map((e) => e.payer))).sort();
  const serviceLineOptions = Array.from(new Set(allChanges.map((e) => e.service_line))).sort();

  const hasAnyFilter =
    !!filterChangeType || !!filterPayer || !!filterServiceLine || !!filterDateFrom || !!filterDateTo;

  const filteredChanges = isCleared
    ? []
    : allChanges.filter((event) => {
        if (knownEventIds !== null && knownEventIds.has(event.event_id)) return false;
        if (filterChangeType && event.change_type !== filterChangeType) return false;
        if (filterPayer && event.payer !== filterPayer) return false;
        if (filterServiceLine && event.service_line !== filterServiceLine) return false;
        if (filterDateFrom) {
          const from = new Date(filterDateFrom).getTime();
          if (new Date(event.created_at).getTime() < from) return false;
        }
        if (filterDateTo) {
          const to = new Date(`${filterDateTo}T23:59:59`).getTime();
          if (new Date(event.created_at).getTime() > to) return false;
        }
        return true;
      });

  const deferredChanges = useDeferredValue(filteredChanges);

  const displayRisk = isCleared
    ? ZERO_RISK
    : knownEventIds !== null
      ? computeRiskFromEvents(filteredChanges)
      : (risk ?? ZERO_RISK);

  const tighteningCount = displayRisk.by_change_type.find((c) => c.change_type === "TIGHTENING")?.count ?? 0;
  const topPayer = displayRisk.by_payer[0] ?? null;
  const topServiceLine = displayRisk.by_service_line[0] ?? null;

  function handleClear() {
    setFilterChangeType("");
    setFilterPayer("");
    setFilterServiceLine("");
    setFilterDateFrom("");
    setFilterDateTo("");
    setIsCleared(true);
    setKnownEventIds(null);
  }

  function restoreFeed() {
    setIsCleared(false);
    setKnownEventIds(null);
  }

  async function handleTriggerDemo() {
    setDemoLoading(true);
    setDemoMessage("");
    try {
      const response = await triggerDemo();
      setDemoMessage(response.message);
      setIsCleared(false);
      setTimeout(refresh, 3000);
    } catch {
      setDemoMessage("Demo trigger failed. Check that the backend is running.");
    } finally {
      setDemoLoading(false);
    }
  }

  const pendingOk = !status || status.pending_diffs === 0;

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="logo-mark">PD</div>
          <div className="brand-info">
            <span className="brand-name">PolicyDiff</span>
            <span className="brand-sub">Policy Intelligence</span>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Pipeline</div>
          <div className="pipeline-list">
            <div className="pipeline-item">
              <span className="p-dot p-ok" />
              <span className="p-name">Ingestion</span>
            </div>
            <div className="pipeline-item">
              <span className="p-dot p-ok" />
              <span className="p-name">Classifier</span>
            </div>
            <div className="pipeline-item">
              <span className={`p-dot ${pendingOk ? "p-ok" : "p-warn"}`} />
              <span className="p-name">Queue</span>
              {!pendingOk && (
                <span className="p-badge">{status?.pending_diffs}</span>
              )}
            </div>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Today</div>
          <div className="sidebar-stats-list">
            <div className="sidebar-stat">
              <span className="ss-label">Processed</span>
              <span className="ss-val">{status?.processed_diffs_today ?? "—"}</span>
            </div>
            <div className="sidebar-stat">
              <span className="ss-label">Published</span>
              <span className="ss-val">{status?.senso_published_count ?? "—"}</span>
            </div>
            <div className="sidebar-stat">
              <span className="ss-label">Pending</span>
              <span className={`ss-val ${!pendingOk ? "ss-warn" : ""}`}>
                {status?.pending_diffs ?? "—"}
              </span>
            </div>
          </div>
        </div>

        <div className="sidebar-bottom">
          {lastRefresh && (
            <div className="refresh-line">
              <span className="live-pulse" />
              <span className="refresh-ts">Updated {lastRefresh.toLocaleTimeString()}</span>
            </div>
          )}
          <button
            className="btn btn-demo btn-sm sidebar-btn"
            onClick={handleTriggerDemo}
            disabled={demoLoading}
            id="trigger-demo-btn"
          >
            {demoLoading ? "Simulating…" : "Trigger Demo"}
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="main-area">
        {/* Header */}
        <header className="main-header">
          <div className="mh-left">
            <h1 className="main-title">Payer Policy Monitor</h1>
            <span className="main-sub">AI-classified · revenue impact · 10s refresh</span>
          </div>
          {status?.datadog_enabled && (
            <span className="header-pill">Datadog tracing</span>
          )}
        </header>

        {demoMessage && <div className="demo-notice">{demoMessage}</div>}

        {/* Stats strip */}
        <div className="stats-strip">
          <div className="stat-block stat-block-primary">
            <span className="stat-num">
              {formatCurrency(displayRisk.total_revenue_at_risk_usd)}
            </span>
            <span className="stat-lbl">Annual revenue at risk</span>
          </div>
          <div className="stat-sep" />
          <div className="stat-block">
            <span className="stat-num">{isCleared ? 0 : deferredChanges.length}</span>
            <span className="stat-lbl">Changes classified</span>
          </div>
          <div className="stat-sep" />
          <div className="stat-block">
            <span className="stat-num stat-red">{tighteningCount}</span>
            <span className="stat-lbl">Tightening</span>
          </div>
          <div className="stat-sep" />
          <div className="stat-block">
            <span className="stat-num stat-md">{topPayer?.payer ?? "—"}</span>
            <span className="stat-lbl">Top exposed payer</span>
          </div>
          <div className="stat-sep" />
          <div className="stat-block">
            <span className="stat-num stat-md">{topServiceLine?.service_line ?? "—"}</span>
            <span className="stat-lbl">Top service line</span>
          </div>
        </div>

        {/* Command bar */}
        <div className="command-bar">
          <div className="cmd-filters">
            <select
              className="cmd-select"
              value={filterChangeType}
              onChange={(e) => { setFilterChangeType(e.target.value); restoreFeed(); }}
              id="filter-change-type"
            >
              <option value="">All types</option>
              <option value="TIGHTENING">Tightening</option>
              <option value="LOOSENING">Loosening</option>
              <option value="SCOPE_CHANGE">Scope change</option>
              <option value="STYLISTIC">Stylistic</option>
            </select>

            <select
              className="cmd-select"
              value={filterPayer}
              onChange={(e) => { setFilterPayer(e.target.value); restoreFeed(); }}
              id="filter-payer"
            >
              <option value="">All payers</option>
              {payerOptions.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>

            <select
              className="cmd-select"
              value={filterServiceLine}
              onChange={(e) => { setFilterServiceLine(e.target.value); restoreFeed(); }}
              id="filter-service-line"
            >
              <option value="">All services</option>
              {serviceLineOptions.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <input
              type="date"
              className="cmd-select cmd-date"
              value={filterDateFrom}
              onChange={(e) => { setFilterDateFrom(e.target.value); restoreFeed(); }}
              id="filter-date-from"
              title="From date"
            />
            <input
              type="date"
              className="cmd-select cmd-date"
              value={filterDateTo}
              onChange={(e) => { setFilterDateTo(e.target.value); restoreFeed(); }}
              id="filter-date-to"
              title="To date"
            />

            {hasAnyFilter && (
              <button className="cmd-clear" id="filter-clear-btn" onClick={handleClear}>
                Clear
              </button>
            )}
          </div>

          <div className="cmd-right">
            {isCleared ? (
              <span className="cmd-state-cleared">Feed cleared</span>
            ) : hasAnyFilter ? (
              <span className="cmd-state-filtered">
                {deferredChanges.length} of {allChanges.length} shown
              </span>
            ) : (
              <span className="cmd-count">{allChanges.length} events</span>
            )}
          </div>
        </div>

        {/* Active filter tags */}
        {!isCleared && hasAnyFilter && (
          <div className="active-tags-row">
            {filterPayer && (
              <span className="active-tag">Payer: {filterPayer}</span>
            )}
            {filterServiceLine && (
              <span className="active-tag">Service: {filterServiceLine}</span>
            )}
            {filterChangeType && (
              <span className="active-tag">
                Type: {CHANGE_TYPE_META[filterChangeType]?.label ?? filterChangeType}
              </span>
            )}
            {filterDateFrom && (
              <span className="active-tag">From: {filterDateFrom}</span>
            )}
            {filterDateTo && (
              <span className="active-tag">To: {filterDateTo}</span>
            )}
          </div>
        )}

        {/* Revenue risk charts */}
        <section aria-label="Revenue Risk Charts">
          <RevenueRiskChart risk={displayRisk} />
        </section>

        {/* Change feed */}
        <section className="feed-section" aria-label="Policy Changes">
          {isCleared ? (
            <div className="cleared-state">
              <p className="cleared-icon">Feed cleared</p>
              <p className="cleared-title">No events shown</p>
              <p className="cleared-hint">
                Apply a filter above or use the demo trigger to populate the feed.
              </p>
            </div>
          ) : (
            <ChangeFeed events={deferredChanges} loading={loading} />
          )}
        </section>
      </div>
    </div>
  );
}
