"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  BookMarked,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  Info,
  Loader2,
  MinusCircle,
  RefreshCw,
  Search,
  WifiOff,
} from "lucide-react";
import {
  checkDocumentAgainstCodebook,
  CodebookUnavailableError,
  getCodebookClause,
  getCodebookCorpora,
  searchCodebook,
  type CodebookAvailability,
} from "@/lib/api";
import type {
  CodebookCheckResult,
  CodebookClauseResult,
  CodebookCorporaResult,
  CodebookSearchResult,
} from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Button, Card, Overline, Skeleton } from "@/components/ui/primitives";

// A real, on-disk example document worth checking against a corpus (see
// backend/data/project_docs/live_upload_samples/ — the same live-upload demo
// docs the rest of the app already uses). This is only ever a placeholder,
// never auto-submitted: check_document_against_corpus reads a path off
// Codebook's OWN host filesystem, not an uploaded file (see
// standards-service/app/mcp_server.py's check_document_against_corpus
// docstring for why it's a path, not a payload).
const EXAMPLE_DOCUMENT_PATH =
  "sitemind/backend/data/project_docs/live_upload_samples/DC1-16-DBR-0201-R0_Generator-Earthing-Addendum.docx";
const EXAMPLE_CORPUS = "sitemind_existing_standards";

// ── One rendered text block from a Codebook MCP tool call, styled to match
// the CitationCard visual language used on /knowledge-base (accent-left
// bordered box on bg-bg-700) — adapted, not copy-pasted, because Codebook's
// REST facade returns ONE prose block per call rather than a list of
// structured citations (see lib/types.ts's Codebook*Result comment for why:
// re-parsing that prose into fields client-side would risk silently
// drifting from what Codebook actually said, the same discipline
// codebook_client.py itself follows server-side). ─────────────────────────
function ResultBlock({
  label,
  meta,
  text,
  accent = "var(--accent)",
}: {
  label: string;
  meta?: ReactNode;
  text: string;
  accent?: string;
}) {
  return (
    <div className="relative rounded bg-bg-700 px-4 py-3" style={{ borderLeft: `3px solid ${accent}` }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className="font-mono inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider"
          style={{ color: accent, background: `${accent}1f`, border: `1px solid ${accent}40` }}
        >
          ◢ {label}
        </span>
        {meta}
      </div>
      <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-[0.8rem] leading-relaxed text-text-mid">
        {text}
      </pre>
    </div>
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
            none of the Codebook routes are mounted. Start the backend with{" "}
            <span className="font-mono text-text-hi">CODEBOOK_ENABLED=1</span> (and Codebook itself
            via <span className="font-mono text-text-hi">standards-service/run.sh</span>) to browse,
            search, and check documents here.
          </>
        )}
      </p>
    </Card>
  );
}

export default function CodebookPage() {
  const [availability, setAvailability] = useState<CodebookAvailability>("checking");

  const [corporaLoading, setCorporaLoading] = useState(true);
  const [corporaResult, setCorporaResult] = useState<CodebookCorporaResult | null>(null);

  const [query, setQuery] = useState("");
  const [searchCorpus, setSearchCorpus] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<CodebookSearchResult | null>(null);

  const [clauseDocId, setClauseDocId] = useState("");
  const [clauseChunkId, setClauseChunkId] = useState("");
  const [clauseLoading, setClauseLoading] = useState(false);
  const [clauseError, setClauseError] = useState<string | null>(null);
  const [clauseResult, setClauseResult] = useState<CodebookClauseResult | null>(null);

  const [checkPath, setCheckPath] = useState("");
  const [checkCorpus, setCheckCorpus] = useState("");
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [checkResult, setCheckResult] = useState<CodebookCheckResult | null>(null);

  const noteUnavailable = useCallback((e: unknown) => {
    if (e instanceof CodebookUnavailableError) {
      setAvailability(e.message.includes("not enabled") ? "disabled" : "unreachable");
    }
  }, []);

  const refreshCorpora = useCallback(async () => {
    setCorporaLoading(true);
    const { result, availability: a } = await getCodebookCorpora();
    setAvailability(a);
    setCorporaResult(result);
    setCorporaLoading(false);
  }, []);

  useEffect(() => {
    refreshCorpora();
  }, [refreshCorpora]);

  async function handleSearch() {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setSearchError(null);
    setSearchResult(null);
    try {
      const result = await searchCodebook(q, searchCorpus.trim() || undefined);
      setSearchResult(result);
      setAvailability("available");
    } catch (e) {
      noteUnavailable(e);
      setSearchError(e instanceof Error ? e.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  async function handleClause() {
    const docId = clauseDocId.trim();
    const chunkId = clauseChunkId.trim();
    if (!docId || !chunkId) return;
    setClauseLoading(true);
    setClauseError(null);
    setClauseResult(null);
    try {
      const result = await getCodebookClause(docId, chunkId);
      setClauseResult(result);
      setAvailability("available");
    } catch (e) {
      noteUnavailable(e);
      setClauseError(e instanceof Error ? e.message : "Clause lookup failed.");
    } finally {
      setClauseLoading(false);
    }
  }

  async function handleCheck() {
    const path = checkPath.trim();
    const corpus = checkCorpus.trim();
    if (!path || !corpus) return;
    setChecking(true);
    setCheckError(null);
    setCheckResult(null);
    try {
      const result = await checkDocumentAgainstCodebook(path, corpus);
      setCheckResult(result);
      setAvailability("available");
    } catch (e) {
      noteUnavailable(e);
      setCheckError(e instanceof Error ? e.message : "Check failed.");
    } finally {
      setChecking(false);
    }
  }

  const showNotEnabled = availability === "disabled" || availability === "unreachable";

  return (
    <div>
      <PageHeader
        eyebrow="Standards-serving layer (Codebook)"
        title="Codebook"
        subtitle="Codebook is a separate, MCP-serving process (standards-service) indexing digitised structural codes, SiteMind's own verified standards, and company-uploaded documents. SiteMind's backend is an MCP client of it — every result below is real, verbatim text Codebook returned, never re-typeset or reparsed client-side."
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
          {/* Corpora */}
          <Card className="px-5 py-4">
            <div className="flex items-center justify-between gap-2">
              <Overline>Indexed corpora</Overline>
              <button
                type="button"
                onClick={refreshCorpora}
                disabled={corporaLoading}
                className="flex items-center gap-1.5 text-xs text-text-lo transition-colors hover:text-text-hi disabled:opacity-50"
              >
                <RefreshCw size={12} className={corporaLoading ? "animate-spin" : ""} strokeWidth={1.6} />
                Refresh
              </button>
            </div>
            <p className="mt-1 text-sm text-text-mid">
              Live corpus metadata straight from Codebook&rsquo;s own registry — <code className="font-mono text-text-hi">manak_structural</code>,{" "}
              <code className="font-mono text-text-hi">sitemind_existing_standards</code>, and any{" "}
              <code className="font-mono text-text-hi">company_upload</code> corpora — with real document/chunk
              counts, never hardcoded.
            </p>
            <div className="mt-3">
              {corporaLoading && !corporaResult ? (
                <Skeleton className="h-20 w-full" />
              ) : corporaResult ? (
                <ResultBlock label="list_corpora" text={corporaResult.text} />
              ) : (
                <p className="flex items-center gap-1.5 text-xs text-text-lo">
                  <Info size={12} strokeWidth={1.6} />
                  No response yet.
                </p>
              )}
            </div>
          </Card>

          {/* Search */}
          <Card className="px-5 py-4">
            <Overline>Search standards</Overline>
            <p className="mt-1 text-sm text-text-mid">
              Ranked, verbatim chunks for a query — hybrid BM25 + dense retrieval, the exact same index
              Codebook&rsquo;s <code className="font-mono text-text-hi">search_standards</code> tool uses for any
              agent. A query too weak to confidently match anything abstains rather than returning the nearest
              irrelevant chunk.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSearch();
              }}
              className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center"
            >
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g. minimum cover for footings"
                className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <input
                value={searchCorpus}
                onChange={(e) => setSearchCorpus(e.target.value)}
                placeholder="corpus (optional, e.g. manak_structural)"
                className="w-full rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none sm:w-64"
              />
              <Button type="submit" disabled={searching || !query.trim()}>
                {searching ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                Search
              </Button>
            </form>

            {searchError && (
              <p className="mt-3 flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {searchError}
              </p>
            )}

            {searchResult && (
              <div className="mt-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-text-lo">
                  <span>
                    query <span className="font-mono text-text-mid">&ldquo;{searchResult.query}&rdquo;</span>
                  </span>
                  <span>·</span>
                  <span>
                    corpus <span className="font-mono text-text-mid">{searchResult.corpus_name ?? "all loaded"}</span>
                  </span>
                  <span>·</span>
                  <span>
                    k <span className="font-mono text-text-mid">{searchResult.k}</span>
                  </span>
                </div>
                <ResultBlock label="search_standards" text={searchResult.text} accent="var(--data)" />
              </div>
            )}

            {!searchResult && !searchError && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-text-lo">
                <FileSearch size={12} strokeWidth={1.6} />
                Search a corpus to see cited, verbatim results.
              </p>
            )}
          </Card>

          {/* Get a specific clause */}
          <Card className="px-5 py-4">
            <Overline>Look up a clause</Overline>
            <p className="mt-1 text-sm text-text-mid">
              Re-fetch one chunk&rsquo;s exact, byte-identical text by the{" "}
              <span className="font-mono text-text-hi">document_id</span>/<span className="font-mono text-text-hi">chunk_id</span> pair
              shown on a search result above — e.g. to re-verify a citation later without re-running the search.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleClause();
              }}
              className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center"
            >
              <input
                value={clauseDocId}
                onChange={(e) => setClauseDocId(e.target.value)}
                placeholder="document_id, e.g. is456_2000"
                className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <input
                value={clauseChunkId}
                onChange={(e) => setClauseChunkId(e.target.value)}
                placeholder="chunk_id, e.g. is456_2000:0042"
                className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <Button type="submit" disabled={clauseLoading || !clauseDocId.trim() || !clauseChunkId.trim()}>
                {clauseLoading ? <Loader2 size={15} className="animate-spin" /> : <BookMarked size={15} />}
                Fetch
              </Button>
            </form>

            {clauseError && (
              <p className="mt-3 flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {clauseError}
              </p>
            )}

            {clauseResult && (
              <div className="mt-4">
                <ResultBlock label="get_clause" text={clauseResult.text} accent="var(--pass)" />
              </div>
            )}
          </Card>

          {/* Check a document against a corpus */}
          <Card className="px-5 py-4">
            <Overline>Check a document against a corpus</Overline>
            <p className="mt-1 text-sm text-text-mid">
              Codebook&rsquo;s own reasoning primitive: extracts candidate requirement sentences from a document
              and deterministically decides CONFORMS / NON_CONFORM / NEEDS_REVIEW against the best-matched real
              clause per sentence — never an LLM decision, never a fabricated clause.
            </p>
            <p className="mt-2 flex items-start gap-1.5 text-[0.78rem] leading-snug text-text-lo">
              <Info size={12} className="mt-0.5 shrink-0" />
              <span>
                <span className="font-mono text-text-hi">document_path</span> must be a file already readable on{" "}
                <span className="font-mono text-text-hi">standards-service</span>&rsquo;s own host filesystem —
                this is a path, not a browser file upload (Codebook is a same-host MCP server, not a document
                store; see <span className="font-mono text-text-hi">check_document_against_corpus</span>&rsquo;s
                own docstring). Example: <span className="font-mono text-text-hi">{EXAMPLE_DOCUMENT_PATH}</span>
              </span>
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleCheck();
              }}
              className="mt-3 flex flex-col gap-2"
            >
              <input
                value={checkPath}
                onChange={(e) => setCheckPath(e.target.value)}
                placeholder={EXAMPLE_DOCUMENT_PATH}
                className="w-full rounded border border-line bg-bg-900 px-4 py-2.5 font-mono text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
              />
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  value={checkCorpus}
                  onChange={(e) => setCheckCorpus(e.target.value)}
                  placeholder={`corpus_name, e.g. ${EXAMPLE_CORPUS}`}
                  className="flex-1 rounded border border-line bg-bg-900 px-4 py-2.5 text-sm text-text-hi placeholder:text-text-lo focus:border-accent focus:outline-none"
                />
                <Button
                  type="submit"
                  disabled={checking || !checkPath.trim() || !checkCorpus.trim()}
                >
                  {checking ? <Loader2 size={15} className="animate-spin" /> : <ClipboardCheck size={15} />}
                  Run check
                </Button>
              </div>
            </form>

            {checkError && (
              <p className="mt-3 flex items-start gap-1.5 text-[0.78rem] leading-snug text-critical">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                {checkError}
              </p>
            )}

            {checkResult && (
              <div className="mt-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-text-lo">
                  <span>
                    document <span className="font-mono text-text-mid">{checkResult.document_path}</span>
                  </span>
                  <span>·</span>
                  <span>
                    corpus <span className="font-mono text-text-mid">{checkResult.corpus_name}</span>
                  </span>
                </div>
                <ResultBlock label="check_document_against_corpus" text={checkResult.text} accent="var(--warning)" />
              </div>
            )}

            {!checkResult && !checkError && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-text-lo">
                <CheckCircle2 size={12} strokeWidth={1.6} />
                Run a check to see real per-sentence findings, each citing a real matched clause or an honest
                abstention.
              </p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
