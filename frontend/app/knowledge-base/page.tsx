"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Search,
  Library,
  Info,
  WifiOff,
  FileText,
  MinusCircle,
} from "lucide-react";
import {
  getRetrievalCorpora,
  queryKnowledgeBase,
  RetrievalUnavailableError,
  uploadKnowledgeBaseDocument,
  type RetrievalAvailability,
} from "@/lib/api";
import type {
  RetrievalCitation,
  RetrievalCorpusSummary,
  RetrievalIngestManifest,
  RetrievalQueryResult,
} from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Button, Card, Chip, Overline, Skeleton } from "@/components/ui/primitives";
import { retrievalSourceTypeMetaFor } from "@/lib/format";

const DEFAULT_CORPUS = "my-documents";

function CitationCard({ citation, index }: { citation: RetrievalCitation; index: number }) {
  const meta = retrievalSourceTypeMetaFor(citation.source_type);
  return (
    <div
      className="relative rounded bg-bg-700 px-4 py-3"
      style={{ borderLeft: `3px solid ${meta.color}` }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className="font-mono inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider"
          title={meta.caveat}
          style={{ color: meta.color, background: meta.bg, border: `1px solid ${meta.color}40` }}
        >
          ◢ {meta.label}
        </span>
        <span className="font-mono text-[0.7rem] text-text-lo">
          score {citation.score.toFixed(3)}
        </span>
      </div>
      <p className="mt-1.5 text-[0.7rem] leading-snug text-text-lo">{meta.caveat}</p>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="clause text-sm font-semibold text-text-hi">
          {citation.filename}
        </span>
        {citation.breadcrumb && (
          <span className="clause text-xs text-text-mid">{citation.breadcrumb}</span>
        )}
        {!citation.breadcrumb && citation.heading && (
          <span className="clause text-xs text-text-mid">{citation.heading}</span>
        )}
      </div>

      <p className="mt-1.5 font-sans text-[0.92rem] italic leading-relaxed text-text-mid">
        &ldquo;{citation.text}&rdquo;
      </p>

      <div className="mt-2 text-[0.68rem] text-text-lo">
        result {index + 1} · chunk <span className="font-mono">{citation.chunk_id}</span>
      </div>
    </div>
  );
}

function NotEnabledState({ availability }: { availability: RetrievalAvailability }) {
  const unreachable = availability === "unreachable";
  return (
    <Card className="grid place-items-center px-6 py-16 text-center">
      {unreachable ? (
        <WifiOff size={28} strokeWidth={1.2} className="mb-3 text-text-lo" />
      ) : (
        <MinusCircle size={28} strokeWidth={1.2} className="mb-3 text-text-lo" />
      )}
      <p className="max-w-md text-sm text-text-mid">
        {unreachable ? (
          <>
            The SiteMind backend is unreachable, so the Knowledge Base can&rsquo;t be checked or
            used right now. Confirm the backend is running and reachable at the configured API URL.
          </>
        ) : (
          <>
            Knowledge Base is not enabled in this environment. This backend is running with{" "}
            <span className="font-mono text-text-hi">RETRIEVAL_ENABLED</span> off (the default), so
            none of the retrieval routes are mounted. Start the backend with{" "}
            <span className="font-mono text-text-hi">RETRIEVAL_ENABLED=1</span> to use document
            upload and hybrid search here.
          </>
        )}
      </p>
    </Card>
  );
}

export default function KnowledgeBasePage() {
  const [availability, setAvailability] = useState<RetrievalAvailability>("checking");
  const [corpora, setCorpora] = useState<RetrievalCorpusSummary[]>([]);
  const [corpusInput, setCorpusInput] = useState(DEFAULT_CORPUS);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<RetrievalIngestManifest | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [question, setQuestion] = useState("");
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryResult, setQueryResult] = useState<RetrievalQueryResult | null>(null);

  const refreshCorpora = useCallback(async () => {
    const { corpora: list, availability: a } = await getRetrievalCorpora();
    setAvailability(a);
    setCorpora(list);
  }, []);

  useEffect(() => {
    refreshCorpora();
  }, [refreshCorpora]);

  async function handleUpload(file: File) {
    const corpusName = corpusInput.trim() || DEFAULT_CORPUS;
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const manifest = await uploadKnowledgeBaseDocument(corpusName, file);
      setUploadResult(manifest);
      // Reflect the new/updated corpus + chunk counts immediately.
      await refreshCorpora();
    } catch (e) {
      if (e instanceof RetrievalUnavailableError) {
        setAvailability(e.message.includes("not enabled") ? "disabled" : "unreachable");
      }
      setUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleQuery() {
    const q = question.trim();
    if (!q) return;
    const corpusName = corpusInput.trim() || DEFAULT_CORPUS;
    setQuerying(true);
    setQueryError(null);
    setQueryResult(null);
    try {
      const result = await queryKnowledgeBase(corpusName, q);
      setQueryResult(result);
    } catch (e) {
      if (e instanceof RetrievalUnavailableError) {
        setAvailability(e.message.includes("not enabled") ? "disabled" : "unreachable");
      }
      setQueryError(e instanceof Error ? e.message : "Query failed.");
    } finally {
      setQuerying(false);
    }
  }

  const showNotEnabled = availability === "disabled" || availability === "unreachable";

  return (
    <div>
      <PageHeader
        eyebrow="Standards & document retrieval (Phase 3)"
        title="Knowledge Base"
        subtitle="Upload your own standards/QA documents into a searchable corpus, then ask questions answered with cited, verbatim chunks — hybrid BM25 + dense retrieval, never fabricated."
      />

      {availability === "checking" && (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {showNotEnabled && <NotEnabledState availability={availability} />}

      {availability === "available" && (
        <div className="space-y-5">
          {/* Corpus selector */}
          <Card className="px-5 py-4">
            <Overline>Corpus</Overline>
            <p className="mt-1 text-sm text-text-mid">
              Pick an existing corpus below, or type a new name — a brand-new corpus is created
              automatically the first time you upload into it. Uploads and queries below both use
              this corpus.
            </p>
            <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
              <input
                value={corpusInput}
                onChange={(e) => setCorpusInput(e.target.value)}
                placeholder={DEFAULT_CORPUS}
                list="kb-corpus-options"
                className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <datalist id="kb-corpus-options">
                {corpora.map((c) => (
                  <option key={c.corpus_name} value={c.corpus_name} />
                ))}
              </datalist>
              {corpusInput.trim() !== DEFAULT_CORPUS && (
                <button
                  type="button"
                  onClick={() => setCorpusInput(DEFAULT_CORPUS)}
                  className="shrink-0 text-xs text-text-lo underline decoration-dotted underline-offset-2 hover:text-text-mid"
                >
                  reset to &ldquo;{DEFAULT_CORPUS}&rdquo;
                </button>
              )}
            </div>

            {corpora.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {corpora.map((c) => {
                  const provenanceMeta = retrievalSourceTypeMetaFor(c.provenance_tag ?? "company_uploaded");
                  return (
                    <button
                      key={c.corpus_name}
                      onClick={() => setCorpusInput(c.corpus_name)}
                      title={provenanceMeta.caveat}
                      className={
                        "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors " +
                        (c.corpus_name === corpusInput.trim()
                          ? "border-accent text-text-hi"
                          : "border-line text-text-mid hover:border-text-lo hover:text-text-hi")
                      }
                    >
                      <Library size={12} strokeWidth={1.6} />
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: provenanceMeta.color }}
                      />
                      <span className="font-mono">{c.corpus_name}</span>
                      <span className="text-text-lo">
                        · {c.document_count} doc{c.document_count === 1 ? "" : "s"} · {c.chunk_count} chunk
                        {c.chunk_count === 1 ? "" : "s"}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-text-lo">
                <Info size={12} strokeWidth={1.6} />
                No corpora exist yet — upload a document below to create{" "}
                <span className="font-mono">{corpusInput.trim() || DEFAULT_CORPUS}</span>.
              </p>
            )}
          </Card>

          {/* Upload */}
          <Card className="px-5 py-4">
            <Overline>Upload a document</Overline>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files?.[0];
                if (f) handleUpload(f);
              }}
              className={
                "mt-3 flex flex-col items-center justify-center gap-2 rounded border border-dashed px-5 py-8 text-center transition-colors " +
                (dragOver ? "border-accent bg-bg-700/60" : "border-line bg-bg-900/40")
              }
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                }}
              />
              <Upload size={22} strokeWidth={1.4} className="text-text-lo" />
              <p className="text-sm text-text-mid">
                Drag & drop a file here, or{" "}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="font-medium text-data hover:text-[#7cd4fb]"
                  disabled={uploading}
                >
                  browse
                </button>
              </p>
              <p className="text-[0.7rem] text-text-lo">
                Uploads into corpus{" "}
                <span className="font-mono text-text-hi">{corpusInput.trim() || DEFAULT_CORPUS}</span>
              </p>
              {uploading && (
                <div className="mt-1 flex items-center gap-2 text-xs text-text-mid">
                  <Loader2 size={14} className="animate-spin text-accent" /> Ingesting…
                </div>
              )}
            </div>

            {uploadError && (
              <p className="mt-3 flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {uploadError}
              </p>
            )}

            {uploadResult && (
              <div className="mt-3 flex items-start gap-2.5 rounded border-l-2 border-pass/50 bg-bg-900/40 px-3 py-2.5">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-pass" />
                <div className="text-xs text-text-mid">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-mono font-semibold text-text-hi">
                      {uploadResult.filename}
                    </span>
                    <span className="text-text-lo">→</span>
                    <span className="font-mono">{uploadResult.corpus_name}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                    <span>
                      <span className="font-mono text-text-hi">{uploadResult.chunk_count}</span> chunk
                      {uploadResult.chunk_count === 1 ? "" : "s"} indexed
                    </span>
                    <span>
                      structure-aware:{" "}
                      <span className="font-mono text-text-hi">
                        {uploadResult.structured ? "yes" : "no (paragraph/sentence fallback)"}
                      </span>
                    </span>
                    <span>
                      provenance: <span className="font-mono text-text-hi">{uploadResult.provenance_tag}</span>
                    </span>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Query */}
          <Card className="px-5 py-4">
            <Overline>Ask a question</Overline>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleQuery();
              }}
              className="mt-3 flex items-center gap-2"
            >
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={`Ask something answerable from “${corpusInput.trim() || DEFAULT_CORPUS}”…`}
                className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <Button type="submit" disabled={querying || !question.trim()}>
                {querying ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                Search
              </Button>
            </form>

            {queryError && (
              <p className="mt-3 flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {queryError}
              </p>
            )}

            {queryResult && (
              <div className="mt-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-text-lo">
                  <span>
                    corpus <span className="font-mono text-text-mid">{queryResult.corpus_name}</span>
                  </span>
                  <span>·</span>
                  <span>
                    abstention floor <span className="font-mono text-text-mid">{queryResult.floor}</span>
                  </span>
                </div>

                {queryResult.abstained ? (
                  <div className="flex items-center gap-2.5 rounded border-l-2 border-warning/50 bg-bg-900/40 px-4 py-3 text-sm text-text-mid">
                    <MinusCircle size={16} className="shrink-0 text-warning" />
                    No confident match found for this question in this corpus. Nothing scored above
                    the abstention floor, so no citation is shown rather than returning the nearest
                    irrelevant chunk.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {queryResult.citations.map((c, i) => (
                      <CitationCard key={c.chunk_id} citation={c} index={i} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {!queryResult && !queryError && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-text-lo">
                <FileText size={12} strokeWidth={1.6} />
                Ask a question against the selected corpus to see cited, verbatim results.
              </p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
