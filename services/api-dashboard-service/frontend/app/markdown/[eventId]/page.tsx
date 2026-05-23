/**
 * app/markdown/[eventId]/page.tsx — Senso Markdown Viewer
 *
 * Route: /markdown/[eventId]
 *
 * Displays either:
 *  1. The stored `cited_markdown` from ClickHouse (via the detail API), or
 *  2. A prominent link to `cited_md_url` if only the URL is available.
 *
 * The page makes it obvious that Senso generated a public citeable artifact.
 */

"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchChangeDetail, type ChangeEventDetail } from "@/lib/api";

export default function MarkdownViewerPage() {
  const params = useParams();
  const eventId = params?.eventId as string;

  const [event, setEvent] = useState<ChangeEventDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!eventId) return;
    fetchChangeDetail(eventId)
      .then(setEvent)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  if (loading) {
    return (
      <div className="page-root">
        <div className="detail-loading">
          <div className="spinner" />
          <p>Loading markdown evidence brief…</p>
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="page-root">
        <div className="detail-error">
          <h2>Evidence brief not found</h2>
          <p>{error || "This event ID does not exist."}</p>
          <Link href="/" className="btn btn-outline">← Back to Dashboard</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-root markdown-page">
      {/* Nav */}
      <nav className="breadcrumb">
        <Link href="/" className="breadcrumb-link">← Dashboard</Link>
        <span className="breadcrumb-sep">/</span>
        <Link href={`/changes/${eventId}`} className="breadcrumb-link">Change Detail</Link>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">Evidence Brief</span>
      </nav>

      {/* Senso provenance badge */}
      <div className="senso-provenance">
        <div className="senso-provenance-header">
          <span className="senso-icon-lg">📄</span>
          <div>
            <h1 className="senso-provenance-title">
              Senso / cited.md Evidence Brief
            </h1>
            <p className="senso-provenance-sub">
              AI-generated, source-grounded policy change intelligence — published publicly on cited.md
            </p>
          </div>
          <span className="senso-ai-badge">✨ AI-Generated</span>
        </div>

        {event.cited_md_url && (
          <a
            href={event.cited_md_url}
            target="_blank"
            rel="noopener noreferrer"
            className="senso-canonical-link"
          >
            ↗ Open canonical brief on cited.md: {event.cited_md_url}
          </a>
        )}
      </div>

      {/* Markdown content — stored or link-only */}
      {event.cited_markdown ? (
        <div className="markdown-viewer">
          <div className="markdown-header">
            <span className="markdown-source-tag">Stored in ClickHouse · {event.payer} · {event.policy_title}</span>
          </div>
          <pre className="markdown-body">{event.cited_markdown}</pre>
        </div>
      ) : event.cited_md_url ? (
        <div className="markdown-link-only">
          <div className="markdown-link-icon">🔗</div>
          <h2>Evidence brief available on cited.md</h2>
          <p>
            The full markdown brief for this policy change was published to cited.md.
            Click below to view it.
          </p>
          <a
            href={event.cited_md_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-senso btn-xl"
          >
            ↗ Open Evidence Brief on cited.md
          </a>
          <code className="senso-url">{event.cited_md_url}</code>
        </div>
      ) : (
        <div className="markdown-not-published">
          <p>
            No evidence brief has been published yet for this change event.
            Senso publishing happens automatically after Gemini classification completes.
          </p>
          <Link href={`/changes/${eventId}`} className="btn btn-outline">
            ← Back to Change Detail
          </Link>
        </div>
      )}
    </div>
  );
}
