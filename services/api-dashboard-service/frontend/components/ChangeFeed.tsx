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
  if (Number.isNaN(date.getTime())) return value;
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
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton-card feed-skeleton-card" />
        ))}
      </div>
    );
  }

  if (!events.length) {
    return (
      <div className="empty-feed">
        <p className="empty-title">No classified policy changes yet.</p>
        <p className="empty-hint">
          Run the demo trigger or wait for the next live ingestion cycle.
        </p>
      </div>
    );
  }

  return (
    <div className="changes-table">
      <div className="ct-head">
        <span className="ct-col-type">Type</span>
        <span className="ct-col-policy">Policy</span>
        <span className="ct-col-payer">Payer</span>
        <span className="ct-col-codes">CPT codes</span>
        <span className="ct-col-rev">Revenue at risk</span>
        <span className="ct-col-conf">Confidence</span>
        <span className="ct-col-date">Date</span>
        <span className="ct-col-action" />
      </div>

      {events.map((event) => {
        const meta = CHANGE_TYPE_META[event.change_type] ?? CHANGE_TYPE_META.STYLISTIC;

        return (
          <div
            key={event.event_id}
            className="ct-row"
            style={{ borderLeft: `3px solid ${meta.color}` }}
          >
            <div className="ct-col-type">
              <span className="change-tag">
                <span className="change-dot" style={{ background: meta.color }} />
                <span className="change-label" style={{ color: meta.color }}>{meta.label}</span>
              </span>
            </div>

            <div className="ct-col-policy">
              <span className="ct-title">{event.policy_title}</span>
              <span className="ct-summary">{event.change_summary}</span>
            </div>

            <div className="ct-col-payer">
              <span className="payer-chip">{event.payer}</span>
              <span className="service-line-chip">{event.service_line}</span>
            </div>

            <div className="ct-col-codes">
              {event.cpt_codes_affected.slice(0, 3).map((code) => (
                <span key={code} className="code-chip">{code}</span>
              ))}
              {event.cpt_codes_affected.length > 3 && (
                <span className="code-more">+{event.cpt_codes_affected.length - 3}</span>
              )}
            </div>

            <div className="ct-col-rev">
              <span className="rev-amount">{formatCurrency(event.revenue_at_risk_usd)}</span>
            </div>

            <div className="ct-col-conf">
              <span className="conf-value">{(event.confidence * 100).toFixed(0)}%</span>
            </div>

            <div className="ct-col-date">
              <span className="ct-date">{formatTimestamp(event.created_at)}</span>
            </div>

            <div className="ct-col-action">
              {event.cited_md_url && (
                <a
                  href={event.cited_md_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="row-link"
                  title="Open Senso brief"
                >
                  Brief
                </a>
              )}
              <Link href={`/changes/${event.event_id}`} className="row-link row-link-primary">
                Review →
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
}
