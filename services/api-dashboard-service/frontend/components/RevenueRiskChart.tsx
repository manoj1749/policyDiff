"use client";

/**
 * RevenueRiskChart.tsx
 *
 * Renders two horizontal bar charts:
 *   1. Revenue at risk by service line
 *   2. Revenue at risk by change type
 *
 * Uses only SVG + CSS — no external charting library required.
 */

import React from "react";
import type { RiskSummary } from "@/lib/api";
import { formatCurrency, CHANGE_TYPE_META } from "@/lib/api";

interface Props {
  risk: RiskSummary | null;
}

interface BarChartProps {
  title: string;
  data: { label: string; value: number; color: string }[];
}

function HorizontalBarChart({ title, data }: BarChartProps) {
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="chart-card">
      <h3 className="chart-title">{title}</h3>
      <div className="bar-chart">
        {data.map((item) => {
          const pct = (item.value / max) * 100;
          return (
            <div key={item.label} className="bar-row">
              <span className="bar-label">{item.label}</span>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{
                    width: `${pct}%`,
                    background: item.color,
                  }}
                />
              </div>
              <span className="bar-value">{formatCurrency(item.value)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const SERVICE_LINE_COLORS: Record<string, string> = {
  Cardiology: "#6366f1",
  Radiology: "#06b6d4",
  Orthopedics: "#8b5cf6",
  Neurology: "#ec4899",
  Oncology: "#f59e0b",
};

export default function RevenueRiskChart({ risk }: Props) {
  if (!risk) {
    return (
      <div className="charts-grid">
        <div className="chart-card skeleton-card" style={{ height: 220 }} />
        <div className="chart-card skeleton-card" style={{ height: 220 }} />
      </div>
    );
  }

  const byServiceLine = risk.by_service_line.map((item) => ({
    label: item.service_line,
    value: item.revenue_at_risk_usd,
    color: SERVICE_LINE_COLORS[item.service_line] ?? "#6366f1",
  }));

  const byChangeType = risk.by_change_type.map((item) => ({
    label: CHANGE_TYPE_META[item.change_type]?.label ?? item.change_type,
    value: item.revenue_at_risk_usd,
    color: CHANGE_TYPE_META[item.change_type]?.color ?? "#6b7280",
  }));

  return (
    <div className="charts-grid">
      <HorizontalBarChart title="Revenue at Risk by Service Line" data={byServiceLine} />
      <HorizontalBarChart title="Revenue at Risk by Change Type" data={byChangeType} />
    </div>
  );
}
