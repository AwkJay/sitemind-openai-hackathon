# Codebook — spec (2026-07-10)

## Goal
Extract SiteMind's standards/docs retrieval into its own service — **Codebook**
— that indexes manak-sourced structural codes, SiteMind's own verified
standards, and company-uploaded documents under one name, exposes itself as
an MCP server so any agent can query it, and adds a genuinely new capability:
check an uploaded document's requirements against the corpus with real
citations, not just retrieve chunks.

## Why
"manak" is a third-party dependency's name leaking into SiteMind's own product
vocabulary (23 files, including the citation `source_type` disclosure tag).
Consolidating retrieval into a named, agent-consumable service is also a real
Innovation/Scalability story for judges: "we didn't just consume manak, we
built our own standards-serving layer other agents can call."

## Grounding (confirmed before writing this spec)
- No live runtime call to manak exists today. The only "manak" references
  outside comments/docs are `schemas.py`'s `source_type` enum value
  (`"manak_verified"`) and comments in `agents/checks.py`. manak-dev is a
  build-time research tool (clause text extracted once into `clauses.json`)
  plus Phase 3b's read-only markdown file indexer
  (`backend/app/retrieval/filesystem_corpora.py`) — never a live MCP call at
  request time. So there is no running integration to "disconnect"; this is a
  rename + relocation of existing, already-eval-verified code.
- Phase 3/3b already built the hard part: `backend/app/retrieval/` —
  `chunker.py`, `index.py`, `embeddings_provider.py`, `filesystem_corpora.py`
  (manak_structural: 6,206 chunks/17 docs; sitemind_existing_standards: 29
  chunks/2 docs) — all passing `run_retrieval_eval.py` (24/24) and
  `run_cross_corpus_eval.py` (26/26). Codebook relocates and exposes this,
  it does not reinvent it.
- No `docker-compose`/`Dockerfile` exists anywhere in the repo today — this is
  currently two processes (FastAPI + Next.js), no containerization. Codebook
  will be a third process, run the same way (a `run.sh`-style script), not a
  container — consistent with the rest of the repo.
- No file named `BUILD_PLAN_CODEBOOK*` or any mention of "Codebook" /
  "standards-service" existed anywhere in the repo before this file.

## Decisions (what we settled, and the road not taken)
- **Separate service, same repo** (`standards-service/` or similarly named
  package) over an in-app page. Chosen because the requirement is "AI agents
  fetch and compare standards" — that needs an independent process with its
  own interface, not a page inside SiteMind's own app. Rejected: pure in-app
  module (too coupled to be independently agent-consumable); fully separate
  repo (unjustified overhead for a 1-2 week window with no reuse-outside-
  SiteMind need yet).
- **MCP-only public interface**, not REST. Mirrors exactly how manak-dev
  itself already works, and is the more genuinely agentic story. The
  browser-facing UI does **not** call Codebook directly — it goes through
  SiteMind's existing backend, which becomes an MCP client of Codebook (the
  same relationship SiteMind's own tooling already has with manak, just now a
  real live client instead of a build-time research tool). Avoids building
  and maintaining a second bespoke REST surface just for the UI.
- **"Compare" = generalized compliance-check-as-a-service**, not
  edition-diffing. Clarified by the user: given an uploaded document, reason
  about its requirements against the corpus and return real citations —
  effectively the Compliance Agent's own pattern (`agents/checks.py`:
  deterministic decision against a real fetched clause, LLM only writes
  prose), generalized into a reusable primitive any caller (QA bot, other
  agents, a human via the UI) can invoke against any corpus, not just the
  hardcoded design-basis-params pipeline. **Must follow the same
  non-negotiable rule as the rest of the project**: retrieval finds candidate
  clauses (RAG), a deterministic/grounded step decides conformance, the LLM
  only composes prose around a clause it was handed — never invents or
  paraphrases from memory.
- **Clause text stays read-only**; only metadata (tags, category, review
  flags) is editable through the UI. Protects the "never invent a clause"
  rule — a standard's actual text can never drift from its verified source
  through this tool.
- **Name: Codebook.** Plain English, no explanation needed to a judge panel,
  literally describes what it is.
- **Rename is two separate risk tiers**, done as two separate steps:
  - *Low-risk*: all user-facing labels, docs, README references — cosmetic,
    no schema/eval impact.
  - *Higher-risk*: the `source_type` enum value `"manak_verified"` in
    `schemas.py`/`clauses.json`/eval assertions. This is load-bearing for the
    held-out eval suite (structural baseline 10 checked/6 NCRs, n=41 eval,
    etc.) — renamed last, with the **full existing eval suite re-run
    before/after** to prove the baseline is unchanged, exactly like every
    other change this project has made to shared code.

## Scope
**In:**
1. New `standards-service/` package: own FastAPI process on a new port (not
   8000/8001, both already spoken for by manak-dev and SiteMind's backend —
   proposing 8010), reusing the chunker/index/embeddings-provider logic moved
   from `backend/app/retrieval/`.
2. Three corpora, ingested the same way Phase 3b already proved works:
   manak-sourced structural codes (file-based, read-only, never touches
   manak-dev), SiteMind's own existing standards (`clauses.json` +
   `commissioning_clauses.json`), and company-uploaded documents (persisted,
   same pattern as today's `backend/data/company_corpus/`).
3. Codebook's own MCP server exposing: `list_corpora`, `search_standards`,
   `get_clause`, `check_document_against_corpus` (the new reasoning
   capability).
4. SiteMind's existing backend becomes an MCP client of Codebook, behind a
   `CODEBOOK_ENABLED` flag (default off until verified — same pattern as
   `RETRIEVAL_ENABLED`).
5. A `/codebook` frontend page (new, or the existing `/knowledge-base` page
   rebranded) — browse corpora, search, upload, and run "check this
   document" — talking to SiteMind's backend, not Codebook directly.
6. Cosmetic rename pass: "manak" → "Codebook" in all SiteMind user-facing
   copy/docs (not manak-dev's own code, which we don't own).
7. The `source_type="manak_verified"` → `"codebook_verified"` (or similar)
   enum rename, done last, with a full eval-suite re-run proving the
   structural/electrical/extraction baselines are byte-identical apart from
   the renamed tag.
8. New held-out eval for Codebook's MCP tools + the
   `check_document_against_corpus` reasoning tool, reported separately, never
   blended into the existing eval count.

**Out (deliberately — revisit later if asked):**
- Cross-standard comparison (IS 3043 vs CEA regs on the same topic) — real
  but harder to get right in this window; edition-diff-style tooling wasn't
  actually what was asked for either (clarified: "compare" means
  document-vs-corpus, not standard-vs-standard).
- Fully editable clause text.
- Containerizing anything (no Dockerfile exists today; not introducing one
  just for this).
- A fully separate repo/CI for Codebook.
- Retiring/deleting `backend/app/retrieval/` — stays in place, untouched,
  until Codebook is built and its own eval passes. Only removed as an
  explicit last step, and only with a fresh go-ahead.
- Any change to manak-dev itself — read-only, always.

## Plan (ordered, smallest shippable first)
1. Scaffold `standards-service/` — own FastAPI app, own port, health check.
   No corpus logic yet.
2. Relocate (not rewrite) `chunker.py`, `embeddings_provider.py`, `index.py`,
   `filesystem_corpora.py`, `ingest.py`, `store.py`, `models.py` from
   `backend/app/retrieval/` into the new service. Re-run
   `run_retrieval_eval.py` / `run_cross_corpus_eval.py` against the relocated
   code to prove nothing broke in the move.
3. Add the MCP server layer on top: `list_corpora`, `search_standards`,
   `get_clause`. Verify each tool is independently callable (same HTTP-
   transport pattern already proven for manak).
4. Build `check_document_against_corpus` — the new reasoning primitive,
   deterministic-decision-plus-cited-LLM-prose, same architecture as
   `agents/checks.py`. This is the one genuinely new piece of logic in the
   whole plan; everything else above is relocation.
5. Wire SiteMind's backend as an MCP client of Codebook, behind
   `CODEBOOK_ENABLED` (default off).
6. New/rebranded frontend page wired to the client, both flag-on and
   flag-off states verified distinct (matches the existing disabled/
   unreachable pattern already used for `RETRIEVAL_ENABLED`).
7. Cosmetic rename pass (low-risk tier).
8. `source_type` enum rename (higher-risk tier) + full existing eval suite
   re-run, before/after diffed.
9. New Codebook eval script, reported separately.
10. Update `PROGRESS.md` / `docs/ARCHITECTURE.md` with the new component.

## Execution
One driving chat, sliced by the plan steps above — steps 1-4 are tightly
coupled (same new package, same files), so no parallel subagents writing
concurrently. Per this project's standing rule, **all implementation code is
written by dispatched Sonnet-5 sub-agents**, never hand-written by the
orchestrating model; subagents are also used for read-only verification
(re-running evals, confirming no accidental edits to manak-dev or existing
standards files) between steps.

## Risks / open questions
- Port choice for `standards-service/` (proposing 8010 — needs confirming
  free on the dev machine before build starts).
- The machine has hit real OOM kills before when running multiple heavy
  Python processes at once (confirmed via `dmesg` in a prior session) — a
  third concurrent process (Codebook) alongside the FastAPI backend and
  Next.js dev server raises that risk again during local testing. Will test
  incrementally, not all three at max load simultaneously, and note this if
  it recurs rather than fighting it silently.
- The `source_type` rename touches held-out eval assertions directly — if the
  full-suite re-run shows any drift, the rename is rolled back, not forced
  through.

## Done when
- [x] `standards-service/` runs standalone, own port, own health check.
- [x] All three corpora ingest with the same counts Phase 3b already proved
      (manak_structural: 17 docs/6,206 chunks; sitemind_existing_standards: 2
      docs/29 chunks) — confirms the relocation didn't change behavior.
- [x] `list_corpora`, `search_standards`, `get_clause` callable via MCP HTTP
      transport, verified live (not just unit-tested).
- [x] `check_document_against_corpus` returns real citations for a real
      uploaded doc, with zero fabricated clause text (spot-checked against
      source).
- [x] SiteMind backend flag-off → zero behavior change, zero new imports
      executed (same proof pattern as `RETRIEVAL_ENABLED`).
- [x] SiteMind backend flag-on → `/codebook` page works end-to-end: browse,
      search, upload, check-document.
- [x] Existing eval suite (structural, electrical, extraction, retrieval,
      cross-corpus, etc.) passes unchanged after the cosmetic rename.
- [x] `source_type` enum rename — **found not applicable, documented below,
      not silently skipped.** `clauses.json` (24 literal `"source_type":
      "manak_verified"` entries) lives under `backend/data/standards/`, and
      the only code reading it is `backend/app/standards.py` — both are on
      this project's non-negotiable never-modify list, which overrides this
      spec's own step 8 wording. Verified Codebook's own new code
      (`mcp_server.py`, `document_check.py`) never references
      `Citation.source_type`/`"manak_verified"` at all — it uses a separate,
      already-Codebook-native tag (`filesystem_readonly`/`company_upload`
      from the retrieval package). So there is nothing left in Codebook's own
      product surface to rename; the value stays permanently inside the
      protected, untouched Compliance Agent pipeline. No code changed, no
      eval re-run needed (nothing touched).
- [ ] New Codebook eval script passes, reported separately from all existing
      evals.
- [x] `manak-dev/` unmodified throughout (mtime/size diff check, same
      discipline as Phase 3b's `manak_untouched` eval group) — reconfirmed at
      every step via `run_cross_corpus_eval.py`'s `manak_untouched` group.

## Session checkpoint (2026-07-10, paused mid-build)

**Steps 1-7 done and independently verified** (each step's sub-agent claim was
spot-checked directly, not taken on faith — real `curl`/`grep`/`git status`/eval
re-runs from the orchestrating session, not just the sub-agent's own report).
**Steps 8-10 (tasks #13-15 in the TaskCreate list) are NOT started.**

Built so far:
- `standards-service/` — full new service, port 8010, `run.sh` boots it.
  `app/main.py`, `app/mcp_server.py` (4 MCP tools), `app/document_check.py`,
  `app/llm.py`, `app/config.py`, `app/retrieval/*` (7 relocated modules +
  router), `eval/run_retrieval_eval.py` (24/24), `eval/run_cross_corpus_eval.py`
  (26/26).
- `backend/app/codebook_client.py`, `backend/app/codebook_router.py` —
  SiteMind's backend as an MCP client, gated on `CODEBOOK_ENABLED` (default
  off) in `backend/app/config.py`. Mounted conditionally in `backend/app/main.py`.
- `frontend/app/codebook/page.tsx`, plus additions to `frontend/lib/api.ts`,
  `frontend/lib/types.ts`, and a new nav entry in `frontend/components/Shell.tsx`
  (`BookMarked` icon, distinct from Knowledge Base's `Library` icon).
- Cosmetic rename pass (step 7) done across: `backend/app/schemas.py` (comments
  only — the `"manak_verified"` literal itself is untouched, that's step 8),
  `backend/app/agents/checks.py`, `backend/app/commissioning.py`,
  `backend/app/commissioning_standards.py`, `backend/data/gen_synthetic.py`,
  `backend/data/README.md`, `backend/eval/run_electrical_eval.py`,
  `docs/ARCHITECTURE.md`, `frontend/lib/types.ts`, `frontend/lib/format.ts`
  (label/caveat text only, dict keys untouched), `frontend/components/CitedClauseBox.tsx`,
  `frontend/lib/mocks.ts`, `frontend/app/codebook/page.tsx`. Full 19-script
  backend eval suite re-run and confirmed byte-identical pass counts after this
  pass (structural 41/41, electrical 32/32, retrieval 24/24, cross-corpus
  26/26, etc.). `backend/app/standards.py`, `backend/data/standards/`, and
  `backend/app/retrieval/` (the original, pre-relocation copy) confirmed
  untouched throughout — `git diff --stat` on all three is empty.

**Next step when resuming: task #13 — step 8 from the plan above**, the
higher-risk `source_type` enum rename (`"manak_verified"` →
`"codebook_verified"` or similar) in `backend/app/schemas.py`,
`backend/data/standards/clauses.json`-referencing code, `frontend/lib/types.ts`,
`frontend/lib/format.ts`, `frontend/components/CitedClauseBox.tsx` — the exact
literal-value spots step 7 deliberately left alone. Requires a full eval-suite
re-run BEFORE and AFTER, diffed, with an explicit rollback if anything drifts
(per the spec's own risk note above). Then task #14 (new Codebook-specific
held-out eval script) and task #15 (update `PROGRESS.md`/`docs/ARCHITECTURE.md`).

**TaskCreate todo list**: tasks #6-12 marked `completed`, #13 marked
`in_progress` (not yet worked), #14-15 `pending`. Run `TaskList` on resume to
recover this state — it survives independently of this file.

**Live process state at pause time**: `standards-service` uvicorn dev server
was left running on port 8010 (`http://127.0.0.1:8010/health` →
`{"status":"ok","service":"codebook"}`) — harmless to leave running or kill,
just `run.sh` again if it's gone. Nothing else was left running (all backend/
frontend dev servers and eval processes started during verification were shut
down after use).

**Nothing has been committed to git.** All work above is uncommitted, matching
this project's "only commit when explicitly asked" rule — `git status --short`
at repo root shows the full uncommitted diff/untracked-file list, all expected
and scoped to this build.
