"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  Info,
  Library,
  Loader2,
  MinusCircle,
  Upload,
  WifiOff,
} from "lucide-react";
import {
  CodebookUnavailableError,
  getCodebookConsoleCorpora,
  getCodebookConsoleDocuments,
  uploadToCodebookConsole,
  type CodebookAvailability,
} from "@/lib/api";
import type {
  CodebookConsoleCorpus,
  CodebookConsoleDocument,
  CodebookConsoleUploadResult,
} from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Skeleton } from "@/components/ui/primitives";
import { codebookConsoleProvenanceMetaFor } from "@/lib/format";

const DEFAULT_UPLOAD_CORPUS = "sitemind_existing_standards";

function ProvenanceBadge({ tag }: { tag: string | null | undefined }) {
  const meta = codebookConsoleProvenanceMetaFor(tag);
  return (
    <span
      className="font-mono inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-wide"
      style={{ color: meta.color, background: meta.bg, border: `1px solid ${meta.color}40` }}
    >
      {meta.label}
    </span>
  );
}

function NotEnabledState({ availability }: { availability: CodebookAvailability }) {
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
            Codebook can&rsquo;t be reached right now. Either the SiteMind backend itself is
            unreachable, or the backend is up with{" "}
            <span className="font-mono text-text-hi">CODEBOOK_ENABLED=1</span> but Codebook&rsquo;s
            own process (<span className="font-mono text-text-hi">standards-service</span>, port{" "}
            <span className="font-mono text-text-hi">8010</span>) isn&rsquo;t running. Start it with{" "}
            <span className="font-mono text-text-hi">standards-service/run.sh</span> and confirm the
            backend&rsquo;s <span className="font-mono text-text-hi">API URL</span> is reachable.
          </>
        ) : (
          <>
            Codebook is not enabled on this backend. It&rsquo;s running with{" "}
            <span className="font-mono text-text-hi">CODEBOOK_ENABLED</span> off (the default), so
            none of the Codebook Console routes are mounted. Start the backend with{" "}
            <span className="font-mono text-text-hi">CODEBOOK_ENABLED=1</span> (and Codebook itself
            via <span className="font-mono text-text-hi">standards-service/run.sh</span>) to browse
            and manage corpora here.
          </>
        )}
      </p>
    </Card>
  );
}

// One corpus row, expandable to its own document list — fetched lazily the
// first time it's expanded, since a document list is a second real API call
// per corpus (never bundled speculatively into the corpora list response).
function CorpusRow({ corpus }: { corpus: CodebookConsoleCorpus }) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<CodebookConsoleDocument[] | null>(null);

  async function toggle() {
    const next = !expanded;
    setExpanded(next);
    if (next && docs === null && !loading) {
      setLoading(true);
      setError(null);
      try {
        const result = await getCodebookConsoleDocuments(corpus.corpus_name);
        setDocs(result);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load documents.");
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className="rounded border border-line bg-bg-900/40">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-bg-700/40"
      >
        <div className="flex min-w-0 items-center gap-2.5">
          {expanded ? (
            <ChevronDown size={14} className="shrink-0 text-text-lo" />
          ) : (
            <ChevronRight size={14} className="shrink-0 text-text-lo" />
          )}
          <Library size={14} className="shrink-0 text-text-lo" />
          <span className="truncate font-mono text-sm font-semibold text-text-hi">
            {corpus.corpus_name}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-xs text-text-lo">
            {corpus.document_count} doc{corpus.document_count === 1 ? "" : "s"} ·{" "}
            {corpus.chunk_count} chunk{corpus.chunk_count === 1 ? "" : "s"}
          </span>
          <ProvenanceBadge tag={corpus.provenance_tag} />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-line px-4 py-3">
          {loading && <Skeleton className="h-16 w-full" />}
          {error && (
            <p className="flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              {error}
            </p>
          )}
          {docs && docs.length === 0 && !loading && (
            <p className="flex items-center gap-1.5 text-xs text-text-lo">
              <Info size={12} strokeWidth={1.6} />
              No documents in this corpus.
            </p>
          )}
          {docs && docs.length > 0 && (
            <div className="space-y-1.5">
              {docs.map((d) => (
                <div
                  key={d.document_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded bg-bg-700/50 px-3 py-2"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <FileText size={13} className="shrink-0 text-text-lo" />
                    <span className="truncate font-mono text-[0.8rem] text-text-hi">
                      {d.filename ?? d.document_id}
                    </span>
                    <span className="shrink-0 text-[0.7rem] text-text-lo">
                      {d.chunk_count} chunk{d.chunk_count === 1 ? "" : "s"}
                      {d.structured ? " · structure-aware" : ""}
                    </span>
                  </div>
                  <ProvenanceBadge tag={d.provenance_tag} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CodebookConsolePage() {
  const [availability, setAvailability] = useState<CodebookAvailability>("checking");
  const [corpora, setCorpora] = useState<CodebookConsoleCorpus[]>([]);
  const [loading, setLoading] = useState(true);

  const [corpusInput, setCorpusInput] = useState(DEFAULT_UPLOAD_CORPUS);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<CodebookConsoleUploadResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const { corpora: list, availability: a } = await getCodebookConsoleCorpora();
    setAvailability(a);
    setCorpora(list);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleUpload(file: File) {
    const corpusName = corpusInput.trim() || DEFAULT_UPLOAD_CORPUS;
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const result = await uploadToCodebookConsole(file, corpusName);
      setUploadResult(result);
      await refresh();
    } catch (e) {
      if (e instanceof CodebookUnavailableError) {
        setAvailability(e.message.includes("not enabled") ? "disabled" : "unreachable");
      }
      setUploadError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const showNotEnabled = availability === "disabled" || availability === "unreachable";

  return (
    <div>
      <PageHeader
        eyebrow="Codebook Console"
        title="Corpora & documents"
        subtitle="Browse every corpus Codebook has indexed — internal verified standards and externally-uploaded company documents alike — and add new documents into any corpus. Real structured JSON from Codebook's own REST retrieval API, not MCP prose."
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
          {/* Corpora list */}
          <Card className="px-5 py-4">
            <Overline>Corpora</Overline>
            <p className="mt-1 text-sm text-text-mid">
              Each corpus is tagged{" "}
              <span className="font-mono text-text-hi">codebook_verified</span> /{" "}
              <span className="font-mono text-text-hi">sitemind_indexed</span> (internal verified
              standard, green) or <span className="font-mono text-text-hi">company_uploaded</span>{" "}
              (external / uploaded, amber) — but a corpus can be mixed, so the badge shown per
              document below is the authoritative one, not the corpus-level summary. Expand a row
              to see its documents.
            </p>
            <div className="mt-3 space-y-2">
              {loading && corpora.length === 0 ? (
                <Skeleton className="h-16 w-full" />
              ) : corpora.length === 0 ? (
                <p className="flex items-center gap-1.5 text-xs text-text-lo">
                  <Info size={12} strokeWidth={1.6} />
                  No corpora indexed yet.
                </p>
              ) : (
                corpora.map((c) => <CorpusRow key={c.corpus_name} corpus={c} />)
              )}
            </div>
          </Card>

          {/* Upload */}
          <Card className="px-5 py-4">
            <Overline>Add a document</Overline>
            <p className="mt-1 text-sm text-text-mid">
              Uploads always land tagged{" "}
              <span className="font-mono text-text-hi">company_uploaded</span> (external / uploaded)
              — Codebook&rsquo;s own convention, never presented as an internal verified standard.
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
              <input
                value={corpusInput}
                onChange={(e) => setCorpusInput(e.target.value)}
                placeholder={DEFAULT_UPLOAD_CORPUS}
                list="console-corpus-options"
                className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <datalist id="console-corpus-options">
                {corpora.map((c) => (
                  <option key={c.corpus_name} value={c.corpus_name} />
                ))}
              </datalist>
            </div>

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
                <span className="font-mono text-text-hi">
                  {corpusInput.trim() || DEFAULT_UPLOAD_CORPUS}
                </span>
              </p>
              {uploading && (
                <div className="mt-1 flex items-center gap-2 text-xs text-text-mid">
                  <Loader2 size={14} className="animate-spin text-accent" /> Uploading…
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
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>
                      <span className="font-mono text-text-hi">{uploadResult.chunk_count}</span>{" "}
                      chunk{uploadResult.chunk_count === 1 ? "" : "s"} indexed
                    </span>
                    <ProvenanceBadge tag={uploadResult.provenance_tag} />
                  </div>
                </div>
              </div>
            )}

            {!uploadResult && !uploadError && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-text-lo">
                <CheckCircle2 size={12} strokeWidth={1.6} />
                Upload a document to see it appear in the corpora list above.
              </p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
