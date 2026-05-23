"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
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

  async function handleRouteAlert() {
    setRouteLoading(true);
    setRouteMsg("");

    try {
      const response = await routeAlert(eventId);
      setRouteMsg(`${response.status}: ${response.message} -> ${response.routed_to}`);
    } catch {
      setRouteMsg("Routing failed. Check ENABLE_LUMINAI and LUMINAI_WEBHOOK_URL.");
    } finally {
      setRouteLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="page-root">
        <div className="detail-loading">
          <div className="spinner" />
          <p>Loading event details...</p>
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
          <Link href="/" className="btn btn-outline">
            Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-root detail-page">
      <nav className="breadcrumb">
        <Link href="/" className="breadcrumb-link">
          Dashboard
        </Link>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">Change Detail</span>
      </nav>

      <EvidencePanel event={event} />

      <section className="detail-section">
        <h2 className="section-heading">Senso Evidence Brief</h2>
        <SensoMarkdownLink citedMdUrl={event.cited_md_url} eventId={eventId} showViewerLink />
      </section>

      <section className="detail-section">
        <h2 className="section-heading">Export Evidence Packet</h2>
        <p className="section-body">
          Export a polished PDF evidence brief for this policy change. Optional x402 payment may
          apply.
        </p>
        <OptionalX402ExportButton eventId={eventId} />
      </section>

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
          {routeLoading ? "Routing..." : "Route alert"}
        </button>
        {routeMsg ? <p className="route-result">{routeMsg}</p> : null}
      </section>
    </div>
  );
}
