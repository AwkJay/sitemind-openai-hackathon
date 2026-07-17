// Generalizes the linked-evidence chip row originally built for ActionBriefCard
// (Compliance pillar) so the SAME real cross-references — computed from a shared
// key (wbs_id / element code), never hardcoded — surface on Supply Chain too. This
// is what makes SHP-002 <-> RFI-EL-112 <-> DC1-04-EL-030 (the DEMO_STORY.md
// narrative) discoverable by a judge clicking around the product, not only
// narrated live.
import { useState } from "react";
import { Link2, CalendarClock, ChevronDown } from "lucide-react";
import type { AffectedActivity, LinkedRFI } from "@/lib/types";

export function LinkedEvidence({
  linkedRfi,
  linkedActivity,
  className,
}: {
  linkedRfi?: LinkedRFI | null;
  linkedActivity?: AffectedActivity | null;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  if (!linkedRfi && !linkedActivity) return null;
  const hasDetail = Boolean(linkedRfi?.subject || linkedRfi?.question);
  return (
    <div className={`flex flex-col gap-2 ${className ?? ""}`}>
      <div className="flex flex-wrap gap-2">
        {linkedRfi && (
          <button
            type="button"
            onClick={() => hasDetail && setOpen((v) => !v)}
            title={
              linkedRfi.match === "curated"
                ? "Matched: this WBS activity is cited verbatim in the RFI's reference text."
                : "Matched: retrieved by text similarity (TF-IDF) between this item and the RFI."
            }
            className={`flex items-center gap-1.5 rounded-chip border border-line bg-bg-900/60 px-2.5 py-1 font-mono text-[0.7rem] text-text-mid ${
              hasDetail ? "cursor-pointer hover:border-accent hover:text-text-hi" : "cursor-default"
            }`}
          >
            <Link2 size={12} className="text-accent" />
            {linkedRfi.id} ({linkedRfi.status}) ·{" "}
            {linkedRfi.match === "curated" ? "matched by WBS ref" : "retrieved by similarity"}
            {hasDetail && (
              <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
            )}
          </button>
        )}
        {linkedActivity && (
          <span className="flex items-center gap-1.5 rounded-chip border border-line bg-bg-900/60 px-2.5 py-1 font-mono text-[0.7rem] text-text-mid">
            <CalendarClock size={12} className="text-accent" />
            {linkedActivity.name}
            {linkedActivity.on_critical_path && <span className="text-critical"> · critical path</span>}
          </span>
        )}
      </div>
      {open && hasDetail && (
        <div className="rounded-chip border border-line bg-bg-900/40 px-3 py-2 text-[0.75rem] leading-snug text-text-mid">
          {linkedRfi?.subject && (
            <p>
              <span className="text-text-lo">Subject: </span>
              {linkedRfi.subject}
            </p>
          )}
          {linkedRfi?.question && (
            <p className="mt-1">
              <span className="text-text-lo">Question: </span>
              {linkedRfi.question}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
