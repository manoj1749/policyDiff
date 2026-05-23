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
  eyebrow?: string;
}

function MetricCard({ label, value, sub, accent, eyebrow }: MetricCardProps) {
  return (
    <article className="metric-card" style={{ borderTop: `3px solid ${accent ?? "#3b82f6"}` }}>
      <div className="metric-card-top">
        <span className="metric-eyebrow">{eyebrow ?? "Metric"}</span>
      </div>
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
      {sub ? <span className="metric-sub">{sub}</span> : null}
    </article>
  );
}

export default function RiskSummaryCards({ risk, status, loading }: RiskSummaryCardsProps) {
  if (loading || !risk || !status) {
    return (
      <div className="metrics-grid">
        {[1, 2, 3, 4].map((item) => (
          <div key={item} className="metric-card skeleton-card metric-skeleton" />
        ))}
      </div>
    );
  }

  const tighteningCount =
    risk.by_change_type.find((item) => item.change_type === "TIGHTENING")?.count ?? 0;

  return (
    <div className="metrics-grid">
      <MetricCard
        label="Total Revenue at Risk"
        value={formatCurrency(risk.total_revenue_at_risk_usd)}
        sub="Annualized across the current change inventory"
        accent="#d97706"
        eyebrow="Financial"
      />
      <MetricCard
        label="Tightening Changes"
        value={tighteningCount}
        sub="Most likely to create denial pressure"
        accent="#dc2626"
        eyebrow="Utilization"
      />
      <MetricCard
        label="Published Evidence Briefs"
        value={status.senso_published_count}
        sub="Senso cited.md outputs available for review"
        accent="#0f766e"
        eyebrow="Evidence"
      />
      <MetricCard
        label="Pending Diffs"
        value={status.pending_diffs}
        sub={`Processed today: ${status.processed_diffs_today}`}
        accent="#2563eb"
        eyebrow="Queue"
      />
    </div>
  );
}
