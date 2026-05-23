/**
 * app/page.tsx — PolicyDiff Home Dashboard
 *
 * Auto-refreshes every NEXT_PUBLIC_REFRESH_INTERVAL_SECONDS (default 10s).
 * Shows metric cards, revenue charts, and the live change feed.
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  fetchChanges,
  fetchRiskSummary,
  fetchSystemStatus,
  triggerDemo,
  REFRESH_INTERVAL_MS,
  type ChangeEventSummary,
  type RiskSummary,
  type SystemStatus,
} from "@/lib/api";
import RiskSummaryCards from "@/components/RiskSummaryCards";
import RevenueRiskChart from "@/components/RevenueRiskChart";
import ChangeFeed from "@/components/ChangeFeed";

export default function HomePage() {
  const [changes, setChanges] = useState<ChangeEventSummary[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [demoMessage, setDemoMessage] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);
  const [filterChangeType, setFilterChangeType] = useState("");
  const [filterPayer, setFilterPayer] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [c, r, s] = await Promise.all([
        fetchChanges({ limit: 50, change_type: filterChangeType || undefined, payer: filterPayer || undefined }),
        fetchRiskSummary(),
        fetchSystemStatus(),
      ]);
      setChanges(c);
      setRisk(r);
      setStatus(s);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setLoading(false);
    }
  }, [filterChangeType, filterPayer]);

  // Initial load + interval
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const handleTriggerDemo = async () => {
    setDemoLoading(true);
    setDemoMessage("");
    try {
      const res = await triggerDemo();
      setDemoMessage(res.message);
      setTimeout(refresh, 3000);
    } catch (err) {
      setDemoMessage("Demo trigger failed — check that ClickHouse is running.");
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="page-root">
      {/* ── Header ── */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo-mark">PD</div>
          <div>
            <h1 className="dashboard-title">PolicyDiff</h1>
            <p className="dashboard-subtitle">Payer Policy Change Monitor</p>
          </div>
        </div>

        <div className="header-right">
          {lastRefresh && (
            <span className="refresh-ts">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          {status?.datadog_enabled && (
            <span className="datadog-badge">🐶 Datadog</span>
          )}
          <button
            className="btn btn-demo"
            onClick={handleTriggerDemo}
            disabled={demoLoading}
            id="trigger-demo-btn"
          >
            {demoLoading ? "⏳ Triggering…" : "⚡ Trigger Demo"}
          </button>
        </div>
      </header>

      {demoMessage && (
        <div className="demo-notice">
          ✅ {demoMessage}
        </div>
      )}

      {/* ── Metric Cards ── */}
      <section aria-label="Risk Summary Metrics">
        <RiskSummaryCards risk={risk} status={status} loading={loading} />
      </section>

      {/* ── Charts ── */}
      <section aria-label="Revenue Risk Charts">
        <RevenueRiskChart risk={risk} />
      </section>

      {/* ── Change Feed ── */}
      <section className="feed-section">
        <div className="feed-header">
          <h2 className="section-title">Live Change Feed</h2>

          {/* Filters */}
          <div className="filter-bar">
            <select
              className="filter-select"
              value={filterChangeType}
              onChange={(e) => setFilterChangeType(e.target.value)}
              id="filter-change-type"
            >
              <option value="">All Types</option>
              <option value="TIGHTENING">Tightening</option>
              <option value="LOOSENING">Loosening</option>
              <option value="SCOPE_CHANGE">Scope Change</option>
              <option value="STYLISTIC">Stylistic</option>
            </select>

            <select
              className="filter-select"
              value={filterPayer}
              onChange={(e) => setFilterPayer(e.target.value)}
              id="filter-payer"
            >
              <option value="">All Payers</option>
              <option value="UHC">UHC</option>
              <option value="Aetna">Aetna</option>
              <option value="Cigna">Cigna</option>
              <option value="Humana">Humana</option>
            </select>

            <button
              className="btn btn-outline btn-sm"
              onClick={() => { setFilterChangeType(""); setFilterPayer(""); }}
            >
              Clear
            </button>
          </div>
        </div>

        <ChangeFeed events={changes} loading={loading} />
      </section>

      {/* ── System Status Panel ── */}
      {status && (
        <section className="status-panel">
          <h2 className="section-title">System Status</h2>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Latest Ingestion</span>
              <span className="status-value">{status.latest_ingestion_run}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Latest Change Event</span>
              <span className="status-value">{status.latest_change_event}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Processed Today</span>
              <span className="status-value">{status.processed_diffs_today}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Pending Diffs</span>
              <span
                className="status-value"
                style={{ color: status.pending_diffs > 0 ? "#f59e0b" : "#22c55e" }}
              >
                {status.pending_diffs}
              </span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
