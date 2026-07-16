// API client. EVERY call gracefully falls back to bundled mock data so the UI
// always renders for a demo, even with the backend down. See lib/mocks.ts.

import {
  PROJECT_LABEL,
  mockComplianceFor,
  mockCopilotAnswer,
  mockCostRisk,
  mockDocuments,
  mockGantt,
  mockKg,
  mockOverview,
  mockReasoningTrace,
  mockRisks,
  mockSupplyChainAlerts,
  mockSupplyChainMap,
  mockSupplyChainMeta,
  mockSupplyChainRisks,
  mockShipments,
} from "./mocks";
import type {
  ActionBrief,
  CommissioningIngestResult,
  ComplianceResult,
  Confidence,
  CostRisk,
  DocItem,
  GanttBar,
  IngestResult,
  KgGraph,
  NCR,
  OverviewStats,
  RFIAnswer,
  RiskItem,
  Shipment,
  SupplyChainAlert,
  SupplyChainMap,
  SupplyChainMeta,
  SupplyChainRisk,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const TIMEOUT_MS = 3500;

async function getJSON<T>(path: string, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}${path}`, { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: (await res.json()) as T, live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

async function postJSON<T>(path: string, body: unknown, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: (await res.json()) as T, live: true };
  } catch {
    return { data: fallback, live: false };
  }
}

export const getOverview = () =>
  getJSON<OverviewStats>("/api/overview", mockOverview);

export const getCostRisk = () =>
  getJSON<CostRisk>("/api/cost-risk", mockCostRisk);

export const getDocuments = () =>
  getJSON<DocItem[]>("/api/documents", mockDocuments);

export const runCompliance = (documentId: string) =>
  postJSON<ComplianceResult>(
    "/api/compliance/check",
    { document_id: documentId },
    mockComplianceFor(documentId),
  );

export const askCopilot = (question: string) =>
  postJSON<RFIAnswer>(
    "/api/copilot/ask",
    { question },
    mockCopilotAnswer(question),
  );

export const getRisks = () =>
  getJSON<RiskItem[]>("/api/schedule/risks", mockRisks);

export const getGantt = () =>
  getJSON<GanttBar[]>("/api/schedule/gantt", mockGantt);

export const getKg = (elementId = "eq-tx") =>
  getJSON<KgGraph>(`/api/kg/${elementId}`, mockKg);

// ── Supply Chain Visibility ─────────────────────────────────────────────────

export const getShipments = () =>
  getJSON<Shipment[]>("/api/supply-chain/shipments", mockShipments);

export const getSupplyChainRisks = () =>
  getJSON<SupplyChainRisk[]>("/api/supply-chain/risks", mockSupplyChainRisks);

export const getSupplyChainMap = () =>
  getJSON<SupplyChainMap>("/api/supply-chain/map", mockSupplyChainMap);

export const getSupplyChainAlerts = () =>
  getJSON<SupplyChainAlert[]>("/api/supply-chain/alerts", mockSupplyChainAlerts);

export const getSupplyChainMeta = () =>
  getJSON<SupplyChainMeta>("/api/supply-chain/meta", mockSupplyChainMeta);

// ── Action Brief ───────────────────────────────────────────────────────────
// If the backend is unreachable, we do NOT fabricate RFI/schedule links or a
// fake confidence score. The fallback derives only what's honestly computable
// client-side from the NCRs already on screen (same confidence rule as the
// backend); linked_rfi/affected_activity are omitted rather than guessed.
function fallbackConfidence(ncr: NCR): { confidence: Confidence; status: "NCR" | "REVIEW_REQUIRED" } {
  if (ncr.severity === "ADVISORY") {
    return {
      confidence: {
        level: "medium",
        basis: "cited judgment call — requires EOR confirmation, not a binary deterministic threshold",
      },
      status: "NCR",
    };
  }
  if (ncr.source && ncr.citation) {
    return {
      confidence: {
        level: "high",
        basis: "exact-span extraction + exact clause match + deterministic result",
      },
      status: "NCR",
    };
  }
  return {
    confidence: { level: "low", basis: "missing source span or citation — insufficient evidence" },
    status: "REVIEW_REQUIRED",
  };
}

function fallbackActionBrief(ncrs: NCR[]): ActionBrief[] {
  return ncrs.map((ncr) => {
    const { confidence, status } = fallbackConfidence(ncr);
    const evidence: string[] = [];
    if (ncr.source) evidence.push(ncr.source.location);
    if (ncr.citation) evidence.push(`${ncr.citation.standard} Cl ${ncr.citation.clause}`);
    return {
      finding_id: ncr.id,
      parameter: { name: ncr.item, value: "", source: ncr.source },
      check: {
        clause: ncr.citation,
        requirement: ncr.finding,
        result: ncr.severity === "ADVISORY" ? "ADVISORY" : "FAIL",
        engine: "deterministic",
      },
      status,
      linked_rfi: null,
      affected_activity: null,
      recommended_action:
        status === "REVIEW_REQUIRED"
          ? null
          : {
              owner_role: "Design Manager",
              action: ncr.corrective_action,
              note: "System raises a design clarification; it does not redesign.",
            },
      confidence,
      evidence,
      computed_impact: null,
    };
  });
}

export async function getActionBrief(documentId: string, ncrs: NCR[]): Promise<{ data: ActionBrief[]; live: boolean }> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const res = await fetch(`${API_URL}/api/compliance/action-brief/${encodeURIComponent(documentId)}`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: (await res.json()) as ActionBrief[], live: true };
  } catch {
    return { data: fallbackActionBrief(ncrs), live: false };
  }
}

export const projectLabel = PROJECT_LABEL;

// ── Health / system status (drives the "Agents online" indicator + Settings panel) ──
export interface HealthState {
  status: string;
  offline_mode: boolean;
  provider: string;
  langfuse_enabled: boolean;
}

const FALLBACK_HEALTH: HealthState = {
  status: "unknown",
  offline_mode: true,
  provider: "offline",
  langfuse_enabled: false,
};

export async function getHealth(): Promise<{ data: HealthState; live: boolean }> {
  return getJSON<HealthState>("/api/health", FALLBACK_HEALTH);
}

// ── Simulated demo clock (proves risk/alert numbers are computed live, not
// hardcoded — advancing "today" changes real downstream output). No mock
// fallback: if the backend is unreachable there is nothing to advance. ──
export interface ClockState {
  base_day: number;
  offset_days: number;
  current_day: number;
  max_offset_days: number;
}

export async function getClockState(): Promise<ClockState | null> {
  try {
    const res = await fetch(`${API_URL}/api/clock`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as ClockState;
  } catch {
    return null;
  }
}

export async function advanceClock(days: number): Promise<ClockState | null> {
  try {
    const res = await fetch(`${API_URL}/api/clock/advance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as ClockState;
  } catch {
    return null;
  }
}

export async function resetClock(): Promise<ClockState | null> {
  try {
    const res = await fetch(`${API_URL}/api/clock/reset`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as ClockState;
  } catch {
    return null;
  }
}

// ── Real document upload ──────────────────────────────────────────────────
// Deliberately NO mock fallback: this reads an actual uploaded file. If the
// backend is unreachable we must say so, not fabricate an extraction result —
// that would be exactly the kind of dishonesty the product promises to avoid.
export class IngestUnavailableError extends Error {}

export async function ingestDocument(file: File): Promise<IngestResult> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/compliance/ingest`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new IngestUnavailableError(
      "Backend unreachable — document upload needs the live SiteMind API (it reads " +
        "the actual file), so there is no offline/mock fallback for this action.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Upload failed (HTTP ${res.status})`);
  }
  return (await res.json()) as IngestResult;
}

// ── Commissioning QA (Pillar 5, cooling-only slice) ─────────────────────────
// Deliberately NO mock fallback: this reads an actual uploaded CSV test log.
// Same honesty rule as ingestDocument — if the backend is unreachable we must
// say so, not fabricate a quality package.
export class CommissioningUnavailableError extends Error {}

export async function ingestCommissioningLog(file: File): Promise<CommissioningIngestResult> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/commissioning/ingest`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new CommissioningUnavailableError(
      "Backend unreachable — commissioning log ingest needs the live SiteMind API (it parses " +
        "the actual CSV test log), so there is no offline/mock fallback for this action.",
    );
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    const msg = detail?.detail?.message ?? detail?.detail ?? `Upload failed (HTTP ${res.status})`;
    const errors: string[] = detail?.detail?.errors ?? [];
    throw new Error(errors.length ? `${msg} — ${errors.join("; ")}` : msg);
  }
  return (await res.json()) as CommissioningIngestResult;
}

export function qualityPackageHtmlUrl(runId: string): string {
  return `${API_URL}/api/commissioning/quality-package/${encodeURIComponent(runId)}/html`;
}

// ── Streaming compliance check ────────────────────────────────────────────────
// Tries the SSE endpoint; if unreachable, simulates a token stream over the mock
// reasoning trace so the "AI is reasoning" panel always animates for the demo.

export interface StreamHandlers {
  onReasoning: (chunk: string) => void;
  onResult: (result: ComplianceResult) => void;
  onSource?: (live: boolean) => void;
}

export function streamCompliance(
  documentId: string,
  handlers: StreamHandlers,
): () => void {
  let cancelled = false;
  const ctrl = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/check/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ document_id: documentId }),
        signal: ctrl.signal,
        cache: "no-store",
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      handlers.onSource?.(true);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!cancelled) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const line = frame
            .split("\n")
            .find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            const evt = JSON.parse(line.slice(5).trim());
            if (evt.type === "reasoning") handlers.onReasoning(evt.text + " ");
            else if (evt.type === "result") handlers.onResult(evt.data);
          } catch {
            /* ignore malformed frame */
          }
        }
      }
    } catch {
      // Fallback: simulate streaming over the mock trace.
      if (cancelled) return;
      handlers.onSource?.(false);
      await simulateStream(documentId, handlers, () => cancelled);
    }
  })();

  return () => {
    cancelled = true;
    ctrl.abort();
  };
}

function delay(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

async function simulateStream(
  documentId: string,
  handlers: StreamHandlers,
  isCancelled: () => boolean,
) {
  const lines = mockReasoningTrace(documentId);
  for (const line of lines) {
    const words = line.split(" ");
    for (const w of words) {
      if (isCancelled()) return;
      handlers.onReasoning(w + " ");
      await delay(18 + Math.random() * 26);
    }
    handlers.onReasoning("\n");
    await delay(160);
  }
  if (isCancelled()) return;
  await delay(220);
  handlers.onResult(mockComplianceFor(documentId));
}
