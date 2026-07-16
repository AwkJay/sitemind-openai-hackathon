import { ExternalLink } from "lucide-react";
import type { Citation } from "@/lib/types";
import { sourceTypeMeta } from "@/lib/format";

// THE signature component. A cited clause rendered as a verified system fact:
// lime left-border, provenance badge, mono clause id + exact text, verify link.
// The badge is NEVER a generic "Verified" — it discloses the real source_type
// (manak / primary native PDF / primary OCR scan / cross-source) so a non-manak
// citation is never presented as equivalent to a manak one.
export function CitedClauseBox({
  citation,
  advisory,
}: {
  citation: Citation;
  advisory?: boolean;
}) {
  const st = sourceTypeMeta[citation.source_type ?? "manak_verified"];
  const accent = advisory ? "var(--info)" : st.color;
  const badgeBg = advisory ? "var(--info-bg)" : st.bg;
  return (
    <div
      className="relative rounded bg-bg-700 px-4 py-3"
      style={{
        borderLeft: `3px solid ${accent}`,
        boxShadow: advisory ? undefined : "0 0 0 1px var(--accent-glow)",
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-mono inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider"
          title={st.caveat}
          style={{ color: accent, background: badgeBg, border: `1px solid ${accent}40` }}
        >
          ◢ {st.label}
        </span>
        <span className="font-mono text-[0.7rem] text-text-lo">
          ground truth · clauses.json
        </span>
      </div>
      {citation.source_type && citation.source_type !== "manak_verified" && (
        <p className="mt-1.5 text-[0.7rem] leading-snug text-text-lo">{st.caveat}</p>
      )}

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="clause text-base font-semibold text-text-hi">
          {citation.standard}
        </span>
        <span className="clause text-sm text-text-mid">
          Cl. {citation.clause}
        </span>
      </div>

      <p className="mt-1.5 font-sans text-[0.95rem] italic leading-relaxed text-text-mid">
        &ldquo;{citation.text}&rdquo;
      </p>

      <a
        href={citation.verify_url}
        target="_blank"
        rel="noreferrer"
        className="mt-2.5 inline-flex items-center gap-1.5 text-sm font-medium text-data transition-colors hover:text-[#7cd4fb]"
      >
        <span aria-hidden>↳</span> View standard
        <ExternalLink size={13} strokeWidth={2} />
      </a>
    </div>
  );
}
