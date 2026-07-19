# Codebook — corrected rename + self-containment plan (2026-07-12)

## Why this file exists
`BUILD_PLAN_CODEBOOK.md`'s own "Done when" checklist has a wrong checked-off
box: it claims "there is nothing left in Codebook's own product surface to
rename," but Codebook's *own* retrieval package (relocated from
`backend/app/retrieval/` into `standards-service/`) still has two literal
"manak" names in it that the original rename pass (step 7) never touched.
This file is the corrected follow-up plan, decided with the user 2026-07-12
(grill-me, full mode) — covers that gap plus 3 adjacent findings from the
same session.

## What's being fixed (5 items, decided this session)

1. **Rename `manak_indexed` → `codebook_verified`** — `standards-service`'s
   own `retrieval/models.py` `SourceType` literal, and every place it's set:
   `filesystem_corpora.py`, `mcp_server.py` disclosure strings,
   `router.py` comments.
2. **Rename `manak_structural` → `codebook_structural`** — the corpus NAME
   constant (`MANAK_CORPUS_NAME` in `filesystem_corpora.py`), same call
   sites as above. This is what `list_corpora` actually returns to any live
   caller today.
3. **Rename `manak_verified` → `codebook_verified`** — the PROTECTED
   Compliance Agent tag: `backend/app/schemas.py` `Citation.source_type`
   literal, `backend/data/standards/clauses.json` (24 literal occurrences),
   `frontend/lib/types.ts`, `frontend/lib/format.ts`,
   `frontend/components/CitedClauseBox.tsx`, and the top-level
   `.claude/CLAUDE.md` project instructions (which currently cite this
   exact string). Full 19-script backend eval suite re-run BEFORE and
   AFTER, byte-diffed pass counts, explicit rollback if anything drifts —
   per `BUILD_PLAN_CODEBOOK.md`'s own risk note for this exact literal.
   **⚠ Naming collision, flagged not hidden**: after items 1 and 3, both
   literals are the string `"codebook_verified"`, living in two separate,
   never-compared `Literal` types (Codebook's own retrieval package vs. the
   Compliance Agent's `Citation` model) — same string, different meaning
   (item 1 = "mirrored into Codebook's structural corpus"; item 3 =
   "verified against the real manak-sourced digitised standard"). Confirmed
   intentional with the user 2026-07-12 — not a bug, just worth remembering
   when reading logs/JSON that span both services.
4. **Copy `manak-dev/lib`'s 17 `.md` files into this repo**
   (`standards-service/data/structural_corpus/`) and point
   `filesystem_corpora.py`'s path constant at the new in-repo location,
   removing the hardcoded external absolute path
   (`/home/awni/Documents/Project_hackathon/manak-dev/lib`). One-time copy;
   `manak-dev/` itself is never modified, and its mtime/size are diffed
   after to prove that. Corrects `BUILD_PLAN_CODEBOOK.md`'s Grounding
   section, which assumed this read only ever happened at build time — it
   actually happens lazily on Codebook's first request, every process
   start.
5. **Real upload widget on `/codebook`'s Document-check panel** — it
   currently takes a raw filesystem path (`checkPath` state in
   `frontend/app/codebook/page.tsx`), which only works because Codebook and
   the demo machine are the same host. Add a real file picker / drag-drop
   that POSTs multipart to a **new** backend endpoint
   (`POST /api/codebook/check-upload`), which saves the uploaded bytes to a
   shared temp path (backend + Codebook are same-host sibling processes in
   this deployment) and calls the existing `check_document_against_corpus`
   MCP tool with that path. No new Codebook-side logic — reuses the tool
   exactly as-is.

## Order (smallest/lowest-risk first, most-coupled/highest-risk last)
1. **Item 5** (upload widget) — fully additive, zero risk to existing
   behavior, no shared literals touched.
2. **Item 4** (copy `manak-dev` files in) — additive + one path constant
   change, still zero risk to protected files.
3. **Items 1 + 2** (retrieval package renames) — internal to
   `standards-service`, no protected/eval-tracked files touched. Verify via
   `run_retrieval_eval.py` (24/24) + `run_cross_corpus_eval.py` (26/26)
   after.
4. **Item 3** (protected `schemas.py` rename) — LAST, by far the highest
   risk. Full 19-script eval baseline captured before touching anything;
   re-run after; diffed; roll back immediately if anything drifts, rather
   than debugging live.

## Execution model
Per `BUILD_PLAN_CODEBOOK.md`'s own standing rule for this project: **all
implementation code is written by dispatched subagents, never hand-written
by the orchestrating model.** This plan follows that exactly — each step
above is one dispatched agent doing the edit, then the orchestrating
session independently re-verifies (re-running the real eval scripts,
grepping for leftover literals, diffing `manak-dev/`'s mtimes) before moving
to the next step. Same discipline `BUILD_PLAN_CODEBOOK.md`'s own checkpoint
log describes for steps 1-7.

## Done when
- [ ] `/codebook` Document-check panel accepts a real uploaded file (not
      just a path), end-to-end verified against a real sample doc.
- [ ] `manak-dev/lib`'s 17 files copied in; `filesystem_corpora.py`'s path
      constant points at the in-repo copy; external absolute-path
      dependency removed; `manak-dev/` itself confirmed byte-for-byte
      untouched (mtime/size diff).
- [ ] `grep -ri "manak_indexed\|manak_structural"` across `standards-service/`
      + `backend/` returns zero hits outside historical docs/comments.
- [ ] `run_retrieval_eval.py` 24/24 and `run_cross_corpus_eval.py` 26/26,
      unchanged, after items 1/2/4.
- [ ] `grep -ri "manak_verified"` across `backend/`, `frontend/`, and
      `.claude/CLAUDE.md` returns zero hits (all now `codebook_verified`).
- [ ] Full backend eval suite (all scripts under `backend/eval/run_*.py` —
      exact list confirmed via `ls` at execution time, expected ~19
      scripts) passes with byte-identical pass counts before and after item
      3.
- [ ] `git status` reviewed — nothing under `manak-dev/` shows as modified.
- [ ] `PROGRESS.md` updated with this pass's outcome.

## Risks
- Item 3 (protected rename) is the one genuine regression risk in this
  whole plan — if the full eval suite shows ANY drift afterward, roll back
  immediately rather than force it through, per the project's own standing
  "never silently change the tracked baseline" rule.
- This machine has hit real OOM kills before running multiple heavy Python
  processes concurrently (noted in `BUILD_PLAN_CODEBOOK.md`'s own risk log)
  — eval runs are sequenced, not run alongside live dev servers.

## Session note (2026-07-12)
User is stepping away and gave explicit go-ahead to execute this whole plan
autonomously in this session, in the order above, using dispatched
subagents per the execution model — no further approval gate between steps
unless something in "Risks" above actually triggers (in which case: stop,
document what happened here, don't force it through).
