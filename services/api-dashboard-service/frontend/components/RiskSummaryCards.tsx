"use client";

import React from "react";
import type { RiskSummary, SystemStatus } from "@/lib/api";
import { formatCurrency } from "@/lib/api";

interface RiskSummaryCardsProps {
  risk: RiskSummary | null;
  status: SystemStatus | null;
  loading?: boolean;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
  icon?: string;
}

function MetricCard({ label, value, sub, accent, icon }: MetricCardProps) {
  return (
    <div className="metric-card" style={{ borderTop: `3px solid ${accent ?? "#6366f1"}` }}>
      {icon && <span className="metric-icon">{icon}</span>}
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  );
}

export default function RiskSummaryCards({ risk, status, loading }: RiskSummaryCardsProps) {
  // Only show skeletons while actively loading — not when intentionally cleared (risk=ZERO_RISK)
  if (loading) {
    return (
      <div className="metrics-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="metric-card skeleton-card" />
        ))}
      </div>
    );
  }

  const tighteningCount =
    risk?.by_change_type?.find((c) => c.change_type === "TIGHTENING")?.count ?? 0;

  return (
    <div className="metrics-grid">
      <MetricCard
        label="Total Revenue at Risk"
        value={formatCurrency(risk?.total_revenue_at_risk_usd ?? 0)}
        sub="Annualized across all changes"
        accent="#ef4444"
        icon="💰"
      />
      <MetricCard
        label="Tightening Changes"
        value={tighteningCount}
        sub="High-risk coverage restrictions"
        accent="#f59e0b"
        icon="⚠️"
      />
      <MetricCard
        label="Senso Briefs Published"
        value={status?.senso_published_count ?? 0}
        sub="cited.md evidence documents"
        accent="#8b5cf6"
        icon="📄"
      />
      <MetricCard
        label="Pending Diffs"
        value={status?.pending_diffs ?? 0}
        sub={`Processed today: ${status?.processed_diffs_today ?? 0}`}
        accent="#06b6d4"
        icon="🔄"
      />
    </div>
  );
}
