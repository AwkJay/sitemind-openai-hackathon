import { GitBranch, Gauge } from "lucide-react";
import type { ActionBrief } from "@/lib/types";
import { Chip, Card, Overline } from "./ui/primitives";
import { LinkedEvidence } from "./LinkedEvidence";

const CONFIDENCE_META: Record<ActionBrief["confidence"]["level"], { color: string; bg: string; label: string }> = {
  high: { color: "var(--pass)", bg: "rgba(34,197,94,0.12)", label: "High confidence" },
  medium: { color: "var(--info)", bg: "rgba(56,189,248,0.12)", label: "Medium confidence" },
  low: { color: "var(--critical)", bg: "rgba(239,68,68,0.12)", label: "Low confidence" },
};

export function ActionBriefCard({ brief, index }: { brief: ActionBrief; index: number }) {
  const cm = CONFIDENCE_META[brief.confidence.level];
  return (
    <div className="animate-fadeUp" style={{ animationDelay: `${index * 90}ms` }}>
    <Card className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Overline>Action Brief · {brief.finding_id}</Overline>
          <p className="mt-1 text-sm text-text-hi">
            {brief.parameter.name.replace(/_/g, " ")}
            {brief.parameter.value ? ` = ${brief.parameter.value}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Chip color={cm.color} bg={cm.bg}>
            <Gauge size={12} /> {cm.label}
          </Chip>
          {brief.status === "REVIEW_REQUIRED" && (
            <Chip color="var(--critical)" bg="rgba(239,68,68,0.12)">
              Needs human review
            </Chip>
          )}
        </div>
      </div>

      <p className="mt-2 text-[0.7rem] leading-snug text-text-lo">{brief.confidence.basis}</p>

      <LinkedEvidence
        linkedRfi={brief.linked_rfi}
        linkedActivity={brief.affected_activity}
        className="mt-3"
      />

      {brief.recommended_action ? (
        <div className="mt-3 rounded border-l-2 border-accent/40 bg-bg-900/50 px-3 py-2.5">
          <div className="text-[0.68rem] font-medium uppercase tracking-wide text-text-lo">
            {brief.recommended_action.owner_role}
          </div>
          <p className="mt-1 text-sm leading-relaxed text-text-hi">{brief.recommended_action.action}</p>
          <p className="mt-1 text-[0.7rem] text-text-lo">{brief.recommended_action.note}</p>
        </div>
      ) : (
        <p className="mt-3 rounded border-l-2 border-critical/40 bg-bg-900/50 px-3 py-2.5 text-sm text-text-mid">
          Evidence insufficient for a prescriptive action — escalated to the Engineer of Record for
          manual review.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <GitBranch size={12} className="text-text-lo" />
        {brief.evidence.map((e, i) => (
          <span
            key={i}
            className="rounded-chip border border-line px-2 py-0.5 font-mono text-[0.66rem] text-text-lo"
          >
            {e}
          </span>
        ))}
      </div>
    </Card>
    </div>
  );
}
