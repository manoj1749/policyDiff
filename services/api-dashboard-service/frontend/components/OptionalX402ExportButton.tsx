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

  async function handleExport() {
    setState("loading");
    setMessage("");

    try {
      const response = await fetch(`${API_BASE}/api/changes/${eventId}/export-pdf`);

      if (response.status === 200) {
        const contentType = response.headers.get("content-type") ?? "";

        if (contentType.includes("application/pdf")) {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          setDownloadUrl(url);
          setState("success");

          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = `policydiff-${eventId}.pdf`;
          anchor.click();
          return;
        }

        const data = await response.json();
        if (data.status === "DISABLED") {
          setState("disabled");
          setMessage(data.message);
          return;
        }
      }

      if (response.status === 402) {
        const data = await response.json();
        setX402Info(data.x402 as Record<string, unknown>);
        setState("payment_required");
        return;
      }

      setState("error");
      setMessage(`Unexpected response: ${response.status}`);
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function handleMockPay() {
    setState("loading");
    try {
      const response = await fetch(`${API_BASE}/api/changes/${eventId}/export-pdf`, {
        headers: { "X-Payment": "mock-demo-payment-proof" },
      });

      if (response.headers.get("content-type")?.includes("application/pdf")) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);
        setState("success");

        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `policydiff-${eventId}.pdf`;
        anchor.click();
      } else {
        const data = await response.json();
        setState("error");
        setMessage(JSON.stringify(data));
      }
    } catch (err) {
      setState("error");
      setMessage(err instanceof Error ? err.message : "Unknown error");
    }
  }

  return (
    <div className="x402-section">
      {state === "idle" ? (
        <button className="btn btn-export" onClick={handleExport} id="export-pdf-btn">
          Export evidence as PDF
        </button>
      ) : null}

      {state === "loading" ? (
        <button className="btn btn-export btn-loading" disabled>
          Preparing export...
        </button>
      ) : null}

      {state === "disabled" ? (
        <div className="x402-notice">
          <span>PDF export is available but not enabled in this deployment.</span>
          <code className="x402-note">{message}</code>
        </div>
      ) : null}

      {state === "payment_required" && x402Info ? (
        <div className="x402-payment-panel">
          <h4 className="x402-title">x402 payment required</h4>
          <p className="x402-desc">
            Pay $2 USDC on Base Sepolia to export a polished PDF evidence packet.
          </p>
          <pre className="x402-payload">{JSON.stringify(x402Info, null, 2)}</pre>
          <div className="x402-actions">
            <button className="btn btn-pay" onClick={handleMockPay} id="mock-pay-btn">
              Demo mock payment and download
            </button>
            <span className="x402-note">Demo mode. No real payment processed.</span>
          </div>
        </div>
      ) : null}

      {state === "success" ? (
        <div className="x402-success">
          <span>PDF exported successfully.</span>
          {downloadUrl ? (
            <a href={downloadUrl} download={`policydiff-${eventId}.pdf`} className="btn btn-download">
              Download again
            </a>
          ) : null}
        </div>
      ) : null}

      {state === "error" ? (
        <div className="x402-error">
          <span>Export failed: {message}</span>
          <button className="btn btn-outline" onClick={() => setState("idle")}>
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}
