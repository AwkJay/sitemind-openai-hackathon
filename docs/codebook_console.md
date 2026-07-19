# Codebook Console — spec (2026-07-12)

## Why this file exists
Follow-up to `docs/codebook_changes.md`. The user asked (via `/grill-me full`)
whether to build a separate document-management service with its own UI,
distinguishing internal standards from externally-uploaded documents, and to
pick a new brand name away from "manak". Grounded answer, decided with the
user this session:

- **A separate service already exists** (`standards-service`, port 8010,
  "Codebook") and **a rename already happened** (`git log`:
  `c603097 Rename manak to Codebook in frontend`, `c513318 ... in backend`,
  both before this session). No new service, no new name needed.
- What's actually missing is a browsing/management **UI** on top of the
  already-separate service, and a visible internal-vs-external provenance
  signal. That's this spec.
- User approved (AskUserQuestion, this session): build the lightweight
  console now, in this session, via dispatched subagents.
- **Correction recorded**: an earlier draft of this plan proposed also
  deleting `backend/app/retrieval/` as "dead code." Verified false before
  acting — `backend/eval/run_retrieval_eval.py` and `run_cross_corpus_eval.py`
  import from it directly, and `main.py` still flag-mounts it
  (`RETRIEVAL_ENABLED`). **Not touched by this plan.**

## What's being built
A new page, **Codebook Console**, reachable from the existing `/codebook`
page (a nav link/tab), showing:
1. **Corpora list** — name, document count, chunk count, and a provenance
   badge per corpus (`codebook_verified`/`sitemind_indexed` → "Internal
   verified standard", green; `company_uploaded` → "External / uploaded",
   amber). Real data, not mocked.
2. **Per-corpus document list** (expand a corpus row) — filename, chunk
   count, provenance badge per document (a corpus can be "mixed" even if
   `CorpusSummary.provenance_tag` is a single value — the per-document tag is
   the authoritative one).
3. **Add a document** — drag-and-drop (or file picker) + a corpus-name
   input, uploads into the chosen corpus. Same interaction pattern as the
   upload widget already built for `/codebook`'s Document-check panel this
   session (reuse, don't reinvent).

## Why this doesn't touch standards-service at all
`standards-service/app/retrieval/router.py` **already exposes** everything
needed, unconditionally (confirmed by reading it this session):
- `GET /api/retrieval/corpora` → `list[CorpusSummary]` (name, document_count,
  chunk_count, source, provenance_tag) — structured JSON, not MCP prose.
- `GET /api/retrieval/corpora/{name}/documents` → `list[dict]` (document_id,
  filename, chunk_count, structured, provenance_tag).
- `POST /api/retrieval/upload` (`corpus_name` form field + `file`) →
  `IngestManifest`, tagged `provenance_tag="company_uploaded"` automatically.

So this build is 100% additive on the `backend/` + `frontend/` side — no
standards-service change, no risk to its eval suite.

## What's being added
1. **`backend/app/codebook_router.py`** — 3 new proxy endpoints, following
   the exact existing `_call()`/503-translation pattern already in this
   file, but hitting standards-service's plain REST retrieval API via
   `httpx` (NOT the MCP client — those 3 REST endpoints return structured
   JSON already; going through MCP would mean re-parsing prose back into
   fields, which `codebook_client.py`'s own docstring says never do):
   - `GET /api/codebook/console/corpora`
   - `GET /api/codebook/console/corpora/{name}/documents`
   - `POST /api/codebook/console/upload` (multipart passthrough)
   New small helper (inline in the router or a `codebook_rest_client.py`
   sibling to `codebook_client.py`) using `httpx.AsyncClient` against
   `config.CODEBOOK_MCP_URL`'s host (same host, different path — reuse the
   config value, don't add a second URL setting). Same `CodebookUnavailable`
   → 503 translation as the MCP-backed endpoints.
2. **`frontend/lib/api.ts`** — 3 matching client functions
   (`getCodebookConsoleCorpora`, `getCodebookConsoleDocuments`,
   `uploadToCodebookConsole`), same error-handling conventions as the
   existing Codebook functions in this file.
3. **`frontend/lib/types.ts`** — matching result types
   (`CodebookConsoleCorpus`, `CodebookConsoleDocument`) mirroring
   standards-service's `CorpusSummary`/document-list shape exactly (real
   fields, not guessed).
4. **`frontend/app/codebook/console/page.tsx`** (new route) — the console UI
   described above, built from this project's existing primitives (`Card`,
   `Overline`, `Button`, `Skeleton`, `PageHeader` from
   `frontend/components/ui/primitives` / `PageHeader`), matching
   `/codebook`'s existing visual language (same accent-bordered `ResultBlock`
   style, same `NotEnabledState` for when Codebook is off/unreachable —
   reuse that exact component via a shared import, don't duplicate it).
5. **`frontend/app/codebook/page.tsx`** — add one link/button in the page
   header to the new `/codebook/console` route.

## Provenance badge mapping (real, not decorative)
| `provenance_tag` value | Badge label | Color |
|---|---|---|
| `codebook_verified` | Internal verified standard | green (`--pass`) |
| `sitemind_indexed` | Internal verified standard | green (`--pass`) |
| `company_uploaded` | External / uploaded | amber (`--warning`) |
| anything else / null | Unknown provenance | gray (`--text-lo`) |

This reuses the exact same 3-tier concept already shipped for Compliance
citations (`source_type`) — same trust framing, extended to Codebook's own
corpus browser.

## Execution model
Per this project's standing convention: implementation is written by a
dispatched subagent, not hand-written by the orchestrating model. One
subagent does backend + frontend together (the two halves are coupled: the
frontend types must match the backend's actual response shape), then the
orchestrating session independently verifies:
- `curl` the 3 new backend endpoints live against a running stack.
- `grep` confirms `frontend/app/codebook/console/page.tsx` imports the new
  api.ts functions and renders real data, not a stub.
- Existing 18-script backend eval suite + `run_retrieval_eval.py`/
  `run_cross_corpus_eval.py` re-run, byte-identical pass counts (this build
  touches `codebook_router.py`, not `app/retrieval/`, so should be a no-op
  for these, but verify rather than assume).

## Explicitly out of scope (this pass)
- No auth/RBAC on who can upload (matches the rest of this hackathon demo's
  security posture — single-tenant, local/offline-first).
- No delete/edit of an already-indexed document — view + add only.
- No new brand name, no new service, no touching standards-service's own
  code.
- No changes to `backend/app/retrieval/` (confirmed still live, not dead).

## Done when
- [ ] `/codebook/console` renders real corpora + documents from a live
      backend, with correct provenance badges per the table above.
- [ ] Drag-and-drop (or file picker) upload adds a document to a chosen
      corpus and it appears in the list on refresh — verified with a real
      small `.txt`/`.md` file, not just claimed.
- [ ] All 3 new backend endpoints return clean 503s (not tracebacks) when
      Codebook/standards-service is down — verified by stopping the process
      once and hitting each endpoint.
- [ ] Full backend eval suite unchanged (byte-identical pass counts).
- [ ] `PROGRESS.md` updated with outcome.
