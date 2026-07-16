import type { AlertSeverity, CommissioningVerdict, EquipmentSpecCheck, ImpactPillar, MitigationAgent, Severity, SourceType } from "./types";

export function inrCompact(n: number): string {
  // Indian Crore/Lakh compaction for ₹ figures
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(n % 1e7 === 0 ? 0 : 2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`;
  return `₹${n.toLocaleString("en-IN")}`;
}

export const severityMeta: Record<
  Severity,
  { label: string; color: string; bg: string; border: string; icon: string }
> = {
  HIGH: {
    label: "HIGH",
    color: "var(--critical)",
    bg: "var(--critical-bg)",
    border: "var(--critical)",
    icon: "▲",
  },
  MEDIUM: {
    label: "MEDIUM",
    color: "var(--warning)",
    bg: "var(--warning-bg)",
    border: "var(--warning)",
    icon: "◆",
  },
  LOW: {
    label: "LOW",
    color: "var(--text-mid)",
    bg: "rgba(159,176,191,0.12)",
    border: "var(--text-lo)",
    icon: "•",
  },
  ADVISORY: {
    label: "ADVISORY",
    color: "var(--warning)",
    bg: "var(--info-bg)",
    border: "var(--info)",
    icon: "◐",
  },
};

// Honest provenance disclosure for CitedClauseBox — see backend Citation.source_type.
// manak_verified is the gold standard; the other three are real primary-source
// extractions with a stated reliability caveat, never presented as equivalent.
export const sourceTypeMeta: Record<
  SourceType,
  { label: string; caveat: string; color: string; bg: string }
> = {
  manak_verified: {
    label: "Verified · manak",
    caveat: "Fetched verbatim from the manak digitised-standards MCP.",
    color: "var(--accent)",
    bg: "rgba(190,242,100,0.12)",
  },
  primary_native_pdf: {
    label: "Primary · native PDF",
    caveat:
      "Real primary BIS/CEA document, clean native (non-scanned) PDF — no OCR risk, but not manak-fetched.",
    color: "var(--data)",
    bg: "rgba(56,189,248,0.12)",
  },
  primary_scan_ocr: {
    label: "Primary · OCR scan",
    caveat:
      "Real primary BIS document extracted via OCR from an older scanned edition — verify edition currency.",
    color: "var(--warning)",
    bg: "var(--warning-bg)",
  },
  cross_source_unverified: {
    label: "Cross-source · unverified",
    caveat:
      "Compiled from convergent secondary sources because the primary standard is paywalled — not fetched from one verified primary document.",
    color: "var(--critical)",
    bg: "var(--critical-bg)",
  },
};

export const domainMeta: Record<string, { label: string; color: string; bg: string }> = {
  structural: { label: "Structural", color: "var(--text-mid)", bg: "rgba(159,176,191,0.12)" },
  electrical: { label: "Electrical", color: "var(--data)", bg: "rgba(56,189,248,0.12)" },
  mechanical: { label: "Mechanical", color: "var(--pass)", bg: "var(--pass-bg)" },
};

export const commissioningVerdictMeta: Record<
  CommissioningVerdict,
  { label: string; color: string; bg: string }
> = {
  PASS: { label: "PASS", color: "var(--pass)", bg: "var(--pass-bg)" },
  OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE: {
    label: "WITHIN ALLOWABLE",
    color: "var(--warning)",
    bg: "var(--warning-bg)",
  },
  FAIL: { label: "FAIL", color: "var(--critical)", bg: "var(--critical-bg)" },
  NOT_CHECKABLE: { label: "NOT CHECKABLE", color: "var(--text-lo)", bg: "rgba(159,176,191,0.10)" },
};

export const equipmentSpecMeta: Record<
  EquipmentSpecCheck["status"],
  { label: string; color: string; bg: string }
> = {
  MATCH: { label: "spec match", color: "var(--pass)", bg: "var(--pass-bg)" },
  MISMATCH: { label: "spec mismatch", color: "var(--critical)", bg: "var(--critical-bg)" },
  SPEC_NOT_PROVIDED: { label: "spec not provided", color: "var(--warning)", bg: "var(--warning-bg)" },
  NOT_APPLICABLE: { label: "no standard yet", color: "var(--text-lo)", bg: "rgba(159,176,191,0.10)" },
};

export const alertSeverityMeta: Record<AlertSeverity, { label: string; color: string; bg: string }> = {
  CRITICAL: { label: "CRITICAL", color: "var(--critical)", bg: "var(--critical-bg)" },
  WARNING: { label: "WARNING", color: "var(--warning)", bg: "var(--warning-bg)" },
  INFO: { label: "INFO", color: "var(--data)", bg: "rgba(56,189,248,0.12)" },
};

export const mitigationAgentMeta: Record<MitigationAgent, { label: string; icon: string }> = {
  procurement_alternative: { label: "Procurement alternative", icon: "■" },
  resequencing_float: { label: "Resequencing / float", icon: "▲" },
  resource_recovery: { label: "Resource / overtime recovery", icon: "●" },
};

export const impactPillarMeta: Record<ImpactPillar, { label: string; href: string }> = {
  compliance: { label: "Compliance", href: "/compliance" },
  schedule: { label: "Schedule", href: "/schedule" },
  supply_chain: { label: "Supply Chain", href: "/supply-chain" },
  commissioning: { label: "Commissioning QA", href: "/commissioning" },
};

export function statusMeta(status: string): { color: string; bg: string } {
  const s = status.toUpperCase();
  if (s.startsWith("A") || s.includes("APPROVED") && !s.includes("NOTED"))
    return { color: "var(--pass)", bg: "var(--pass-bg)" };
  if (s.startsWith("B") || s.includes("NOTED"))
    return { color: "var(--warning)", bg: "var(--warning-bg)" };
  if (s.startsWith("C") || s.includes("REVISE"))
    return { color: "var(--critical)", bg: "var(--critical-bg)" };
  return { color: "var(--text-mid)", bg: "rgba(159,176,191,0.10)" };
}
