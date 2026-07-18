"use client";

import { useEffect, useRef, useState } from "react";
import {
  FileText,
  Play,
  Terminal,
  CheckCircle2,
  Loader2,
  Upload,
  AlertTriangle,
} from "lucide-react";
import { getActionBrief, getDocuments, ingestDocument, IngestUnavailableError, streamCompliance } from "@/lib/api";
import type { ActionBrief, ComplianceResult, DocItem, IngestResult } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Button, Skeleton, cn } from "@/components/ui/primitives";
import { NCRCard } from "@/components/NCRCard";
import { ActionBriefCard } from "@/components/ActionBriefCard";
import { domainMeta, statusMeta } from "@/lib/format";

type Phase = "idle" | "streaming" | "done";

const TYPE_LABEL: Record<string, string> = {
  design_basis: "Design Basis",
  submittal: "Submittal",
  mix_design: "Mix Design",
  rfi: "RFI",
};

export default function CompliancePage() {
  const [docs, setDocs] = useState<DocItem[] | null>(null);
  const [selected, setSelected] = useState<DocItem | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [trace, setTrace] = useState("");
  const [result, setResult] = useState<ComplianceResult | null>(null);
  const [live, setLive] = useState<boolean | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [actionBriefs, setActionBriefs] = useState<ActionBrief[] | null>(null);
  const [briefsLive, setBriefsLive] = useState<boolean | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const traceEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getDocuments().then((r) => {
      setDocs(r.data);
      const def =
        r.data.find((d) => d.type === "design_basis") ?? r.data[0] ?? null;
      setSelected(def);
    });
    return () => cancelRef.current?.();
  }, []);

  useEffect(() => {
    traceEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [trace]);

  function runCheck() {
    if (!selected) return;
    cancelRef.current?.();
    setPhase("streaming");
    setTrace("");
    setResult(null);
    setLive(null);
    setActionBriefs(null);
    setBriefsLive(null);
    cancelRef.current = streamCompliance(selected.id, {
      onReasoning: (chunk) => setTrace((t) => t + chunk),
      onResult: (r) => {
        setResult(r);
        setPhase("done");
        if (r.ncrs.length > 0) {
          getActionBrief(selected.id, r.ncrs).then(({ data, live: l }) => {
            setActionBriefs(data);
            setBriefsLive(l);
          });
        }
      },
      onSource: (isLive) => setLive(isLive),
    });
  }

  async function handleUpload(file: File) {
    setUploading(true);
    setUploadError(null);
    setIngestResult(null);
    try {
      const r = await ingestDocument(file);
      setIngestResult(r);
      const uploadedDoc: DocItem = {
        id: r.document_id,
        title: `${r.title} (uploaded)`,
        type: "design_basis",
        status: "Pending",
        discipline: "Structural",
      };
      setDocs((prev) => [uploadedDoc, ...(prev ?? [])]);
      setSelected(uploadedDoc);
      setPhase("idle");
      setResult(null);
      setTrace("");
    } catch (e) {
      setUploadError(
        e instanceof IngestUnavailableError
          ? e.message
          : e instanceof Error
            ? e.message
            : "Upload failed.",
      );
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Automated Code Compliance"
        title="Compliance Check"
        subtitle="For the QA/QC manager — select a document, run the agent, and watch it cite the exact IS clause for every finding."
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
        {/* Document register */}
        <Card className="h-fit">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <Overline>Document register</Overline>
            <span className="font-mono text-xs text-text-lo">
              {docs?.length ?? "—"} docs
            </span>
          </div>

          {/* Legend for the A–E chip codes below — real AEC submittal-review
              status codes (A=Approved ... E=For Information), previously shown
              as a bare letter with no explanation anywhere on the page. */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 border-b border-line px-4 py-2 font-mono text-[0.6rem] text-text-lo">
            <span><span className="text-pass">A</span> Approved</span>
            <span><span className="text-warning">B</span> Approved as noted</span>
            <span><span className="text-critical">C</span> Revise &amp; resubmit</span>
            <span><span className="text-critical">D</span> Rejected</span>
            <span><span className="text-text-mid">E</span> For information</span>
          </div>

          {/* Real document upload — reads the actual file, no fabricated data */}
          <div className="border-b border-line px-3 py-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
              }}
            />
            <Button
              variant="ghost"
              className="w-full justify-center"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? (
                <>
                  <Loader2 size={15} className="animate-spin" /> Reading document…
                </>
              ) : (
                <>
                  <Upload size={15} /> Upload DBR (PDF/DOCX/TXT)
                </>
              )}
            </Button>
            <p className="mt-1.5 font-mono text-[0.62rem] leading-snug text-text-lo">
              Reads the real file text; extracts only the checked parameter set and
              abstains on the rest instead of guessing.
            </p>
            {uploadError && (
              <p className="mt-1.5 flex items-start gap-1.5 text-[0.68rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {uploadError}
              </p>
            )}
          </div>

          <ul className="p-2">
            {docs
              ? docs.map((d) => {
                  const sm = statusMeta(d.status);
                  const active = selected?.id === d.id;
                  return (
                    <li key={d.id}>
                      <button
                        onClick={() => setSelected(d)}
                        className={cn(
                          "w-full rounded px-3 py-2.5 text-left transition-colors duration-150",
                          active
                            ? "bg-bg-700"
                            : "hover:bg-bg-700/60",
                        )}
                        style={
                          active
                            ? { boxShadow: "inset 3px 0 0 var(--accent)" }
                            : undefined
                        }
                      >
                        <div className="flex items-start gap-2">
                          <FileText
                            size={15}
                            strokeWidth={1.5}
                            className="mt-0.5 shrink-0 text-text-lo"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="text-sm leading-snug text-text-hi">
                              {d.title}
                            </div>
                            <div className="mt-1 flex items-center justify-between gap-2">
                              <span className="font-mono text-[0.66rem] text-text-lo">
                                {d.id}
                              </span>
                              <span
                                title={d.status}
                                className="rounded-chip px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold"
                                style={{ color: sm.color, background: sm.bg }}
                              >
                                {d.status.split(" ")[0]}
                              </span>
                            </div>
                            <div className="mt-1 text-[0.66rem] text-text-lo">
                              {TYPE_LABEL[d.type] ?? d.type} · {d.discipline}
                            </div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })
              : [0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="m-1 h-16" />
                ))}
          </ul>
        </Card>

        {/* Run + reasoning + results */}
        <div className="space-y-5">
          <Card className="flex items-center justify-between px-5 py-4">
            <div className="min-w-0">
              <Overline>Selected document</Overline>
              <div className="mt-1 truncate text-sm font-medium text-text-hi">
                {selected?.title ?? "—"}
              </div>
              <div className="font-mono text-xs text-text-lo">
                {selected?.id}
              </div>
            </div>
            <Button
              onClick={runCheck}
              disabled={!selected || phase === "streaming"}
            >
              {phase === "streaming" ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Checking…
                </>
              ) : (
                <>
                  <Play size={16} /> Run compliance check
                </>
              )}
            </Button>
          </Card>

          {/* Real extraction preview — shown right after upload, before any check runs */}
          {ingestResult && selected?.id === ingestResult.document_id && (
            <Card className="px-5 py-4">
              <div className="flex items-center justify-between">
                <Overline>Extracted from the uploaded document</Overline>
                <span className="font-mono text-[0.66rem] text-text-lo">
                  {ingestResult.checkable_params} found · {ingestResult.abstained.length} abstained
                </span>
              </div>
              {ingestResult.extracted.length > 0 ? (
                <ul className="mt-3 space-y-2">
                  {ingestResult.extracted.map((p, i) => (
                    <li key={i} className="text-sm">
                      <div className="text-text-hi">
                        {p.element} · {p.param.replace(/_/g, " ")} ={" "}
                        <span className="font-mono">{p.value} {p.unit}</span>
                      </div>
                      <p className="mt-0.5 font-mono text-[0.68rem] leading-snug text-text-lo">
                        &ldquo;{p.source_quote}&rdquo;
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-text-mid">
                  No parameters could be confidently extracted from this document — see the abstained
                  list below for why. Running a compliance check on it will find 0 checkable parameters.
                </p>
              )}
              {ingestResult.abstained.length > 0 && (
                <div className="mt-4 border-t border-line pt-3">
                  <div className="flex items-center gap-1.5 text-[0.7rem] font-medium text-text-lo">
                    <AlertTriangle size={12} /> Abstained — not found or not confidently extractable
                  </div>
                  <ul className="mt-1.5 space-y-1">
                    {ingestResult.abstained.map((a, i) => (
                      <li key={i} className="text-[0.72rem] leading-snug text-text-lo">
                        <span className="font-mono text-text-mid">{a.param.replace(/_/g, " ")}</span>
                        {" — "}
                        {a.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}

          {/* Reasoning panel — the "alive" moment */}
          {phase !== "idle" && (
            <Card glow={phase === "streaming"} className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Terminal size={15} strokeWidth={1.5} className="text-accent" />
                  <Overline>Agent reasoning trace</Overline>
                </div>
                {live !== null && (
                  <span className="font-mono text-[0.66rem] text-text-lo">
                    {live ? "● live · backend SSE" : "● simulated · mock stream"}
                  </span>
                )}
              </div>
              <div className="relative max-h-56 overflow-y-auto px-4 py-3">
                {phase === "streaming" && (
                  <div className="scanline animate-scan" />
                )}
                <pre className="whitespace-pre-wrap font-mono text-[0.78rem] leading-relaxed text-text-mid">
                  {trace}
                  {phase === "streaming" && (
                    <span className="ml-0.5 inline-block h-3.5 w-2 translate-y-0.5 bg-accent animate-blink" />
                  )}
                </pre>
                <div ref={traceEndRef} />
              </div>
            </Card>
          )}

          {/* Results */}
          {result && phase === "done" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-card border border-line bg-bg-800 px-5 py-3.5">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-pass" />
                  <span className="text-sm text-text-mid">
                    Checked{" "}
                    <span className="font-mono text-text-hi">
                      {result.checked_params}
                    </span>{" "}
                    parameters
                  </span>
                </div>
                <div className="text-sm text-text-mid">
                  <span className="font-mono text-critical">
                    {result.ncrs.length}
                  </span>{" "}
                  finding(s)
                </div>
                <div className="text-sm text-text-mid">
                  <span className="font-mono text-pass">
                    {result.conforming.length}
                  </span>{" "}
                  conforming
                </div>
                {result.coverage && (
                  <div className="ml-auto flex items-center gap-2 text-sm text-text-mid">
                    <span className="font-mono text-text-hi">
                      {result.coverage.clauses_cited}
                    </span>
                    <span>clauses cited across</span>
                    <span className="font-mono text-text-hi">
                      {result.coverage.standards.length}
                    </span>
                    <span>standards</span>
                  </div>
                )}
              </div>

              {/* Coverage meter — honest depth-of-review */}
              {result.coverage && (
                <Card className="px-5 py-3.5">
                  <div className="flex items-center justify-between">
                    <Overline>Coverage this review</Overline>
                    <span className="font-mono text-[0.66rem] text-text-lo">
                      {result.coverage.checks_run} deterministic checks ·{" "}
                      {result.coverage.library_clauses} clauses in library
                    </span>
                  </div>
                  {result.coverage.standards_by_domain &&
                  Object.keys(result.coverage.standards_by_domain).length > 0 ? (
                    <div className="mt-3 space-y-2.5">
                      {Object.entries(result.coverage.standards_by_domain).map(([domain, stds]) => {
                        const dm = domainMeta[domain] ?? domainMeta.structural;
                        return (
                          <div key={domain} className="flex flex-wrap items-center gap-2">
                            <span
                              className="rounded-chip px-2 py-0.5 font-mono text-[0.66rem] font-semibold uppercase tracking-wide"
                              style={{ color: dm.color, background: dm.bg }}
                            >
                              {dm.label}
                            </span>
                            {stds.map((s) => (
                              <span
                                key={s}
                                className="rounded-chip border border-line bg-bg-900/60 px-2.5 py-1 font-mono text-[0.72rem] text-text-mid"
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {result.coverage.standards.map((s) => (
                        <span
                          key={s}
                          className="rounded-chip border border-line bg-bg-900/60 px-2.5 py-1 font-mono text-[0.72rem] text-text-mid"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </Card>
              )}

              {/* Overlapping requirements — multi-clause governance */}
              {result.overlaps && result.overlaps.length > 0 && (
                <Card className="px-5 py-4">
                  <Overline>Overlapping requirements · binding clause resolved</Overline>
                  <ul className="mt-3 space-y-3">
                    {result.overlaps.map((o, i) => (
                      <li key={i} className="text-sm">
                        <div className="text-text-hi">
                          {o.item} · {o.param.replace(/_/g, " ")}
                        </div>
                        <p className="mt-1 text-text-mid">{o.note}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-[0.7rem]">
                          {o.clauses.map((c) => (
                            <span
                              key={c}
                              className={cn(
                                "rounded-chip px-2 py-0.5",
                                c === o.governing
                                  ? "bg-accent/15 text-accent"
                                  : "border border-line text-text-lo",
                              )}
                            >
                              {c === o.governing ? "● binding · " : ""}
                              {c}
                            </span>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {result.ncrs.map((ncr, i) => (
                <NCRCard key={ncr.id} ncr={ncr} index={i} />
              ))}

              {actionBriefs && actionBriefs.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Overline>Action Brief · finding → linked evidence → owner action</Overline>
                    {briefsLive !== null && (
                      <span className="font-mono text-[0.66rem] text-text-lo">
                        {briefsLive ? "● live · backend" : "● derived client-side (backend unreachable)"}
                      </span>
                    )}
                  </div>
                  {actionBriefs.map((b, i) => (
                    <ActionBriefCard key={b.finding_id} brief={b} index={i} />
                  ))}
                </div>
              )}

              {result.conforming.length > 0 && (
                <Card className="px-5 py-4">
                  <Overline>Conforming parameters</Overline>
                  <ul className="mt-3 space-y-1.5">
                    {result.conforming.map((c, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-text-mid"
                      >
                        <CheckCircle2
                          size={14}
                          className="mt-0.5 shrink-0 text-pass"
                        />
                        {c}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {result.checked_params === 0 && (
                <Card className="px-5 py-4">
                  <p className="text-sm text-text-mid">
                    No checkable parameters were found in this document — nothing to report against the
                    check registry. This can happen on a real upload whose text doesn&rsquo;t confidently
                    match the narrow parameter set SiteMind extracts (see the abstained list above).
                  </p>
                </Card>
              )}
            </div>
          )}

          {/* Empty state */}
          {phase === "idle" && (
            <Card className="grid place-items-center px-5 py-16 text-center">
              <Terminal
                size={28}
                strokeWidth={1.2}
                className="mb-3 text-text-lo"
              />
              <p className="text-sm text-text-mid">
                No checks run yet — select a document and press{" "}
                <span className="font-medium text-text-hi">
                  Run compliance check
                </span>
                .
              </p>
              <p className="mt-1 font-mono text-xs text-text-lo">
                The agent streams its reasoning, then renders cited NCRs.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
