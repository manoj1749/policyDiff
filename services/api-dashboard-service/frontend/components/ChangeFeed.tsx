"use client";

import React from "react";
import Link from "next/link";
import type { ChangeEventSummary } from "@/lib/api";
import { CHANGE_TYPE_META, formatCurrency } from "@/lib/api";

interface ChangeFeedProps {
  events: ChangeEventSummary[];
  loading?: boolean;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export default function ChangeFeed({ events, loading }: ChangeFeedProps) {
  if (loading) {
    return (
      <div className="feed-skeleton">
        {[1, 2, 3].map((item) => (
          <div key={item} className="skeleton-card feed-skeleton-card" />
        ))}
      </div>
    );
  }

  if (!events.length) {
    return (
      <div className="empty-feed">
        <p className="empty-title">No classified policy changes yet.</p>
        <p className="empty-hint">
          Run the demo trigger or wait for the next live ingestion cycle to populate this queue.
        </p>
      </div>
    );
  }

  return (
    <div className="change-feed">
      {events.map((event) => {
        const meta = CHANGE_TYPE_META[event.change_type] ?? CHANGE_TYPE_META.STYLISTIC;

        return (
          <article
            key={event.event_id}
            className="change-card"
            style={{ borderLeft: `4px solid ${meta.color}` }}
          >
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
                <span className="status-chip">{event.status}</span>
              </div>
              <span className="card-ts">{formatTimestamp(event.created_at)}</span>
            </div>

            <div className="card-body">
              <div className="card-main">
                <h3 className="card-title">{event.policy_title}</h3>
                <p className="card-summary">{event.change_summary}</p>
                <p className="card-copy">{event.clinical_impact}</p>

                {event.cpt_codes_affected.length ? (
                  <div className="card-codes">
                    <span className="meta-label">Affected CPT codes</span>
                    <div className="code-chip-row">
                      {event.cpt_codes_affected.map((code) => (
                        <span key={code} className="code-chip">
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <aside className="card-rail">
                <div className="rail-metric">
                  <span className="meta-label">Revenue at risk</span>
                  <span className="rail-value rail-value-risk">
                    {formatCurrency(event.revenue_at_risk_usd)}
                  </span>
                </div>
                <div className="rail-metric">
                  <span className="meta-label">Confidence</span>
                  <span className="rail-value">{(event.confidence * 100).toFixed(0)}%</span>
                </div>
              </aside>
            </div>

            <div className="card-footer">
              <div className="card-actions">
                {event.cited_md_url ? (
                  <a
                    href={event.cited_md_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-senso"
                    title="Open Senso cited.md evidence brief"
                  >
                    Open Senso brief
                  </a>
                ) : null}
                <Link href={`/changes/${event.event_id}`} className="btn btn-details">
                  Review evidence
                </Link>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
