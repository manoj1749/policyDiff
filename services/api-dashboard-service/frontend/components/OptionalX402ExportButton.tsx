"use client";

import React, { useState } from "react";
import { API_BASE } from "@/lib/api";

interface OptionalX402ExportButtonProps {
  eventId: string;
}

type ExportState = "idle" | "loading" | "payment_required" | "success" | "error" | "disabled";

export default function OptionalX402ExportButton({ eventId }: OptionalX402ExportButtonProps) {
  const [state, setState] = useState<ExportState>("idle");
  const [message, setMessage] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [x402Info, setX402Info] = useState<Record<string, unknown> | null>(null);

  const handleExport = async () => {
    setState("loading");
    setMessage("");

    try {
      // First try without payment header
      const res = await fetch(`${API_BASE}/api/changes/${eventId}/export-pdf`);

      if (res.status === 200) {
        const ct = res.headers.get("content-type") ?? "";

        if (ct.includes("application/pdf")) {
          // Payment was accepted or x402 disabled — download the PDF
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          setDownloadUrl(url);
          setState("success");
          // Trigger browser download
          const a = document.createElement("a");
          a.href = url;
          a.download = `policydiff-${eventId}.pdf`;
          a.click();
          return;
        }

        // x402 is disabled — show message
        const data = await res.json();
        if (data.status === "DISABLED") {
          setState("disabled");
          setMessage(data.message);
          return;
        }
      }

      if (res.status === 402) {
        const data = await res.json();
        setX402Info(data.x402 as Record<string, unknown>);
        setState("payment_required");
        return;
      }

      setState("error");
      setMessage(`Unexpected response: ${res.status}`);
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : "Unknown error");
    }
  };

  // Simulate mock payment for hackathon demo
  const handleMockPay = async () => {
    setState("loading");
    try {
      const res = await fetch(`${API_BASE}/api/changes/${eventId}/export-pdf`, {
        headers: { "X-Payment": "mock-demo-payment-proof" },
      });
      if (res.headers.get("content-type")?.includes("application/pdf")) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);
        setState("success");
        const a = document.createElement("a");
        a.href = url;
        a.download = `policydiff-${eventId}.pdf`;
        a.click();
      } else {
        const data = await res.json();
        setState("error");
        setMessage(JSON.stringify(data));
      }
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : "Unknown error");
    }
  };

  return (
    <div className="x402-section">
      {state === "idle" && (
        <button className="btn btn-export" onClick={handleExport} id="export-pdf-btn">
          📥 Export Evidence as PDF
        </button>
      )}

      {state === "loading" && (
        <button className="btn btn-export btn-loading" disabled>
          ⏳ Preparing…
        </button>
      )}

      {state === "disabled" && (
        <div className="x402-notice">
          <span>🔒 PDF export is available but not enabled in this deployment.</span>
          <code className="x402-note">{message}</code>
        </div>
      )}

      {state === "payment_required" && x402Info && (
        <div className="x402-payment-panel">
          <h4 className="x402-title">💳 x402 Payment Required</h4>
          <p className="x402-desc">Pay $2 USDC on Base Sepolia to export a polished PDF evidence packet.</p>
          <pre className="x402-payload">{JSON.stringify(x402Info, null, 2)}</pre>
          <div className="x402-actions">
            <button className="btn btn-pay" onClick={handleMockPay} id="mock-pay-btn">
              🎭 Demo: Mock Payment & Download PDF
            </button>
            <span className="x402-note">Demo mode — no real payment processed</span>
          </div>
        </div>
      )}

      {state === "success" && (
        <div className="x402-success">
          <span>✅ PDF exported successfully!</span>
          {downloadUrl && (
            <a href={downloadUrl} download={`policydiff-${eventId}.pdf`} className="btn btn-download">
              ⬇ Download Again
            </a>
          )}
        </div>
      )}

      {state === "error" && (
        <div className="x402-error">
          <span>❌ Export failed: {message}</span>
          <button className="btn btn-outline" onClick={() => setState("idle")}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
