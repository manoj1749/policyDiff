/**
 * app/changes/[eventId]/page.tsx — Change Detail Page
 *
 * Route: /changes/[eventId]
 * Shows full evidence: payer, policy, change type, changed clause,
 * CPT codes, clinical impact, revenue risk, Senso link, x402 export,
 * and optional Luminai alert routing.
 */

"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchChangeDetail, routeAlert, type ChangeEventDetail } from "@/lib/api";
import EvidencePanel from "@/components/EvidencePanel";
import SensoMarkdownLink from "@/components/SensoMarkdownLink";
import OptionalX402ExportButton from "@/components/OptionalX402ExportButton";

export default function ChangeDetailPage() {
  const params = useParams();
  const eventId = params?.eventId as string;

  const [event, setEvent] = useState<ChangeEventDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [routeMsg, setRouteMsg] = useState("");
  const [routeLoading, setRouteLoading] = useState(false);

  useEffect(() => {
    if (!eventId) return;
    fetchChangeDetail(eventId)
      .then(setEvent)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  const handleRouteAlert = async () => {
    setRouteLoading(true);
    setRouteMsg("");
    try {
      const res = await routeAlert(eventId);
      setRouteMsg(`${res.status}: ${res.message} → ${res.routed_to}`);
    } catch (err) {
      setRouteMsg("Routing failed — check ENABLE_LUMINAI and LUMINAI_WEBHOOK_URL.");
    } finally {
      setRouteLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="page-root">
        <div className="detail-loading">
          <div className="spinner" />
          <p>Loading event details…</p>
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="page-root">
        <div className="detail-error">
          <h2>Event not found</h2>
          <p>{error || "This event ID does not exist."}</p>
          <Link href="/" className="btn btn-outline">← Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-root detail-page">
      {/* Back nav */}
      <nav className="breadcrumb">
        <Link href="/" className="breadcrumb-link">← Dashboard</Link>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">Change Detail</span>
      </nav>

      {/* Evidence Panel */}
      <EvidencePanel event={event} />

      {/* Senso / cited.md link section */}
      <section className="detail-section">
        <h2 className="section-heading">Senso Evidence Brief</h2>
        <SensoMarkdownLink
          citedMdUrl={event.cited_md_url}
          eventId={eventId}
          showViewerLink
        />
      </section>

      {/* Optional x402 export */}
      <section className="detail-section">
        <h2 className="section-heading">Export Evidence Packet</h2>
        <p className="section-body">
          Export a polished PDF evidence brief for this policy change.
          Optional x402 payment may apply.
        </p>
        <OptionalX402ExportButton eventId={eventId} />
      </section>

      {/* Optional Luminai routing */}
      <section className="detail-section">
        <h2 className="section-heading">Route Alert to Workflow Team</h2>
        <p className="section-body">
          Send this policy change alert to the affected service-line workflow queue via Luminai.
        </p>
        <button
          className="btn btn-route"
          onClick={handleRouteAlert}
          disabled={routeLoading}
          id="route-alert-btn"
        >
          {routeLoading ? "⏳ Routing…" : "📤 Route Alert"}
        </button>
        {routeMsg && <p className="route-result">{routeMsg}</p>}
      </section>
    </div>
  );
}
