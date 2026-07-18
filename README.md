# SiteMind — AI EPC Project Intelligence for Data-Centre Construction

The automated **senior-structural-reviewer** for data-centre construction. SiteMind reads a project's
**Design Basis Report / submittals**, extracts each engineering parameter **with its source sentence**,
checks it against the **real Indian code clause** (digitised IS 456 / 875 / 1893, cited + verifiable), and
returns non-conformances, senior **advisory** flags, a cited project copilot, and a schedule-risk view — in
seconds, with a measured **zero-hallucination citation rate**.

> ET AI Hackathon 2026 · Problem #4. Built for the rubric: Innovation / Business Impact / Technical
> Excellence / Scalability / UX. See `docs/ARCHITECTURE.md` for the full system diagram + scalability
> story, and `PROGRESS.md` for the build log (see "Development process" below).

## What's REAL vs REPRESENTATIVE (we say this out loud)
- **REAL:** the IS standards + every clause citation (resolves to real digitised text) · the compliance
  decision logic · both evals (computed, not asserted, and reported as two separate numbers — see below) ·
  the citation-grounding check · document ingestion (an uploaded PDF/DOCX is actually parsed, with mandatory
  abstention on anything not confidently extracted) · the CPM schedule impact (a real re-run, not asserted).
- **REPRESENTATIVE:** the pre-loaded project documents + schedule are synthetic, modelled on real public
  Indian DC tenders. The standards and the logic are real; so is anything you upload yourself.

## Quick start (runs fully OFFLINE — no API key needed)

Two processes, two terminals: the FastAPI backend, then the Next.js frontend. The frontend
talks to the backend over `NEXT_PUBLIC_API_URL` — if that's wrong or the backend isn't up yet,
the UI silently falls back to bundled mock data, which looks fine but isn't the real pipeline.
Start the backend first and confirm its health check before touching the frontend.

### Backend

**macOS / Linux**
```bash
cd backend
./run.sh            # creates .venv (Python 3.12), installs deps, serves on :8000
```

**Windows (PowerShell)** — `run.sh` is Mac/Linux-oriented; use uvicorn directly:
```powershell
cd backend
py -3 -m venv .venv                                           # first time only
.venv\Scripts\python.exe -m pip install -r requirements.txt   # first time only
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
> If port 8000 is already taken (e.g. the `manak` MCP server also listens on `127.0.0.1:8000`),
> run on a different port instead — `--port 8001` — and point the frontend at it (see below).

Either way, this runs **OFFLINE by default**: compliance pass/fail + citations are always
deterministic; prose/answers come from cached fixtures. Confirm it's actually up before
starting the frontend:
```bash
curl localhost:8000/api/health   # -> {"status":"ok","offline_mode":true,"provider":"offline",...}
```

### Optional: a live LLM (prose + answering unseen questions)
Copy `.env.example` → `backend/.env` and set `LLM_PROVIDER`:
- **`codex`** — OpenAI Codex SDK via **ChatGPT login (no API key)**. See **`docs/CODEX_SETUP.md`**
  (`codex login` + `pip install -r requirements-codex.txt`). Constrained to a `read_only` sandbox; any
  failure falls back to the offline path automatically. **Measured live: ~185s per completion** — fine for
  one scripted "it generalises" demo question, far too slow to leave as the standing default (the
  compliance check calls it once per NCR). Keep `offline` as the default; see `docs/CODEX_SETUP.md`.
- **`openai`** — OpenAI API (`OPENAI_API_KEY`). · **`anthropic`** — Anthropic API (`ANTHROPIC_API_KEY`).
- `curl localhost:8000/api/health` → `{"offline_mode":...,"provider":"..."}`. The compliance decision +
  citations stay deterministic regardless of provider; only prose/answers change.

### Frontend
```bash
cd frontend
npm install
npm run dev         # http://localhost:3000  (falls back to bundled mocks if backend is down)
```
If the backend is running on anything other than `http://localhost:8000` (e.g. `--port 8001`
because 8000 was taken), point the frontend at it **before** `npm run dev`:

**macOS / Linux**
```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8001" > .env.local
```
**Windows (PowerShell)**
```powershell
"NEXT_PUBLIC_API_URL=http://localhost:8001" | Out-File -Encoding utf8 .env.local
```
Restart `npm run dev` after changing `.env.local` — Next.js only reads it at startup. Then open
`http://localhost:3000` and check the top-bar "Agents online" indicator: green means the
frontend reached the real backend; red means the API URL is wrong or the backend isn't up (in
which case the UI is quietly showing mock data, not a real run).

### Eval (the credibility benchmark — THIRTEEN separate numbers, never blended)
```bash
cd backend && source .venv/bin/activate
python -m eval.run_eval               # structural rule-decision: writes eval/report.json + testset.jsonl
# Result: SiteMind 100% vs naive baseline 59% on 41 labelled cases · 0.00 hallucinated citations.

python -m eval.run_extraction_eval    # document extraction: writes eval/extraction_report.json
# Result: precision/recall/F1 1.0 on 11 planted params across 14 held-out docs, 0 false positives,
# abstention accuracy 1.0 (59/59). Small n — an honest first pass, state that caveat when citing it.

python -m eval.run_electrical_eval        # electrical rule-decision: n=32, 32/32 pass
python -m eval.run_equipment_spec_eval    # equipment-spec compliance: n=12, 12/12 pass
python -m eval.run_supply_chain_eval      # supply-chain delay/root-cause/alternative logic: n=8, 8/8 pass
python -m eval.run_schedule_eval          # CPM + leading-indicator rule logic: n=12, 12/12 pass
python -m eval.run_copilot_eval           # retrieval-floor calibration: n=9, accuracy 1.0
python -m eval.run_commissioning_eval     # cooling envelope threshold logic: n=14, 14/14 pass
python -m eval.run_impact_eval            # impact-model arithmetic: n=12, 12/12 pass
python -m eval.run_cost_risk_eval         # cost-at-risk arithmetic: n=9, 9/9 pass
python -m eval.run_mitigation_eval        # multi-agent mitigation-option arithmetic (2026-07-03): n=13, 13/13
python -m eval.run_alerts_eval            # alert severity-tiering + detection logic (2026-07-03): n=11, 11/11
python -m eval.run_hybrid_retrieval_eval  # BM25+dense RRF fusion arithmetic (2026-07-03): n=5, 5/5 pass
```
Each measures a different thing (deterministic rule-application, free-text extraction, delay-propagation
arithmetic, ROI/cost-formula correctness, retrieval calibration...) and is reported separately on purpose —
blending them into one claimed metric was an earlier mistake this project corrected, and stayed corrected
as the number of pillars grew from 3 to 5 and the eval count grew from 8 to 13.

## The demo path (Golden Demo Path)
1. **Overview** (`/`) — ROI ticker (now a platform-wide total across all 4 measurable pillars, with a
   per-pillar hours/₹ breakdown showing each pillar's exact computed basis — see `backend/app/impact.py`,
   added 2026-07-03) and a **Cost-at-Risk** panel (`backend/app/cost_risk.py`): a deterministic
   schedule-delay + expedite-premium + rework-exposure total, every term's formula shown, not just the
   number.
2. **Compliance** (`/compliance`) — run a check on the **Design Basis Report** → 6 NCRs incl. the
   **IS 1893 I=1.5 judgment-catch** (advisory, "confirm with EOR", cited to BOTH Cl 7.2.3 and Cl 6.4.2),
   each with a real cited clause + source span. Plus a **coverage meter** (12 clauses / 3 standards) and an
   **overlapping-requirement** panel that names the *binding* clause when two clauses govern one parameter.
   Or **upload your own** PDF/DOCX/txt — real extraction with source spans, mandatory abstention, runs
   through the same pipeline. Each NCR gets an **Action Brief**: confidence enum, real RFI/schedule links
   (or none, never guessed), a recommended action or an explicit EOR escalation.
3. **Copilot** (`/copilot`) — cross-document Q&A with citations + the "seen-before RFI" callout. Abstains
   below a similarity floor instead of guessing on weak/off-topic questions.
4. **Schedule** (`/schedule`) — CPM + leading-indicator risk with "days before baseline", a "biggest early
   warning" hero card, and a CPM-recomputed project-finish impact per risk (or "absorbed by float"). Each
   risk now also shows **mitigation options from 3 specialist agents** (`backend/app/agents/mitigation.py`,
   added 2026-07-03 — the brief's only explicit "multi-agent system" ask): a procurement-alternative check,
   a resequencing/float check, and a resource/overtime-recovery check, each a real computation, coordinated
   without an LLM in the loop.
5. **Supply Chain** (`/supply-chain`) — an **Alerts** panel (in-app, timestamped log — not push/email —
   added 2026-07-03, answers the brief's "alerting timeliness" metric) sits above a multi-tier shipment map,
   root-cause attribution (e.g. SHP-002's LV switchgear delay traces to a tier-1 production slip),
   procurement alternatives with a real viability check, and an **equipment-spec compliance** column
   (IS 8623-1:1993) — MATCH/MISMATCH/SPEC_NOT_PROVIDED/NOT_APPLICABLE, honestly narrow to the one
   procurement category a real standard covers so far. Each at-risk shipment shows **clickable
   linked-evidence chips** (`backend/app/evidence_links.py`): SHP-002 links to RFI-EL-112 (matched because
   the RFI's own reference text cites `DC1-04-EL-030` verbatim — a real, computed join, not a hardcoded
   story) and to the real schedule activity it feeds — surfaced in the product, not only narrated in
   `DEMO_STORY.md`. A disclosure banner states the real data provenance plainly: a static milestone
   snapshot diffed against an as-of day (`GET /api/supply-chain/meta`), not live carrier tracking.
6. **Commissioning QA** (`/commissioning`) — upload a real cooling test-log CSV (try
   `backend/data/project_docs/sample_commissioning_log.csv`), get deterministic PASS/within-allowable/FAIL
   verdicts against the ASHRAE TC9.9 envelope, NCRs for failures, and an exportable as-commissioned quality
   package. The corpus-limitation banner (cross-source compiled, not manak-verified) is always shown.
7. **Graph** (`/graph`) — equipment→spec→standard→RFI knowledge graph, with an in-page panel
   explaining it's plain NetworkX over the same structured data + rule engine Compliance uses — no
   LLM, no embeddings.
8. **Live document upload** (`/compliance`) — beyond the pre-loaded DBR, upload
   `backend/data/project_docs/live_upload_samples/DC1-16-DBR-0201-R0_Generator-Earthing-Addendum.docx`
   (Electrical — 3 real HIGH NCRs + 1 conforming, the electrical domain's first live-upload exercise)
   or `DC1-02-SD-0187-R0_Generator-Plinth-Shop-Drawing.docx` (Structural — a cover violation that
   triggers the same overlap-resolution logic as the bundled DBR) to prove the pipeline generalises
   past the one fixture everyone reruns. See `DEMO_STORY.md` Act 5.
9. **Simulated clock** (top-bar `Day N` control, `GET/POST /api/clock`) — advances "today" and
   re-runs every real computation against it (schedule at-risk count, alert advance-warning-days,
   alternative-supplier viability), so a judge watches the same real numbers change instead of
   taking "derived, not hardcoded" on faith. Resets to the exact baseline. See `DEMO_STORY.md` Act 6.
10. **Eval** — the 0.00-hallucination rule-decision benchmark, plus 12 more separate eval numbers (extraction,
    electrical, equipment-spec, supply-chain, schedule, copilot, commissioning, impact-model, cost-risk,
    multi-agent mitigation, alerting, hybrid-retrieval fusion — 13 total, never blended into one figure). Run individually via
    `python -m eval.run_*` (see "Eval" above) — there is no dedicated eval UI page; the numbers are
    demonstrated by running the harness live, same as the rest of this section.
11. **Trace** (`GET /api/trace`) — a local, real provenance log (step timings, provider, output summary) for
    every agent run, always written. When `LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY` are set in
    `backend/.env`, every trace is also mirrored to a real Langfuse project (`app/langfuse_sink.py`) —
    verified live, not just configured.

See `DEMO_STORY.md` for a connected narration script tying the above into one continuous story instead of
five separate feature demos, and `docs/archive/DEPLOY.md` for free-tier Vercel+Render deploy steps
(written, not run — this submission delivers as recorded video + repo, not a live URL).

## Development process
Git history for this repo is a single large commit rather than incremental ones — the platform was built
across several AI-pair-programming sessions and only the completed result was committed. That's a real
gap against normal engineering practice, and we're not papering over it: `PROGRESS.md` is the actual
incremental record instead — every slice is timestamped, states what was built, and states the real
verified numbers at that point, in the same "newest at top" log format `git log` would give you.

## Architecture
```
Next.js Command Center  ──REST/SSE──>  FastAPI
  (Blueprint design system)              ├─ compliance (deterministic checks + real cited clauses + advisory)
                                         ├─ copilot (sentence-transformer embeddings + retrieval-floor abstain, cited)
                                         ├─ schedule (CPM + leading-indicator rules)
                                         ├─ supply_chain (delay propagation + root cause + evidence_links.py)
                                         ├─ commissioning (cooling-envelope threshold checks)
                                         ├─ impact / cost_risk (platform-wide ROI + deterministic cost-at-risk)
                                         ├─ overview / kg / documents / eval
                                         └─ standards: clauses.json (REAL digitised IS + electrical clauses)
```
Full diagram-as-code with every route + data dependency: `docs/ARCHITECTURE.md` (Mermaid, renders on
GitHub) — also covers why the platform is deliberately not built on a multi-agent orchestration framework.

Stack: Python · FastAPI · scikit-learn · sentence-transformers · NetworkX · Anthropic (optional) ·
Next.js 14 · TypeScript · Tailwind · Recharts. No model training anywhere — AI engineering (LLM + retrieval
+ deterministic logic).

## Layout
- `backend/app/` — FastAPI app (agents/, ingest.py, schedule, supply_chain, commissioning, impact,
  cost_risk, evidence_links, kg, overview, standards, trace, eval)
- `backend/data/` — synthetic project docs (incl. `cost_basis.json`) + offline fixtures +
  `standards/clauses.json` (real clauses) + `traces/` (local provenance log, written at runtime)
- `backend/eval/` — the labelled test sets + 10 separate benchmark runners (see "Eval" above)
- `frontend/` — the Command Center UI
- `CONTRACT.md` — the API contract · `PROGRESS.md` — build log · `docs/archive/` — superseded pre-build
  specs, kept for provenance (see its own `README.md`)

## Roadmap — pluggable code library (the scalability story, said honestly)
The compliance engine is clause-driven: every check maps to a real digitised clause, so **breadth scales by
adding clauses, not by retraining anything**. On-narrative next codes for a data-centre EPC:
- **IS 875 Parts 1, 2, 4, 5** (dead / imposed / snow / load combinations — we have Pt 3 wind today)
- **IS 13920** (ductile seismic detailing — pairs with the I=1.5 catch) · **IS 800** (steel platforms, busway
  supports, racking) · **IS 1893 Pt 4** (seismic for industrial structures & equipment)
- **NBC 2016** (fire / egress / electrical) — the most-cited code in real DC permitting
We deliberately **do not** chase petroleum/oil-gas codes (wrong domain) or international DC standards
(TIA-942, Uptime) — they carry no Indian-standard moat; they stay a mention, not a dependency.
