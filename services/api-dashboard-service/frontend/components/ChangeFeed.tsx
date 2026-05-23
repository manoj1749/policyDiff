"use client";

import React from "react";
import type { ChangeEventSummary } from "@/lib/api";
import { CHANGE_TYPE_META, formatCurrency } from "@/lib/api";
import Link from "next/link";

interface ChangeFeedProps {
  events: ChangeEventSummary[];
  loading?: boolean;
}

export default function ChangeFeed({ events, loading }: ChangeFeedProps) {
  if (loading) {
    return (
      <div className="feed-skeleton">
        {[1, 2, 3].map((i) => (
          <div key={i} className="skeleton-card" />
        ))}
      </div>
    );
  }

  if (!events.length) {
    return (
      <div className="empty-feed">
        <span className="empty-icon">📭</span>
        <p>No policy changes detected yet.</p>
        <p className="empty-hint">Use the "Trigger Demo" button to seed a sample event.</p>
      </div>
    );
  }

  return (
    <div className="change-feed">
      {events.map((event) => {
        const meta = CHANGE_TYPE_META[event.change_type] ?? CHANGE_TYPE_META.STYLISTIC;
        return (
          <div
            key={event.event_id}
            className="change-card"
            style={{
              borderLeft: `4px solid ${meta.color}`,
            }}
          >
            {/* Header row */}
            <div className="card-header">
              <div className="card-header-left">
                <span
                  className="badge"
                  style={{
                    color: meta.color,
                    background: meta.bg,
                    border: `1px solid ${meta.border}`,
                  }}
                >
                  {meta.label}
                </span>
                <span className="payer-chip">{event.payer}</span>
                <span className="service-line-chip">{event.service_line}</span>
              </div>
              <span className="card-ts">{event.created_at}</span>
            </div>

            {/* Title */}
            <h3 className="card-title">{event.policy_title}</h3>

            {/* Summary */}
            <p className="card-summary">{event.change_summary}</p>

            {/* Footer row */}
            <div className="card-footer">
              <div className="card-meta-row">
                {/* Revenue at risk */}
                <div className="meta-item">
                  <span className="meta-label">Revenue at Risk</span>
                  <span
                    className="meta-value"
                    style={{ color: event.revenue_at_risk_usd > 0 ? "#ef4444" : "#9ca3af" }}
                  >
                    {formatCurrency(event.revenue_at_risk_usd)}
                  </span>
                </div>

                {/* CPT codes */}
                {event.cpt_codes_affected.length > 0 && (
                  <div className="meta-item">
                    <span className="meta-label">CPT Codes</span>
                    <span className="meta-value cpt-codes">
                      {event.cpt_codes_affected.join(", ")}
                    </span>
                  </div>
                )}

                {/* Confidence */}
                <div className="meta-item">
                  <span className="meta-label">Confidence</span>
                  <span className="meta-value">
                    {(event.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="card-actions">
                {event.cited_md_url && (
                  <a
                    href={event.cited_md_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-senso"
                    title="Open Senso cited.md evidence brief"
                  >
                    📄 Senso Brief
                  </a>
                )}
                <Link
                  href={`/changes/${event.event_id}`}
                  className="btn btn-details"
                >
                  View Details →
                </Link>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
