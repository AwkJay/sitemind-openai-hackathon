# SiteMind — feature inventory (as of 2026-07-12)

Grounded snapshot of every page and feature actually built, for a later critical pass (what's
weak, what's demo theater, what's missing). Not a spec, not a roadmap — a mirror of current code.
Compiled by reading every frontend page and every backend router directly; see file paths inline.

---

## 1. Command Center (`/`, `frontend/app/page.tsx`)
ROI/status dashboard aggregating every pillar. Read-only, no inputs.
- Machine-scale strip: docs read, clauses checked, cross-refs found, conflicts surfaced.
- "Next decisions" — ranked action list merging supply-chain + schedule risks (client-side ranking only).
- "Latest on site" — top-5 most recent Timeline events.
- Cost-at-risk card — total INR + component breakdown, hover tooltips.
- Cumulative impact — issues caught, engineer-hours saved, rework avoided (INR).
- Per-pillar ROI breakdown with links out.
- 3-card row: open NCRs by severity, schedule health, recent submittals/RFIs.
- Backend: `GET /api/overview`, `/api/cost-risk`, `/api/schedule/risks`, `/api/documents`, `/api/timeline`, `/api/supply-chain/risks`.

## 2. Compliance Agent — HERO (`/compliance`, `backend/app/agents/compliance.py`)
Reads a Design Basis doc, extracts params with source spans, checks each against a real cited
IS clause, emits NCRs + a senior ADVISORY.
- Document register with status legend, upload (PDF/DOCX/TXT/MD, click-to-browse).
- Extracted-parameters preview after upload.
- Live SSE-streamed agent reasoning trace (falls back to simulated stream if backend unreachable).
- Results: coverage-by-domain chips, overlapping-requirements panel (multi-clause governance),
  NCR cards, Action Brief cards (finding → linked RFI/schedule activity → owner action),
  conforming-parameter list.
- Backend: `POST /ingest` (real extraction, no mock fallback), `POST /check/stream` (SSE),
  `POST /check` (non-streamed), `GET /action-brief/{document_id}`.
- Decision logic is deterministic Python (`app/agents/checks.py`) against real clauses; LLM only
  writes prose and is handed the clause to cite.

## 3. Project/RFI Copilot (`/copilot`, `backend/app/agents/copilot.py`)
Cited hybrid-RAG Q&A over project docs/standards, plus "seen-before RFI" detection.
- Chat thread, hoverable `[n]` citation chips, per-answer sources list.
- "Seen before" card when a semantically similar resolved RFI is found.
- Suggestion chips (auto-asks the first on load), "try also" row, explicit abstention disclosure.
- Backend: `POST /ask` — curated fixture match first (keyword + embedding confirm), else hybrid
  BM25+dense retrieval with RRF fusion and an abstention floor; offline mode uses a deterministic
  fallback composer instead of an LLM call.

## 4. Schedule & Risk (`/schedule`, `backend/app/schedule.py`)
CPM + leading-indicator rules (not fabricated-data ML), weather/workforce risk factors.
- WBS gantt (baseline vs. predicted-slip overlay, "today" line, hover tooltips) — read-only.
- "Biggest early warning this cycle" hero card.
- Top schedule risks: drivers, downstream activities, project-impact days (re-run CPM),
  3-option Mitigation panel (viable/not-viable + days recovered per option).
- Backend: `GET /gantt`, `/risks` (NetworkX forward/backward CPM pass + 5 leading-indicator rules:
  slipping vendor, progress lag, legacy monsoon proxy, cited IMD monsoon window, cited Pongal
  workforce window), `/methodology` (discloses how each risk input is grounded).

## 5. Project Timeline (`/timeline`, `backend/app/timeline.py`)
Cross-pillar chronological aggregation — explicitly "aggregation only, no new judgment" (banner
shown in-page).
- 5-lane chart (compliance, copilot, schedule, supply_chain, commissioning), day axis, phase
  boundaries, "today" marker, severity-colored dots (jittered on same-day collision).
- Click a dot → SVG connector lines to its linked events (reuses `evidence_links.py`'s real
  shared-key matches) + detail card + "open in {pillar}" link.
- Backend: `GET /api/timeline` — pure aggregation of the other 4 pillars' own outputs.

## 6. Supply Chain Visibility & Risk (`/supply-chain`, `backend/app/supply_chain.py`)
Multi-tier shipment tracking extending schedule's procurement fields. Read-only page.
- As-of-day/date disclosure banner.
- In-app timestamped alerts panel (severity-tiered by days-at-risk/critical-path).
- Leaflet shipment map (site/tier-1/tier-2/at-risk legend, dynamic import, no SSR).
- At-risk shipment cards: root cause (first slipped milestone), linked RFI/schedule activity,
  recommended alternative or an explicit "no viable alternative" message.
- Full tracked-shipments table: item, tier-1 supplier, stage, required-by, projected arrival,
  status, equipment-spec compliance chip (IS 8623-1 LV switchgear voltage check).
- Backend: `GET /shipments`, `/shipments/{id}`, `/risks`, `/alerts`, `/meta`,
  `/equipment-spec-ncrs`, `/map`. Delay propagation, root-cause attribution, and alternative
  viability are all computed, not asserted.

## 7. Commissioning QA Copilot (`/commissioning`, `backend/app/commissioning.py`)
Cooling-only slice (electrical/fire deferred — see project instructions, corpus gap).
- Upload a real CSV cooling test log (click-to-browse).
- Persistent corpus-limitation disclosure (ASHRAE TC9.9 envelope is cross-source compiled, not
  manak-verified — ASHRAE is paywalled).
- Summary counts (record/pass/within-allowable/fail/not-checkable) + link to an HTML quality package.
- Findings-with-NCR list, other-test-records list (each with cited-clause box).
- Backend: `POST /ingest` (per-row deterministic PASS / OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE→
  NCR MEDIUM / FAIL→NCR HIGH / NOT_CHECKABLE, never crashes on a bad row), `GET
  /quality-package/{run_id}` (JSON), `/quality-package/{run_id}/html` (standalone report).

## 8. Codebook (`/codebook`, `standards-service` via MCP)
SiteMind's backend as an MCP *client* of Codebook (standards-service, port 8010) — browser never
talks to Codebook directly.
- Availability gating (checking/disabled/unreachable, explained in-page).
- Indexed-corpora panel (refresh button).
- Search-standards panel (query + optional corpus filter).
- Clause lookup panel (document_id + chunk_id → verbatim text).
- Document-check panel (upload a file + corpus name → per-sentence CONFORMS/NON_CONFORM/
  NEEDS_REVIEW).
- Backend: `GET /corpora`, `/search`, `/clause/{doc_id}/{chunk_id}`, `POST /check`,
  `/check-upload` — all proxy Codebook's 4 MCP tools (`list_corpora`, `search_standards`,
  `get_clause`, `check_document_against_corpus`), all return prose text blocks by design (MCP has
  no structured_output in the pinned SDK version).

## 9. Codebook Console (`/codebook/console`, new 2026-07-12)
Admin/browsing UI on Codebook's plain REST retrieval API (structured JSON, not MCP prose) — built
after establishing Codebook was already a separate service and already renamed (no new service,
no new brand needed; see `docs/codebook_console.md`).
- Corpora list, expandable rows, lazily-loaded per-corpus document list.
- Provenance badges: `codebook_verified`/`sitemind_indexed` → "Internal verified standard"
  (green); `company_uploaded` → "External / uploaded" (amber); unknown → gray. Per-document, not
  just per-corpus, since a corpus can be mixed.
- Add-a-document panel: corpus-name input (datalist suggestions) + drag-and-drop upload.
- Backend: `GET /console/corpora`, `/console/corpora/{name}/documents`, `POST /console/upload` —
  `httpx`-based REST proxy (bypasses MCP entirely) to standards-service's own `/api/retrieval/*`.

## 10. Knowledge Base (`/knowledge-base`, `backend/app/retrieval/` — flag-gated)
Independent standalone retrieval package (`RETRIEVAL_ENABLED`, default off) — predates Codebook,
still live because 2 eval scripts (`run_retrieval_eval.py`, `run_cross_corpus_eval.py`) import it
directly. Upload arbitrary docs into a searchable corpus, ask cited questions.
- Corpus selector (text input + datalist + clickable chips showing doc/chunk counts).
- Drag-and-drop upload panel.
- Ask-a-question panel — citations show source-type badge, score, filename/breadcrumb, verbatim
  quoted text; explicit abstention message when nothing clears the retrieval floor.
- Backend: `GET /corpora`, `POST /upload`, `POST /query`.

## 11. Knowledge Graph (`/graph`, `backend/app/kg.py`)
Equipment → spec → standard → RFI connections from real structured data (NetworkX, no LLM/embeddings).
- SVG subgraph, 4 columns (Equipment/Spec/Standard/RFI), curved labeled edges.
- Click a node → highlight its neighborhood, dim the rest; inspector side panel; "how this is
  built" explainer panel.
- Backend: `GET /api/kg/{element_id}` — builds an in-memory graph from `applicable_checks()` and
  shared-ID RFI references, returns the requested node's neighborhood (or whole graph on no match).

---

## 12. Automated eval suite (21 scripts)
Every pillar's correctness claim is a *computed* number from a re-runnable script, not an assertion
(project rule — see `PROGRESS.md` for current pass counts). Run via `python -m eval.run_X_eval`;
each writes a JSON report (`n_cases`, `n_pass`, `accuracy`/precision-recall-F1, `cases`). 18 live in
`backend/eval/`, 3 in `standards-service/eval/` (2 of which are near-duplicates of a backend
script, repointed — see caveats). None are blended into one score; each pillar reports separately.

**Compliance / extraction**
- `run_eval.py` — structural rule engine (8 checks) + citation-hallucination rate. ~41 hand-built
  boundary cases + naive-keyword baseline comparison, macro-F1/accuracy/confusion matrix.
- `run_extraction_eval.py` — free-text parameter extraction (planted values, correct abstention,
  no fabrication). 14 held-out-phrasing mini-docs incl. 2 adversarial decoys; precision/recall/F1.
- `run_electrical_eval.py` — electrical checks vs. IS 732 (OCR, superseded edition). 30 boundary
  cases; exact-match accuracy.
- `run_equipment_spec_eval.py` — IS 8623-1 LV switchgear spec matching. 12 cases incl. 4
  NOT_APPLICABLE (categories the standard doesn't cover); exact-match accuracy.

**Commissioning**
- `run_commissioning_eval.py` — ASHRAE-derived cooling envelope verdicts. 14 boundary cases
  (temp/RH, A1/A2 classes, 2 out-of-scope); exact-match accuracy.

**Supply chain**
- `run_alerts_eval.py` — alert severity tiering + detection-day logic. 11 synthetic cases;
  exact-match accuracy.
- `run_supply_chain_eval.py` — delay propagation, root-cause attribution, alternative viability.
  8 synthetic milestone scenarios; multi-field pass/fail.

**Schedule**
- `run_schedule_eval.py` — leading-indicator rules + CPM re-computation. ~11 cases (7 rule + 4
  synthetic dependency-graph); exact-match accuracy, uses live module constants (not fully mocked).
- `run_weather_eval.py` — IMD monsoon-window overlap/slip arithmetic. 11 synthetic cases;
  exact-match accuracy.
- `run_workforce_eval.py` — Pongal labour-dip overlap/slip arithmetic. 10 synthetic cases;
  exact-match accuracy.
- `run_mitigation_eval.py` — 3 mitigation functions (procurement-alternative, resequencing-float,
  resource-recovery) — the project's one explicit multi-agent claim. 13 synthetic cases; exact
  match on verdict + days-recovered.
- `run_timeline_eval.py` — cross-pillar aggregation traceability (every event id resolves to a
  real source record, phase bands match real `schedule.csv`, links are symmetric). ~20 checks
  against the **live demo dataset**, not synthetic fixtures.

**Cost / impact**
- `run_cost_risk_eval.py` — cost-at-risk arithmetic (delay/expedite/rework components). 9 synthetic
  cases; exact numeric match.
- `run_impact_eval.py` — ROI-ticker composition (hours/₹ saved per pillar). 11 synthetic cases;
  exact match + non-empty basis-string check.

**Copilot / retrieval (backend)**
- `run_copilot_eval.py` — retrieval-floor and seen-before-floor calibration (embeddings). 12 +
  9 hand-labeled queries; threshold-sweep accuracy, reports the deployed floors (0.40/0.35).
- `run_hybrid_retrieval_eval.py` — RRF fusion arithmetic only, cross-checked against an
  independently written reference implementation. 5 synthetic cases; accuracy.
- `run_cross_corpus_eval.py` (backend) — builds/tests 2 real filesystem corpora (17 real IS-code
  files, ~6,200 chunks + SiteMind's own clause JSON). ~20 cases: build-integrity, known-answer
  queries, gibberish abstention, byte-for-byte verbatim-offset integrity over **every** chunk,
  read-only-source proof.
- `run_retrieval_eval.py` (backend) — chunker + RRF + end-to-end ingest/query. ~22 cases across
  3 tiny made-up documents (earthing/fire/canteen — never real standards).

**Codebook / standards-service**
- `run_codebook_tools_eval.py` — drives all 4 MCP tools through a real client session against the
  **live running service** (port 8010) — the only script testing the actual MCP protocol surface,
  not just in-process logic. ~25 cases, every expected value independently pre-verified (REST call,
  grep, or direct function call) before being hardcoded; deliberately covers error paths (bogus
  chunk id/corpus/path), not just happy paths.
- `run_cross_corpus_eval.py` (standards-service) — same logic as the backend script above,
  repointed at the relocated `codebook_structural` corpus.
- `run_retrieval_eval.py` (standards-service) — same logic as the backend script above, repointed
  at the relocated package.

**Eval-suite caveats worth a critical look**
- Several rule-engine evals (`run_eval.py`, `run_electrical_eval.py`) grade the code against gold
  labels derived from the same thresholds the code implements — closer to a regression check than
  independent validation. The informative part of `run_eval.py` is its baseline comparison, not
  the headline accuracy number alone.
- Most test sets are small (n=5–14) and entirely self-authored by whoever wrote the feature —
  "held-out" mostly means different wording, not independent authorship.
- `run_copilot_eval.py`'s deployed retrieval floors are chosen using the same small labeled set
  that evaluates them — risk of overfitting the threshold to the eval's own paraphrase style.
- `run_workforce_eval.py` self-reports the Pongal rule is "dormant" on the real bundled demo data
  (formula proven correct in isolation, never exercised end-to-end against real project data).
- The backend and standards-service copies of `run_cross_corpus_eval.py` and `run_retrieval_eval.py`
  are near-duplicate test code maintained in two places — a fix in one isn't guaranteed to land in
  the other, and inflates the "21 scripts" count somewhat.
- `run_codebook_tools_eval.py` requires a separately running live service and can't run standalone
  in CI — easy for it to silently go stale if that process isn't up when the rest of the suite runs.
- No script backtests a prediction against real historical outcomes (no real project to backtest
  against) — schedule/supply-chain/cost evals all explicitly disclaim this and only prove internal
  arithmetic consistency, not real-world predictive accuracy.
- Strongest scripts in the suite, for contrast: `run_timeline_eval.py` and both
  `run_cross_corpus_eval.py` copies test against real derived/external data rather than hand-picked
  synthetic cases, with full (not sampled) coverage.

---

## Cross-cutting backend-only endpoints (no dedicated page)
- `GET /api/eval/report` — live-verified hallucination rate (every NCR citation re-checked
  against the real clause cache) + precomputed macro-F1/accuracy/confusion matrix from
  `backend/eval/run_eval.py`. Auto-runs the eval script if `report.json` is missing.
- `GET /api/trace`, `/api/trace/{run_id}` — provenance/trace record log.
- `GET /api/clock`, `POST /api/clock/advance`, `/api/clock/reset` — simulated "today" (offset
  clamped 0–60d), clears every downstream `lru_cache` on advance so schedule/supply-chain/
  timeline numbers recompute live. No mock fallback anywhere in this router.

## Cross-cutting frontend conventions
- `lib/api.ts`'s `getJSON`/`postJSON` helpers: 3.5s timeout, silent fallback to bundled mock data
  (`lib/mocks.ts`) on failure, surfaced to callers via a `live: boolean`.
- Upload/ingest/retrieval/codebook endpoints deliberately have **no** mock fallback — they throw a
  typed `*UnavailableError` instead, per the project's "never fabricate a real-file result" rule.
- Citation trust tiers, used consistently across Compliance and Codebook: `codebook_verified` /
  `primary_native_pdf` / `primary_scan_ocr` / `cross_source_unverified` — never silently presented
  as equivalent.

## Known caveats worth a critical look
- Two parallel retrieval stacks exist: the flag-gated `backend/app/retrieval/` (Knowledge Base
  page) and `standards-service` (Codebook + Codebook Console). Not consolidated — kept apart
  because 2 eval scripts still depend on the former directly.
- Codebook Console's frontend interactions (drag-and-drop, expand/collapse) have been code-reviewed
  and endpoint-verified live, but never exercised in an actual browser (no Playwright in this
  environment).
- Commissioning QA is cooling-only; electrical/fire slice is explicitly deferred pending a corpus
  gap (NBC 2016, DG-set testing standard not yet confirmed in Codebook).
- `standards-service` has no on-disk embeddings cache — every process restart triggers a ~7 minute
  blocking rebuild of the 6,206-chunk structural corpus.
- 13/24 citation `verify_url`s flagged as dead in `docs/PS_optimize.md`, not yet replaced.
