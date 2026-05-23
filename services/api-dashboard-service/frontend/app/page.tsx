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
import RiskSummaryCards from "@/components/RiskSummaryCards";
import RevenueRiskChart from "@/components/RevenueRiskChart";
import ChangeFeed from "@/components/ChangeFeed";

function toTitleCase(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

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
  // After a post-clear demo, holds the IDs that existed before — only new events shown
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

  const payerOptions = Array.from(new Set(allChanges.map((event) => event.payer))).sort();
  const serviceLineOptions = Array.from(
    new Set(allChanges.map((event) => event.service_line)),
  ).sort();

  const hasAnyFilter =
    !!filterChangeType ||
    !!filterPayer ||
    !!filterServiceLine ||
    !!filterDateFrom ||
    !!filterDateTo;

  const filteredChanges = isCleared
    ? []
    : allChanges.filter((event) => {
        // After a post-clear demo, hide every event that existed before the demo was triggered
        if (knownEventIds !== null && knownEventIds.has(event.event_id)) return false;
        if (filterChangeType && event.change_type !== filterChangeType) return false;
        if (filterPayer && event.payer !== filterPayer) return false;
        if (filterServiceLine && event.service_line !== filterServiceLine) return false;
        if (filterDateFrom) {
          const from = new Date(filterDateFrom).getTime();
          const ts = new Date(event.created_at).getTime();
          if (ts < from) return false;
        }
        if (filterDateTo) {
          const to = new Date(`${filterDateTo}T23:59:59`).getTime();
          const ts = new Date(event.created_at).getTime();
          if (ts > to) return false;
        }
        return true;
      });

  const deferredChanges = useDeferredValue(filteredChanges);

  // When cleared: metrics show zero. When demo-after-clear: metrics reflect only new event.
  const displayRisk = isCleared ? ZERO_RISK : (risk ?? ZERO_RISK);
  const topPayer = isCleared ? null : (displayRisk.by_payer?.[0] ?? null);
  const topServiceLine = isCleared ? null : (displayRisk.by_service_line?.[0] ?? null);
  const topChangeType = isCleared ? null : (displayRisk.by_change_type?.[0] ?? null);

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
    // Snapshot the IDs of all events currently in the feed before the demo fires.
    // After the demo we exclude these — only the brand-new event shows.
    const snapshot = new Set(allChanges.map((e) => e.event_id));
    try {
      const response = await triggerDemo();
      setDemoMessage(response.message);
      setIsCleared(false);
      setKnownEventIds(snapshot);
      setTimeout(refresh, 3000);
    } catch {
      setDemoMessage("Demo trigger failed. Check that the backend is running.");
    } finally {
      setDemoLoading(false);
    }
  }

  return (
    <div className="page-root">
      <header className="dashboard-shell">
        <section className="hero-panel">
          <div className="hero-topline">PolicyDiff</div>
          <div className="hero-main">
            <div className="hero-copy">
              <div className="hero-brand-row">
                <div className="logo-mark">PD</div>
                <div>
                  <h1 className="dashboard-title">Payer Policy Change Monitor</h1>
                  <p className="dashboard-subtitle">
                    Detect tightening, quantify revenue risk, and route evidence before denials
                    hit operations.
                  </p>
                </div>
              </div>

              <div className="hero-status-row">
                <span className="hero-pill hero-pill-live">Live refresh every 10 seconds</span>
                {status?.datadog_enabled ? (
                  <span className="hero-pill">Datadog tracing enabled</span>
                ) : null}
                {lastRefresh ? (
                  <span className="hero-pill hero-pill-muted">
                    Last updated {lastRefresh.toLocaleTimeString()}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="hero-actions">
              <button
                className="btn btn-demo btn-hero"
                onClick={handleTriggerDemo}
                disabled={demoLoading}
                id="trigger-demo-btn"
              >
                {demoLoading ? "Simulating..." : "Trigger Demo Change"}
              </button>
              <p className="hero-helper">
                Use the demo path when live payer content is delayed or blocked upstream.
              </p>
            </div>
          </div>

          <div className="hero-insight-grid">
            <article className="insight-card">
              <span className="insight-label">Top payer exposure</span>
              <strong className="insight-value">{topPayer?.payer ?? "Waiting for data"}</strong>
              <span className="insight-sub">
                {topPayer ? formatCurrency(topPayer.revenue_at_risk_usd) : "No risk summary yet"}
              </span>
            </article>
            <article className="insight-card">
              <span className="insight-label">Most exposed service line</span>
              <strong className="insight-value">
                {topServiceLine?.service_line ?? "Waiting for data"}
              </strong>
              <span className="insight-sub">
                {topServiceLine
                  ? `${topServiceLine.count} flagged changes`
                  : "No risk summary yet"}
              </span>
            </article>
            <article className="insight-card">
              <span className="insight-label">Dominant change type</span>
              <strong className="insight-value">
                {topChangeType ? toTitleCase(topChangeType.change_type) : "Waiting for data"}
              </strong>
              <span className="insight-sub">
                {topChangeType
                  ? formatCurrency(topChangeType.revenue_at_risk_usd)
                  : "No risk summary yet"}
              </span>
            </article>
          </div>
        </section>
      </header>

      {demoMessage ? <div className="demo-notice">{demoMessage}</div> : null}

      <section aria-label="Risk Summary Metrics">
        <RiskSummaryCards risk={displayRisk} status={status} loading={loading} />
      </section>

      <section className="control-deck">
        <div className="control-deck-header">
          <div>
            <p className="section-kicker">Ops Workbench</p>
            <h2 className="section-title">Filter the live decision queue</h2>
          </div>
          <div className="control-summary">
            <span className="control-count">{isCleared ? 0 : deferredChanges.length} visible</span>
            <span className="control-divider" />
            <span className="control-count">{allChanges.length} tracked</span>
          </div>
        </div>

        <div className="filter-bar filter-grid">
          <select
            className="filter-select"
            value={filterChangeType}
            onChange={(event) => {
              setFilterChangeType(event.target.value);
              restoreFeed();
            }}
            id="filter-change-type"
          >
            <option value="">All Change Types</option>
            <option value="TIGHTENING">Tightening</option>
            <option value="LOOSENING">Loosening</option>
            <option value="SCOPE_CHANGE">Scope Change</option>
            <option value="STYLISTIC">Stylistic</option>
          </select>

          <select
            className="filter-select"
            value={filterPayer}
            onChange={(event) => {
              setFilterPayer(event.target.value);
              restoreFeed();
            }}
            id="filter-payer"
          >
            <option value="">All Payers</option>
            {payerOptions.map((payer) => (
              <option key={payer} value={payer}>
                {payer}
              </option>
            ))}
          </select>

          <select
            className="filter-select"
            value={filterServiceLine}
            onChange={(event) => {
              setFilterServiceLine(event.target.value);
              restoreFeed();
            }}
            id="filter-service-line"
          >
            <option value="">All Service Lines</option>
            {serviceLineOptions.map((serviceLine) => (
              <option key={serviceLine} value={serviceLine}>
                {serviceLine}
              </option>
            ))}
          </select>

          <input
            type="date"
            className="filter-select filter-date"
            value={filterDateFrom}
            onChange={(event) => {
              setFilterDateFrom(event.target.value);
              restoreFeed();
            }}
            id="filter-date-from"
            title="From date"
          />

          <input
            type="date"
            className="filter-select filter-date"
            value={filterDateTo}
            onChange={(event) => {
              setFilterDateTo(event.target.value);
              restoreFeed();
            }}
            id="filter-date-to"
            title="To date"
          />

          <button className="btn btn-outline btn-sm" id="filter-clear-btn" onClick={handleClear}>
            Clear workspace
          </button>
        </div>

        <div className="active-filter-strip">
          <span className={`active-state ${isCleared ? "active-state-cleared" : ""}`}>
            {isCleared
              ? "Feed intentionally cleared"
              : hasAnyFilter
                ? "Filtered view active"
                : "Showing all classified events"}
          </span>

          {!isCleared && hasAnyFilter ? (
            <div className="active-tags">
              {filterPayer ? <span className="active-tag">Payer: {filterPayer}</span> : null}
              {filterServiceLine ? (
                <span className="active-tag">Service line: {filterServiceLine}</span>
              ) : null}
              {filterChangeType ? (
                <span className="active-tag">
                  Type: {CHANGE_TYPE_META[filterChangeType]?.label ?? filterChangeType}
                </span>
              ) : null}
              {filterDateFrom ? <span className="active-tag">From: {filterDateFrom}</span> : null}
              {filterDateTo ? <span className="active-tag">To: {filterDateTo}</span> : null}
            </div>
          ) : null}
        </div>
      </section>

      <section aria-label="Revenue Risk Charts">
        <RevenueRiskChart risk={displayRisk} />
      </section>

      <section className="feed-section">
        <div className="feed-header feed-header-stacked">
          <div>
            <p className="section-kicker">Live Feed</p>
            <h2 className="section-title">Classified policy changes</h2>
          </div>
          <p className="feed-supporting-copy">
            Every card summarizes payer, clinical impact, affected codes, confidence, and the
            fastest next action.
          </p>
        </div>

        {isCleared ? (
          <div className="cleared-state">
            <span className="cleared-icon">Search the queue</span>
            <p className="cleared-title">Feed cleared on purpose</p>
            <p className="cleared-hint">
              Select a payer, service line, change type, or date window above to rebuild the
              working set.
            </p>
          </div>
        ) : (
          <ChangeFeed events={deferredChanges} loading={loading} />
        )}
      </section>

      {status ? (
        <section className="status-panel">
          <div className="status-panel-header">
            <div>
              <p className="section-kicker">Pipeline Health</p>
              <h2 className="section-title">System status</h2>
            </div>
            <span className="status-badge">
              {status.pending_diffs > 0 ? "Attention required" : "Stable"}
            </span>
          </div>

          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Latest ingestion run</span>
              <span className="status-value">{status.latest_ingestion_run}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Latest change event</span>
              <span className="status-value">{status.latest_change_event}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Processed today</span>
              <span className="status-value">{status.processed_diffs_today}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Pending diffs</span>
              <span
                className={`status-value ${status.pending_diffs > 0 ? "status-alert" : "status-ok"}`}
              >
                {status.pending_diffs}
              </span>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
