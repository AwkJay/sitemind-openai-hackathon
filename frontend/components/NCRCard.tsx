import { FileSearch, ShieldAlert, Wrench, Info, Layers } from "lucide-react";
import type { NCR } from "@/lib/types";
import { domainMeta, severityMeta } from "@/lib/format";
import { CitedClauseBox } from "./CitedClauseBox";
import { Chip } from "./ui/primitives";

export function NCRCard({ ncr, index }: { ncr: NCR; index: number }) {
  const meta = severityMeta[ncr.severity];
  const advisory = ncr.severity === "ADVISORY";
  const dm = domainMeta[ncr.domain ?? "structural"];
  return (
    <article
      className="animate-fadeUp rounded-card border border-line bg-bg-800"
      style={{ borderLeft: `3px solid ${meta.border}`, animationDelay: `${index * 90}ms` }}
    >
      <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3.5">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-semibold text-text-hi">
            {ncr.id}
          </span>
          <span className="text-text-lo">·</span>
          <span className="text-sm text-text-mid">{ncr.item}</span>
        </div>
        <div className="flex items-center gap-2">
          <Chip color={dm.color} bg={dm.bg}>
            {dm.label}
          </Chip>
          <Chip color={meta.color} bg={meta.bg}>
            <span aria-hidden>{meta.icon}</span> {meta.label}
          </Chip>
        </div>
      </header>

      <div className="space-y-4 px-5 py-4">
        {/* Finding */}
        <div className="flex gap-3">
          <ShieldAlert
            size={18}
            strokeWidth={1.5}
            className="mt-0.5 shrink-0"
            style={{ color: meta.color }}
          />
          <div>
            <div className="overline mb-1">Finding</div>
            <p className="text-[0.95rem] leading-relaxed text-text-hi">
              {ncr.finding}
            </p>
          </div>
        </div>

        {/* Source span — proves it came from the document */}
        {ncr.source && (
          <div className="flex gap-3">
            <FileSearch
              size={18}
              strokeWidth={1.5}
              className="mt-0.5 shrink-0 text-text-lo"
            />
            <div className="min-w-0">
              <div className="overline mb-1">Source in document</div>
              <blockquote className="rounded bg-bg-900/60 px-3 py-2 text-sm text-text-mid">
                <span className="italic">&ldquo;{ncr.source.quote}&rdquo;</span>
                <span className="mt-1 block font-mono text-[0.72rem] text-text-lo">
                  {ncr.source.location}
                </span>
              </blockquote>
            </div>
          </div>
        )}

        {/* The cited clause box — the hero */}
        {ncr.citation && (
          <CitedClauseBox citation={ncr.citation} advisory={advisory} />
        )}

        {/* Multi-clause governance — names the binding requirement */}
        {ncr.governing_note && (
          <div className="flex gap-3">
            <Layers
              size={18}
              strokeWidth={1.5}
              className="mt-0.5 shrink-0 text-accent"
            />
            <div>
              <div className="overline mb-1">Governing requirement</div>
              <p className="rounded border-l-2 border-accent/40 bg-bg-900/50 px-3 py-2 text-sm leading-relaxed text-text-mid">
                {ncr.governing_note}
              </p>
            </div>
          </div>
        )}

        {/* Why it matters */}
        <div>
          <div className="overline mb-1">Why it matters</div>
          <p className="text-sm leading-relaxed text-text-mid">
            {ncr.why_it_matters}
          </p>
        </div>

        {/* Corrective action OR advisory recommendation */}
        {advisory ? (
          <div
            className="rounded px-4 py-3"
            style={{ background: "var(--info-bg)", border: "1px solid #38bdf833" }}
          >
            <div className="flex items-center gap-2">
              <Info size={15} strokeWidth={1.8} style={{ color: "var(--info)" }} />
              <span
                className="overline"
                style={{ color: "var(--info)", letterSpacing: "0.08em" }}
              >
                Advisory · Judgment call
              </span>
            </div>
            <p className="mt-1.5 text-sm leading-relaxed text-text-hi">
              {ncr.recommendation}
            </p>
            {ncr.confirm_with && (
              <p className="mt-2 text-xs text-text-mid">
                <span className="font-mono">↳</span> Confirm with{" "}
                <span className="font-semibold text-text-hi">
                  {ncr.confirm_with}
                </span>{" "}
                before incorporation.
              </p>
            )}
          </div>
        ) : (
          <div className="flex gap-3">
            <Wrench
              size={18}
              strokeWidth={1.5}
              className="mt-0.5 shrink-0 text-accent"
            />
            <div>
              <div className="overline mb-1">Corrective action</div>
              <p className="rounded border-l-2 border-accent/40 bg-bg-900/50 px-3 py-2 text-sm leading-relaxed text-text-hi">
                {ncr.corrective_action}
              </p>
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
