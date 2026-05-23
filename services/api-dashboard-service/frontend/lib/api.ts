/**
 * lib/api.ts — typed API client for the PolicyDiff dashboard.
 *
 * In production (Vercel) API_BASE is "" so all calls go to /api/... which
 * next.config.js rewrites to the Railway backend — no CORS needed.
 * In local dev, calls hit localhost:8003 directly via the rewrite too.
 */

export const API_BASE = "";
export const REFRESH_INTERVAL_MS =
  (Number(process.env.NEXT_PUBLIC_REFRESH_INTERVAL_SECONDS ?? "10")) * 1000;

// ---------------------------------------------------------------------------
// Types matching backend schemas.py
// ---------------------------------------------------------------------------

export interface ChangeEventSummary {
  event_id: string;
  created_at: string;
  payer: string;
  policy_id: string;
  policy_title: string;
  service_line: string;
  change_type: "TIGHTENING" | "LOOSENING" | "SCOPE_CHANGE" | "STYLISTIC";
  confidence: number;
  change_summary: string;
  clinical_impact: string;
  cpt_codes_affected: string[];
  revenue_at_risk_usd: number;
  cited_md_url: string;
  status: string;
}

export interface ChangeEventDetail extends ChangeEventSummary {
  url: string;
  changed_clause: string;
  recommended_action: string;
  cited_markdown: string;
}

export interface ChangeTypeSummary {
  change_type: string;
  count: number;
  revenue_at_risk_usd: number;
}

export interface ServiceLineSummary {
  service_line: string;
  count: number;
  revenue_at_risk_usd: number;
}

export interface PayerSummary {
  payer: string;
  count: number;
  revenue_at_risk_usd: number;
}

export interface RiskSummary {
  total_revenue_at_risk_usd: number;
  by_change_type: ChangeTypeSummary[];
  by_service_line: ServiceLineSummary[];
  by_payer: PayerSummary[];
}

export interface SystemStatus {
  pending_diffs: number;
  processed_diffs_today: number;
  latest_ingestion_run: string;
  latest_change_event: string;
  senso_published_count: number;
  datadog_enabled: boolean;
}

export interface DemoTriggerResponse {
  status: string;
  message: string;
}

export interface RouteAlertResponse {
  status: string;
  message: string;
  routed_to: string;
  webhook_url: string;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

export async function fetchChanges(params?: {
  limit?: number;
  change_type?: string;
  payer?: string;
  service_line?: string;
}): Promise<ChangeEventSummary[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.change_type) qs.set("change_type", params.change_type);
  if (params?.payer) qs.set("payer", params.payer);
  if (params?.service_line) qs.set("service_line", params.service_line);
  const query = qs.toString() ? `?${qs}` : "";
  return apiFetch<ChangeEventSummary[]>(`/api/changes${query}`);
}

export async function fetchChangeDetail(eventId: string): Promise<ChangeEventDetail> {
  return apiFetch<ChangeEventDetail>(`/api/changes/${eventId}`);
}

export async function fetchRiskSummary(): Promise<RiskSummary> {
  return apiFetch<RiskSummary>("/api/risk-summary");
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  return apiFetch<SystemStatus>("/api/system-status");
}

export async function triggerDemo(): Promise<DemoTriggerResponse> {
  return apiFetch<DemoTriggerResponse>("/api/demo/trigger", { method: "POST" });
}

export async function routeAlert(eventId: string): Promise<RouteAlertResponse> {
  return apiFetch<RouteAlertResponse>(`/api/changes/${eventId}/route-alert`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

export function formatCurrency(usd: number): string {
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(2)}M`;
  if (usd >= 1_000) return `$${(usd / 1_000).toFixed(0)}K`;
  return `$${usd.toFixed(0)}`;
}

export const CHANGE_TYPE_META: Record<
  string,
  { label: string; color: string; bg: string; border: string }
> = {
  TIGHTENING: {
    label: "Tightening",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.12)",
    border: "rgba(239,68,68,0.4)",
  },
  LOOSENING: {
    label: "Loosening",
    color: "#22c55e",
    bg: "rgba(34,197,94,0.12)",
    border: "rgba(34,197,94,0.4)",
  },
  SCOPE_CHANGE: {
    label: "Scope Change",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.12)",
    border: "rgba(245,158,11,0.4)",
  },
  STYLISTIC: {
    label: "Stylistic",
    color: "#9ca3af",
    bg: "rgba(156,163,175,0.12)",
    border: "rgba(156,163,175,0.4)",
  },
};
