"use client";

import React from "react";
import type { ChangeEventDetail } from "@/lib/api";
import { formatCurrency, CHANGE_TYPE_META } from "@/lib/api";

interface EvidencePanelProps {
  event: ChangeEventDetail;
}

export default function EvidencePanel({ event }: EvidencePanelProps) {
  const meta = CHANGE_TYPE_META[event.change_type] ?? CHANGE_TYPE_META.STYLISTIC;

  return (
    <div className="evidence-panel">
      {/* Header */}
      <div className="evidence-header">
        <div className="evidence-header-left">
          <span
            className="badge badge-lg"
            style={{
              color: meta.color,
              background: meta.bg,
              border: `1px solid ${meta.border}`,
            }}
          >
            {meta.label}
          </span>
          <span className="payer-chip payer-chip-lg">{event.payer}</span>
          <span className="service-line-chip">{event.service_line}</span>
        </div>
        <span className="confidence-badge">
          {(event.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      {/* Policy info */}
      <h1 className="evidence-title">{event.policy_title}</h1>
      {event.url && (
        <a href={event.url} target="_blank" rel="noopener noreferrer" className="policy-url">
          ↗ View Original Policy
        </a>
      )}

      {/* Key metrics */}
      <div className="evidence-metrics">
        <div className="ev-metric">
          <span className="ev-metric-label">Revenue at Risk</span>
          <span className="ev-metric-value" style={{ color: "#ef4444" }}>
            {formatCurrency(event.revenue_at_risk_usd)}
          </span>
        </div>
        <div className="ev-metric">
          <span className="ev-metric-label">Affected CPT Codes</span>
          <span className="ev-metric-value cpt-codes">
            {event.cpt_codes_affected.join(", ") || "None"}
          </span>
        </div>
      </div>

      {/* Changed clause */}
      <section className="evidence-section">
        <h2 className="section-heading">Changed Clause</h2>
        <blockquote className="changed-clause">
          {event.changed_clause || "Not available"}
        </blockquote>
      </section>

      {/* Change summary */}
      <section className="evidence-section">
        <h2 className="section-heading">Change Summary</h2>
        <p className="section-body">{event.change_summary}</p>
      </section>

      {/* Clinical impact */}
      <section className="evidence-section">
        <h2 className="section-heading">Clinical Impact</h2>
        <p className="section-body">{event.clinical_impact}</p>
      </section>

      {/* Recommended action */}
      <section className="evidence-section action-section">
        <h2 className="section-heading">⚡ Recommended Action</h2>
        <p className="section-body action-body">{event.recommended_action}</p>
      </section>
    </div>
  );
}
