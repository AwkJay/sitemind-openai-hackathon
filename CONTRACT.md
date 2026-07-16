# API CONTRACT — frontend & backend agreement (do not drift)

Base URL: `http://localhost:8000`. All responses JSON. CORS open for `http://localhost:3000`.
Schemas are in `backend/app/schemas.py`. Frontend types mirror these in `frontend/lib/types.ts`.

## Endpoints

### `GET /api/health` → `{ "status": "ok", "offline_mode": bool }`

### `GET /api/overview` → `OverviewStats`
Computed from the actual NCRs found + schedule risks. Drives the ROI ticker.

### `GET /api/documents` → `[{ id, title, type, status, discipline }]`
The submittal/document register (from synthetic data). `type` ∈ design_basis|submittal|mix_design|rfi.
`status` uses real codes: "A – Approved","B – Approved as Noted","C – Revise & Resubmit","Pending".

### `POST /api/compliance/ingest` multipart `file` (.pdf/.docx/.txt/.md) → `IngestResult`
Reads the ACTUAL uploaded file (`app/ingest.py`; pdfplumber / python-docx / plain text). Extracts ONLY the
narrow parameter set the CHECK REGISTRY (`agents/checks.py`) can evaluate — nominal_cover, concrete_grade,
wc_ratio, long_steel_pct, importance_factor — each with its exact source sentence. Explicitly **abstains**
(never guesses) on parameter types it can't confidently find, and always abstains on design_wind_speed /
design_wind_pressure / tie_spacing (they need numeric context — site Vb, bar diameter — that free text rarely
states unambiguously). Response: `{ document_id, title, extracted:[{param,element,value,unit,source_quote}],
abstained:[{param,reason}], checkable_params }`. The returned `document_id` (e.g. `UPLOAD-XXXXXXXX`) can be
passed straight into `/compliance/check` or `/compliance/check/stream` — it flows through the exact same
deterministic check pipeline as any pre-loaded document. No mock/offline fallback: this endpoint requires the
live backend since it reads a real file; the frontend surfaces "backend unreachable" rather than fabricating
a result.

### `POST /api/compliance/check` body `{ "document_id": str }` → `ComplianceResult`
Runs the compliance agent on that document. Each NCR includes `source` (the quote+location proving the
input) and `citation` (the real clause). At least one ADVISORY (the IS 1893 I=1.5 judgment-catch) appears
for the design-basis doc.
- Streaming variant `POST /api/compliance/check/stream` (SSE): emits `{type:"reasoning", text}` events as
  the agent works, then a final `{type:"result", data: ComplianceResult}`. Frontend shows the live trace.

### `GET /api/compliance/action-brief/{document_id}` → `[ActionBrief]`
One brief per NCR (from `/compliance/check`'s result for that document). Every field is extracted-with-span,
cited, or deterministic. `confidence` is an enum (`high`/`medium`/`low`) tied to explicit conditions, never a
fabricated percentage; `low` confidence sets `status: REVIEW_REQUIRED` and omits `recommended_action`
(escalated to EOR instead of a guessed fix). `linked_rfi` / `affected_activity` are `null` when no defensible
real match exists — never a guessed link. `computed_impact` is always `null` (no transparent-formula impact
model exists yet). Works for both pre-loaded and uploaded (`UPLOAD-*`) document IDs. Full contract + rationale
in `../update_plan_draft.md`.

### `POST /api/copilot/ask` body `{ "question": str }` → `RFIAnswer`
Cited RAG over project docs + standards. Streaming variant `/api/copilot/ask/stream` (SSE) optional.
Retrieval applies a cosine-similarity floor (0.12) before composing an answer from TF-IDF hits — a
genuinely off-topic or gibberish question returns `"The project corpus does not contain enough
information to answer this question."` with `sources: []` rather than the nearest (irrelevant) chunk.
Curated fixture answers for known questions are matched first and bypass the floor.

### `GET /api/schedule/risks` → `[RiskItem]`
CPM + leading-indicator rules over the synthetic schedule. Each item includes
`downstream_activities` (direct successors read straight off the CPM dependency DAG) and
`project_impact_days` — the CPM forward pass re-run with `predicted_slip_days` added to that
activity's duration, diffed against the baseline project finish. Genuinely causal, not asserted:
non-critical-path activities correctly show `project_impact_days: 0` when float absorbs the slip.

### `GET /api/schedule/gantt` → `[{ wbs_id, task, phase, start_day, duration_days, on_critical_path, at_risk }]`

### `GET /api/kg/{element_id}` → `{ nodes:[{id,label,type}], edges:[{source,target,label}] }`
type ∈ equipment|spec|standard|rfi.

### `GET /api/supply-chain/shipments` → `[Shipment]`, `GET /api/supply-chain/shipments/{id}` → `Shipment`
Multi-tier shipment tracking, built by extending the schedule pillar's own procurement fields
(`procurement_item`/`lead_time_days`/`vendor_status` on `schedule.csv`) rather than a disconnected data
source — `wbs_id` links each shipment back to the schedule activity it feeds. Nothing here is asserted:
- `required_on_site_by` is derived from the real schedule DAG (the downstream "install" activity's start
  day; falls back to the shipment's own row), not hand-picked.
- `projected_arrival_day` is computed by propagating the delay observed at the *last-reached* milestone
  forward onto not-yet-reached milestones — never invented, and `0` (on time) unless a real delay was
  observed.
- `days_at_risk = max(0, projected_arrival_day - required_on_site_by)`.
- `root_cause` names the FIRST milestone that slipped, including which supplier *tier* — so a tier-1
  vendor flagged "slipping" can be explained by an upstream tier-2 sub-supplier delay (e.g. a customs
  hold on an imported component), not just re-stated.
- `alternatives`: each candidate supplier's `viable` flag is real arithmetic — `today + that supplier's
  own lead_time_days <= required_on_site_by`. When no alternative is viable, the field is empty and the
  caller should escalate for a schedule replan; never a guessed "it'll probably work out."

### `GET /api/supply-chain/risks` → `[SupplyChainRisk]`
Only shipments with `days_at_risk > 0`, sorted critical-path-first then by `days_at_risk`. Includes
`detected_lead_time_days` (days of advance warning vs `required_on_site_by`, same "lead time over naive
baseline" framing as `/schedule/risks`) and `recommended_alternative` (the earliest-arriving *viable* one,
or `null`).

### `GET /api/supply-chain/map` → `{ points:[{id,kind,shipment_id,label,city,lat,lon,at_risk}], routes:[{shipment_id,from,to,tier,at_risk}] }`
Plain lat/lon data for the geospatial view — real city coordinates for each supplier/site, no external
maps API or key required. `kind` ∈ `site|tier1|tier2`.

### `GET /api/eval/report` → `{ n, kappa, hallucination_rate, per_class:{...}, examples:[{pass:bool,...}] }`

### `GET /api/trace?limit=20` → `[TraceRecord]`, `GET /api/trace/{run_id}` → `TraceRecord`
Local provenance log for the three agent pipelines (`compliance.evaluate`, `copilot.ask`,
`action_brief.build`) — real wall-clock step timings, the actual LLM provider used (or `"offline"`),
and a summary of what each run produced. This is NOT Langfuse: it's a zero-dependency local substitute
until the team's Langfuse account is wired (see `sitemind/PROGRESS.md`). `TraceRecord`: `{ id, pipeline,
started_at, finished_at, duration_ms, input_summary, steps:[{name, duration_ms, meta}], output_summary }`.
Persisted to `backend/data/traces/<id>.json`; `GET /api/trace` also serves an in-memory ring buffer
(last 200 runs) for listing without a disk scan.

## Offline mode
If `ANTHROPIC_API_KEY` is unset, backend runs in OFFLINE_MODE: extraction/answers come from
deterministic cached fixtures (`backend/data/fixtures/`) so the full demo path works without any API key.
Compliance pass/fail + citations are ALWAYS deterministic (Python + clauses.json) regardless of mode.
