/**
 * app/page.tsx — PolicyDiff Home Dashboard
 *
 * Filter behaviours:
 *  - Default: show all events
 *  - After Clear: show nothing (isCleared=true) until a filter is explicitly set
 *  - Any filter selection restores the feed for that subset
 *  - Date range filter works alongside payer/type filters
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

const LS_KEY = "policydiff_feed_cleared";

export default function HomePage() {
  const [allChanges, setAllChanges] = useState<ChangeEventSummary[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [demoMessage, setDemoMessage] = useState("");
  const [demoLoading, setDemoLoading] = useState(false);

  // Filters
  const [filterChangeType, setFilterChangeType] = useState("");
  const [filterPayer, setFilterPayer] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");

  /**
   * clearKey: incrementing this forces date <input type="date"> elements to
   * remount, which is the only reliable way to visually reset them in all browsers.
   */
  const [clearKey, setClearKey] = useState(0);

  /**
   * isCleared: persisted in localStorage so page reloads respect the cleared state.
   * true  → feed blank until a filter is explicitly selected
   * false → feed shows all / filtered events
   */
  const [isCleared, setIsCleared] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(LS_KEY) === "true";
  });

  // Sync isCleared → localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem(LS_KEY, String(isCleared));
  }, [isCleared]);

  const hasAnyFilter =
    !!filterChangeType || !!filterPayer || !!filterDateFrom || !!filterDateTo;

  // Derived: apply all active filters synchronously
  const filteredChanges: ChangeEventSummary[] = isCleared
    ? []
    : allChanges.filter((e) => {
        if (filterChangeType && e.change_type !== filterChangeType) return false;
        if (filterPayer && e.payer !== filterPayer) return false;
        if (filterDateFrom) {
          const from = new Date(filterDateFrom).getTime();
          const ts = new Date(e.created_at).getTime();
          if (ts < from) return false;
        }
        if (filterDateTo) {
          // include the full "to" day by going to end of day
          const to = new Date(filterDateTo + "T23:59:59").getTime();
          const ts = new Date(e.created_at).getTime();
          if (ts > to) return false;
        }
        return true;
      });

  const refresh = useCallback(async () => {
    try {
      const [c, r, s] = await Promise.all([
        fetchChanges({ limit: 50 }),
        fetchRiskSummary(),
        fetchSystemStatus(),
      ]);
      setAllChanges(c);
      setRisk(r);
      setStatus(s);
      setLastRefresh(new Date());
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

  // Clear: hide everything + reset all inputs visually + persist across reloads
  const handleClear = () => {
    setFilterChangeType("");
    setFilterPayer("");
    setFilterDateFrom("");
    setFilterDateTo("");
    setIsCleared(true);
    setClearKey((k) => k + 1); // forces date inputs to remount and visually reset
  };

  // Any filter change un-clears the feed
  const handleChangeType = (v: string) => {
    setFilterChangeType(v);
    setIsCleared(false);
  };
  const handlePayer = (v: string) => {
    setFilterPayer(v);
    setIsCleared(false);
  };
  const handleDateFrom = (v: string) => {
    setFilterDateFrom(v);
    setIsCleared(false);
  };
  const handleDateTo = (v: string) => {
    setFilterDateTo(v);
    setIsCleared(false);
  };

  const handleTriggerDemo = async () => {
    setDemoLoading(true);
    setDemoMessage("");
    try {
      const res = await triggerDemo();
      setDemoMessage(res.message);
      // Restore feed (clear the cleared state) so new event is visible
      setIsCleared(false);
      setTimeout(refresh, 3000);
    } catch {
      setDemoMessage("Demo trigger failed — check that the backend is running.");
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="page-root">
      {/* Header */}
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
            {demoLoading ? "⏳ Simulating…" : "⚡ Trigger Demo"}
          </button>
        </div>
      </header>

      {demoMessage && (
        <div className="demo-notice">✅ {demoMessage}</div>
      )}

      {/* Metric Cards */}
      <section aria-label="Risk Summary Metrics">
        <RiskSummaryCards risk={risk} status={status} loading={loading} />
      </section>

      {/* Charts */}
      <section aria-label="Revenue Risk Charts">
        <RevenueRiskChart risk={risk} />
      </section>

      {/* Change Feed */}
      <section className="feed-section">
        <div className="feed-header">
          <h2 className="section-title">Live Change Feed</h2>

          <div className="filter-bar">
            {/* Change type */}
            <select
              className="filter-select"
              value={filterChangeType}
              onChange={(e) => handleChangeType(e.target.value)}
              id="filter-change-type"
            >
              <option value="">All Types</option>
              <option value="TIGHTENING">Tightening</option>
              <option value="LOOSENING">Loosening</option>
              <option value="SCOPE_CHANGE">Scope Change</option>
              <option value="STYLISTIC">Stylistic</option>
            </select>

            {/* Payer */}
            <select
              className="filter-select"
              value={filterPayer}
              onChange={(e) => handlePayer(e.target.value)}
              id="filter-payer"
            >
              <option value="">All Payers</option>
              <option value="UHC">UHC</option>
              <option value="Aetna">Aetna</option>
              <option value="Cigna">Cigna</option>
              <option value="Humana">Humana</option>
            </select>

            {/* Date from */}
            <input
              key={`date-from-${clearKey}`}
              type="date"
              className="filter-select filter-date"
              value={filterDateFrom}
              onChange={(e) => handleDateFrom(e.target.value)}
              id="filter-date-from"
              title="From date"
            />

            {/* Date to */}
            <input
              key={`date-to-${clearKey}`}
              type="date"
              className="filter-select filter-date"
              value={filterDateTo}
              onChange={(e) => handleDateTo(e.target.value)}
              id="filter-date-to"
              title="To date"
            />

            <button
              className="btn btn-outline btn-sm"
              id="filter-clear-btn"
              onClick={handleClear}
            >
              Clear
            </button>
          </div>
        </div>

        {/* Cleared state: prompt user to pick a filter */}
        {isCleared ? (
          <div className="cleared-state">
            <span className="cleared-icon">🔍</span>
            <p className="cleared-title">Feed cleared</p>
            <p className="cleared-hint">
              Select a payer, change type, or date range above to explore past changes.
            </p>
          </div>
        ) : (
          <ChangeFeed events={filteredChanges} loading={loading} />
        )}
      </section>

      {/* System Status */}
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
