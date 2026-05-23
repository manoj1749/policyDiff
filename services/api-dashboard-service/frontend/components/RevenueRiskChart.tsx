"use client";

import React from "react";
import type { RiskSummary } from "@/lib/api";
import { CHANGE_TYPE_META, formatCurrency } from "@/lib/api";

interface Props {
  risk: RiskSummary | null;
}

interface ChartDatum {
  label: string;
  value: number;
  color: string;
}

interface BarChartProps {
  title: string;
  subtitle: string;
  data: ChartDatum[];
}

function HorizontalBarChart({ title, subtitle, data }: BarChartProps) {
  const max = Math.max(...data.map((item) => item.value), 1);

  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <h3 className="chart-title">{title}</h3>
        <p className="chart-subtitle">{subtitle}</p>
      </div>

      <div className="bar-chart">
        {data.map((item) => {
          const pct = (item.value / max) * 100;

          return (
            <div key={item.label} className="bar-row">
              <div className="bar-copy">
                <span className="bar-label">{item.label}</span>
                <span className="bar-detail">{formatCurrency(item.value)}</span>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${pct}%`, background: item.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </article>
  );
}

const SERVICE_LINE_COLORS: Record<string, string> = {
  Cardiology: "#b45309",
  Radiology: "#0f766e",
  Orthopedics: "#1d4ed8",
  Neurology: "#7c3aed",
  Oncology: "#dc2626",
};

const PAYER_COLORS: string[] = ["#1d4ed8", "#b45309", "#0f766e", "#7c2d12", "#334155"];

export default function RevenueRiskChart({ risk }: Props) {
  if (!risk) {
    return (
      <div className="charts-grid-three">
        {[1, 2, 3].map((item) => (
          <div key={item} className="chart-card skeleton-card chart-skeleton" />
        ))}
      </div>
    );
  }

  const byServiceLine = risk.by_service_line.map((item) => ({
    label: item.service_line,
    value: item.revenue_at_risk_usd,
    color: SERVICE_LINE_COLORS[item.service_line] ?? "#334155",
  }));

  const byChangeType = risk.by_change_type.map((item) => ({
    label: CHANGE_TYPE_META[item.change_type]?.label ?? item.change_type,
    value: item.revenue_at_risk_usd,
    color: CHANGE_TYPE_META[item.change_type]?.color ?? "#64748b",
  }));

  const byPayer = risk.by_payer.map((item, index) => ({
    label: item.payer,
    value: item.revenue_at_risk_usd,
    color: PAYER_COLORS[index % PAYER_COLORS.length],
  }));

  return (
    <div className="charts-grid-three">
      <HorizontalBarChart
        title="Revenue by Service Line"
        subtitle="Where policy movement concentrates operational exposure"
        data={byServiceLine}
      />
      <HorizontalBarChart
        title="Revenue by Change Type"
        subtitle="How much risk is tied to tightening versus other movement"
        data={byChangeType}
      />
      <HorizontalBarChart
        title="Revenue by Payer"
        subtitle="Which contracts are driving the highest downstream impact"
        data={byPayer}
      />
    </div>
  );
}
