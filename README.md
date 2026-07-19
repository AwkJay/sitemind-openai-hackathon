# SiteMind — AI Intelligence Platform for Data-Centre EPC Delivery

SiteMind is the automated **senior-structural-reviewer** for data-centre construction projects.
It reads a project's Design Basis Report and submittals, extracts each engineering parameter
**with its exact source sentence**, checks it against the **real, digitised Indian code clause**
that governs it, and returns non-conformances, senior advisory flags, a cited project copilot,
schedule-risk forecasting, supply-chain visibility, and commissioning QA — in seconds, with a
measured **zero-hallucination citation rate**.

## Why it's different

Most AI compliance tools either hallucinate citations or hide their reasoning behind an LLM
"trust me." SiteMind doesn't:
- **Every citation resolves to real text.** Compliance decisions are grounded in digitised
  Indian Standards (IS 456, IS 875, IS 1893, IS 732, IS 3043, IS 8623) and CEA regulations —
  never paraphrased from a model's memory.
- **Pass/fail is deterministic Python, not an LLM.** The model only writes prose; the actual
  judgment call is a rule evaluated against a cited clause, so it's auditable and reproducible.
- **Every number is computed, not asserted.** ROI, cost-at-risk, schedule impact, and retrieval
  confidence all come from real formulas over real inputs — see `docs/ARCHITECTURE.md`.
- **21 eval scripts** — 18 distinct harnesses plus 3 more in the standalone Codebook service (2 of
  which repoint near-duplicate logic at the relocated corpus, not independently authored) — each
  reported separately, never blended into one figure.

## What's REAL vs REPRESENTATIVE

- **Real:** every IS/CEA clause citation (resolves to digitised primary-source text), the
  compliance decision logic, all 21 evals, document ingestion (an uploaded PDF/DOCX is actually
  parsed, with mandatory abstention on anything not confidently extracted), and the CPM
  schedule-impact recomputation.
- **Representative:** the pre-loaded project documents and schedule are synthetic, modelled on
  real public Indian data-centre tenders. The standards and the logic that check them are real;
  so is anything you upload yourself.

## Prerequisites

Check these *before* running anything — most first-run failures trace back to one of these being
missing or the wrong version:

| Tool | Version | Check | Notes |
|---|---|---|---|
| Python | 3.12 (3.11 OK) | `python3 --version` (Linux/macOS) / `py -3.12 --version` (Windows) | The pinned numpy/pandas wheels don't build on 3.13+/3.14 yet. If your default `python3`/`py -3` resolves to a newer version, install 3.12 alongside it — both `run.sh` scripts already prefer `python3.12` over `python3` if it's on PATH. |
| Node.js | 18+ | `node --version` | Needed for the Next.js frontend. |
| A JS package manager | npm **or** pnpm | `npm --version` / `pnpm --version` | Not every machine has `npm` on PATH (some only have `pnpm`, or `node` installed without `npm`). Either works — see the frontend section below. If you don't have either, install Node via [nodejs.org](https://nodejs.org) (bundles npm) or `corepack enable` for pnpm. |
| curl | any | `curl --version` | Used to health-check the backend. Pre-installed on macOS/Linux; on Windows, PowerShell's `curl` alias works fine, or use `Invoke-WebRequest`. |

You do **not** need an LLM API key — the app runs fully offline by default (see below).

## Quick start (runs fully offline — no API key needed)

Two processes, two terminals: the FastAPI backend, then the Next.js frontend. The frontend talks
to the backend over `NEXT_PUBLIC_API_URL` — if that's wrong or the backend isn't up yet, the UI
silently falls back to bundled mock data, which looks fine but isn't the real pipeline. Start the
backend first and confirm its health check before touching the frontend.

### Backend

**macOS / Linux**
```bash
cd backend
./run.sh            # creates .venv (Python 3.12), installs deps, serves on :8000
```

**Windows (PowerShell)** — `run.sh` is Mac/Linux-oriented; use uvicorn directly:
```powershell
cd backend
py -3.12 -m venv .venv                                        # first time only
.venv\Scripts\python.exe -m pip install -r requirements.txt   # first time only
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
> If port 8000 is already taken, run on a different port instead (`--port 8001`) and point the
> frontend at it — see below.

> **If `pip install` fails with `pip: command not found` (Linux/macOS) or a similar error inside
> `run.sh`/the venv:** the venv was created without pip bundled (some distro Python builds ship
> `python3-venv` without `ensurepip`, or a stale `.venv/` was copied from elsewhere without its
> `bin/pip`). Fix by deleting and recreating it:
> ```bash
> rm -rf .venv
> python3.12 -m venv .venv --upgrade-deps   # --upgrade-deps ensures pip is installed
> source .venv/bin/activate
> pip install -r requirements.txt
> ```
> On Debian/Ubuntu, if `venv` creation itself fails, install `python3.12-venv` first
> (`sudo apt install python3.12-venv`).

This runs **offline by default**: compliance pass/fail and citations are always deterministic;
prose/answers come from cached fixtures. Confirm the backend is up before starting the frontend:
```bash
curl localhost:8000/api/health   # -> {"status":"ok","offline_mode":true,"provider":"offline",...}
```
**Windows (PowerShell):**
```powershell
curl.exe localhost:8000/api/health
```

### Optional: a live LLM (prose + answering unseen questions)
Copy `.env.example` → `backend/.env` and set `LLM_PROVIDER` to `openai` (`OPENAI_API_KEY`) or
`anthropic` (`ANTHROPIC_API_KEY`). The compliance decision and citations stay deterministic
regardless of provider — only prose/answers change.

### Frontend

Works identically on Windows/macOS/Linux — pick whichever package manager is on your machine
(check with `npm --version` / `pnpm --version` from the Prerequisites table above):

```bash
cd frontend
npm install          # or: pnpm install
npm run dev          # or: pnpm run dev   -> http://localhost:3000
```
> `node_modules` was previously installed with a *different* package manager than the one you're
> using now? Delete it first (`rm -rf node_modules` / `Remove-Item -Recurse -Force node_modules`)
> to avoid a corrupted install — the two package managers lay out `node_modules` differently.
>
> Using pnpm and it refuses to run native postinstall scripts (`ERR_PNPM_IGNORED_BUILDS`)? Run
> `pnpm approve-builds` and retry `pnpm install`.

If the backend is running on anything other than `http://localhost:8000` (e.g. `--port 8001`
because 8000 was taken), point the frontend at it **before** `npm run dev` / `pnpm run dev`:

**macOS / Linux**
```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8001" > .env.local
```
**Windows (PowerShell)**
```powershell
"NEXT_PUBLIC_API_URL=http://localhost:8001" | Out-File -Encoding utf8 .env.local
```
Restart the dev server after changing `.env.local` — Next.js only reads it at startup. Then open
`http://localhost:3000` and check the top-bar status indicator: green means the frontend reached
the real backend; red means the API URL is wrong or the backend isn't up (the UI is quietly
showing mock data, not a real run).

### One command: boot the full stack (Codebook + backend + frontend, with both optional flags on)

The manual two-terminal quick start above runs the backend with `CODEBOOK_ENABLED`/
`RETRIEVAL_ENABLED` **off** (the checked-in default), so the `/codebook` and `/knowledge-base`
pages will show "not enabled" banners. Use this path instead whenever you intend to demo either
of those — it's the only path that turns both flags on for you.

> ⏱️ **First run after starting the backend with `RETRIEVAL_ENABLED=1` will feel stuck — it
> isn't.** The first request to any `/api/retrieval/*` route triggers a one-time, CPU-bound
> embedding build of ~6,000+ document chunks (no GPU required, but no progress bar either). This
> can take several minutes on a laptop CPU. It happens once per backend process (not on every
> request), and the backend keeps responding to *other* routes (health, compliance, schedule,
> etc.) while it runs in the background thread pool — only `/knowledge-base` itself is briefly
> slow to answer its first query. Same one-time cost applies to Codebook's own embedding model
> load on `standards-service` startup (~1–2 min), which is why the launcher below waits on a
> health check before moving on.

**macOS / Linux — one command:**
```bash
npm run dev    # from the repo root — Codebook + backend (RETRIEVAL_ENABLED=1 CODEBOOK_ENABLED=1)
                # + frontend, all together. Same as running ./run-full.sh directly.
```
`npm run dev` inside `frontend/` (not the repo root) still does frontend-only, no-flags Next.js
dev, as documented above — the flags only get set by the repo-root script.

**Windows (PowerShell) — `run-full.sh` is a bash script and won't run natively; do the same three
steps by hand, in three separate PowerShell windows, in this order:**

1. Codebook:
   ```powershell
   cd standards-service
   py -3.12 -m venv .venv                                        # first time only
   .venv\Scripts\python.exe -m pip install -r requirements.txt   # first time only
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8010
   ```
   Wait for `curl.exe localhost:8010/health` to return `{"status":"ok",...}` before continuing.
2. Backend, with both flags set for *this* PowerShell session only:
   ```powershell
   cd backend
   $env:CODEBOOK_ENABLED = "1"
   $env:RETRIEVAL_ENABLED = "1"
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   Wait for `curl.exe localhost:8000/api/health` to return `{"status":"ok",...}` before continuing.
   (If you skip setting the env vars, the backend starts fine but silently serves without
   Codebook/Knowledge Base — same failure mode as the Linux default, just without a script to
   remind you.)
3. Frontend, in the third window:
   ```powershell
   cd frontend
   npm run dev   # or: pnpm run dev
   ```

Either way, open `http://localhost:3000` when all three report healthy.

### Codebook — the standalone standards service (part of the demo — see DEMO_STORY.md Act 7)

Codebook (`standards-service/`) is a separate, independently-runnable service that indexes the
same standards corpora as a searchable, MCP-consumable index — the point is other agents (not
just SiteMind's own backend) can query it too. The app above works fully without it, and its
backend flag (`CODEBOOK_ENABLED`) stays **off by default in `backend/.env`** so a fresh clone or
an eval run never depends on a third process being up. `npm run dev` at the repo root (above)
turns it on for you; or run it manually, one piece at a time:
```bash
cd standards-service
./run.sh            # creates .venv, installs deps, serves on :8010
curl localhost:8010/health   # -> {"status":"ok","service":"codebook"}
```

To let SiteMind's backend use it (browse/search/check-document from the `/codebook` page), set in
`backend/.env`:
```
CODEBOOK_ENABLED=1
CODEBOOK_MCP_URL=http://127.0.0.1:8010/mcp   # default, only needed if you moved the port
```
Restart the backend after changing this. With `CODEBOOK_ENABLED` unset (the checked-in default —
`run-full.sh` sets it for its own processes only), every `/api/codebook/*` route 404s and none of
that code path ever runs — same import-gating pattern as the rest of this repo's feature flags,
kept off by default so a fresh clone or an eval run never depends on a third process being up.
Full design/decisions: `docs/BUILD_PLAN_CODEBOOK.md`. Codebook also has its own **Console**
(`/codebook/console`) for browsing corpora/documents and uploading new ones, with a provenance
badge distinguishing internal verified standards from externally-uploaded documents.

### Optional: Knowledge Base — the standalone retrieval package (`/knowledge-base`)

A second, independent retrieval package (`backend/app/retrieval/`) predates Codebook and is kept
separate rather than merged, because 2 of the 21 evals still import it directly. Off by default
(`RETRIEVAL_ENABLED=0` in `backend/.env`); set `RETRIEVAL_ENABLED=1` and restart the backend to
mount `/api/retrieval/*` and use `/knowledge-base` to upload documents into a searchable corpus
and ask cited questions against it.

## Evaluation suites

21 eval scripts — **18 distinct harnesses** in `backend/eval/`, plus **3 more** in the standalone
Codebook service's own `standards-service/eval/` (2 of which repoint near-duplicate logic at the
relocated corpus, so treat those as re-verification, not independent authorship). Each measures a
different thing (rule-decision accuracy, extraction precision/recall, delay-propagation arithmetic,
ROI/cost-formula correctness, retrieval calibration...) and is reported on its own, never blended
into a single score. Full per-script breakdown (test-data source, metric, honest limitations):
`docs/features.md`.

**18 in `backend/`:**
```bash
cd backend && source .venv/bin/activate   # Windows: .venv\Scripts\activate

python -m eval.run_eval                # structural rule-decision — 100% vs 59% naive baseline, n=41
python -m eval.run_extraction_eval     # document extraction — precision/recall/F1 1.0, n=14 docs
python -m eval.run_electrical_eval     # electrical rule-decision — n=32, 32/32
python -m eval.run_equipment_spec_eval # equipment-spec compliance — n=12, 12/12
python -m eval.run_supply_chain_eval   # supply-chain delay/root-cause logic — n=8, 8/8
python -m eval.run_schedule_eval       # CPM + leading-indicator logic — n=12, 12/12
python -m eval.run_copilot_eval        # retrieval-floor calibration — n=9, 9/9
python -m eval.run_commissioning_eval  # cooling envelope threshold logic — n=14, 14/14
python -m eval.run_impact_eval         # ROI-model arithmetic — n=12, 12/12
python -m eval.run_cost_risk_eval      # cost-at-risk arithmetic — n=9, 9/9
python -m eval.run_mitigation_eval     # multi-agent mitigation-option arithmetic — n=13, 13/13
python -m eval.run_alerts_eval         # alert severity-tiering logic — n=11, 11/11
python -m eval.run_hybrid_retrieval_eval  # BM25+dense fusion arithmetic — n=5, 5/5
python -m eval.run_weather_eval        # IMD-cited monsoon-window overlap arithmetic — n=11, 11/11
python -m eval.run_workforce_eval      # Pongal labour-dip overlap arithmetic — n=10, 10/10
python -m eval.run_timeline_eval       # cross-pillar aggregation consistency — n=20, 20/20
python -m eval.run_retrieval_eval      # Knowledge Base: chunking + RRF + abstention — n=24, 24/24
python -m eval.run_cross_corpus_eval   # real corpus build, both corpora — n=26, 26/26
```

Codebook (`standards-service/`, the standalone service above) has its own **3 evals**, run
separately with their own `.venv`/`eval/` directory — the last two are near-duplicates of the
backend's own `run_retrieval_eval`/`run_cross_corpus_eval` above, repointed at the relocated
package after Codebook split out as its own service; kept in both places on purpose (Codebook
must be evaluable standalone, without the rest of the backend):
```bash
cd standards-service && source .venv/bin/activate

python -m eval.run_retrieval_eval        # chunking + RRF fusion + abstention — n=24, 24/24
python -m eval.run_cross_corpus_eval     # real corpus build, both corpora — n=26, 26/26
python -m eval.run_codebook_tools_eval   # all 4 MCP tools over the real protocol — n=30, 30/30
```

## Features

**Project Timeline** (`/timeline`) — the whole 48 MW build as one horizontal lifecycle, from
groundbreaking to handover, with every NCR/RFI/schedule-risk/supply-chain-alert/commissioning-
finding the other five pillars have already computed plotted as one sorted, cross-linked event
list. Pure aggregation — zero new judgment, zero fabricated events (`eval/run_timeline_eval.py`
checks every event traces to a real source record). Selecting an event highlights its real
cross-pillar links (e.g. a supply-chain alert lighting up the RFI and schedule risk it shares a
root cause with) and deep-links into the pillar page that owns it.

**Compliance Agent** (`/compliance`) — upload a Design Basis Report, submittal, or shop drawing
and get back non-conformances, each with a real cited clause, the exact source span it was
extracted from, and a confidence-scored Action Brief with a recommended action or an explicit
escalation to the Engineer of Record. Includes a coverage meter and an overlapping-requirement
resolver that names the binding clause when two standards both govern one parameter.

**Project Copilot** (`/copilot`) — cross-document Q&A with citations and a "seen-before RFI"
callout, using hybrid (BM25 + dense) retrieval. Abstains below a similarity floor instead of
guessing on weak or off-topic questions.

**Schedule Risk** (`/schedule`) — critical-path-method scheduling with leading-indicator risk
detection and a recomputed project-finish impact per risk. All four brief-named risk inputs are
covered: procurement status and lead times (vendor-status rule), workforce availability (a Pongal
festival labour-dip window), and weather (a real IMD-cited Northeast Monsoon normal window for
Coastal Tamil Nadu — planning-grade climatological, never a fabricated forecast; see
`GET /api/schedule/methodology`). Each risk includes mitigation options generated by three
specialist agents (procurement alternatives, resequencing/float, and resource/overtime recovery)
— bounded, deterministic computations, not free-form LLM planning.

**Supply Chain Visibility** (`/supply-chain`) — multi-tier shipment tracking with delay
propagation, root-cause attribution across supplier tiers, procurement-alternative viability
checks, equipment-spec compliance, and an in-app alerting log. Cross-references to RFIs and
schedule activities are computed and shown as clickable evidence chips, not just narrated.

**Commissioning QA** (`/commissioning`) — upload a cooling test-log CSV and get deterministic
pass/allowable/fail verdicts against a thermal envelope, generated NCRs, and an exportable
as-commissioned quality package.

**Knowledge Graph** (`/graph`) — an equipment → spec → standard → RFI graph built with plain
NetworkX over the same structured data the other pillars use.

**Knowledge Base** (`/knowledge-base`, off by default — see "Optional: Knowledge Base" above) —
upload documents into a searchable corpus and ask cited questions against it, independent of
Codebook's own corpora.

**Overview** (`/`) — a platform-wide ROI figure broken down per pillar with its computed basis,
and a cost-at-risk panel showing schedule-delay, expedite-premium, and rework-exposure terms
with their formulas, not just a headline number.

**Provenance trace** (`GET /api/trace`) — every agent run logs its step timings, provider, and
output summary locally; optionally mirrored to a Langfuse project when credentials are set.

**Codebook** (`/codebook`, part of the demo — see DEMO_STORY.md Act 7) — a standalone standards
service (`standards-service/`, its own process on :8010) exposing the same corpora over 4 MCP tools
so any agent can query them, not just SiteMind's own backend. Adds one new reasoning primitive,
`check_document_against_corpus`: upload a document, it extracts candidate requirements, retrieves
the matching real clause, and returns a deterministic CONFORMS/NON_CONFORM/NEEDS_REVIEW — same
retrieval-then-deterministic-decision-then-cited-prose pattern as the Compliance Agent, generalized
to any corpus. Its Console (`/codebook/console`) adds a browsing/upload UI with provenance badges.
See "Codebook — the standalone standards service" above to run it (`./run-full.sh` for the
one-command path).

## Architecture

```
Next.js Command Center  ──REST──>  FastAPI
  (Blueprint design system)          ├─ timeline     (pure aggregation, zero new judgment)
                                      ├─ compliance   (deterministic checks + cited clauses)
                                      ├─ copilot      (hybrid retrieval, cited, abstains)
                                      ├─ schedule     (CPM + leading-indicator rules + schedule_factors)
                                      ├─ supply_chain (delay propagation + root cause)
                                      ├─ commissioning (thermal-envelope threshold checks)
                                      ├─ impact / cost_risk (ROI + deterministic cost-at-risk)
                                      ├─ overview / kg / documents / eval
                                      └─ standards    (real digitised IS + electrical clauses)
```
Full diagram-as-code with every route and data dependency: `docs/ARCHITECTURE.md` (Mermaid,
renders on GitHub) — it also covers why the platform is deliberately not built on a multi-agent
orchestration framework.

**Stack:** Python · FastAPI · scikit-learn · sentence-transformers · NetworkX · Anthropic/OpenAI
(optional) · Next.js 14 · TypeScript · Tailwind · Recharts. No model training anywhere — this is
AI engineering (retrieval + deterministic logic + an LLM for prose only), not an ML pipeline.

## Troubleshooting

A quick-reference index of every failure mode covered in detail above, so you don't have to hunt
for it mid-demo:

| Symptom | Cause | Fix |
|---|---|---|
| `npm: command not found` | Only `pnpm` (or neither) is installed | Use `pnpm install && pnpm run dev` instead — see [Frontend](#frontend). |
| `pip: command not found` inside `run.sh` / a venv | venv created without pip bundled | `rm -rf .venv && python3.12 -m venv .venv --upgrade-deps` then reinstall — see [Backend](#backend). |
| Backend build fails on numpy/pandas wheels | Python 3.13+/3.14 default, not 3.12 | Install/point at Python 3.12 explicitly (`python3.12`, `py -3.12`) — see [Prerequisites](#prerequisites). |
| Frontend loads but everything looks like canned data, status pill is red | Backend isn't running, or `NEXT_PUBLIC_API_URL` points at the wrong port | Confirm `curl localhost:8000/api/health` succeeds *before* starting the frontend; set `.env.local` if the backend is on a non-default port — see [Frontend](#frontend). |
| `/codebook` or `/knowledge-base` pages say "not enabled" | Backend started without `CODEBOOK_ENABLED=1` / `RETRIEVAL_ENABLED=1` (the checked-in default) | Use the full-stack boot path (`npm run dev` at repo root, or the 3-step Windows sequence) instead of the plain two-terminal quick start — see [One command: boot the full stack](#one-command-boot-the-full-stack-codebook--backend--frontend-with-both-optional-flags-on). |
| Knowledge Base's first query (or `/api/retrieval/*` generally) hangs for minutes | Expected — first hit after `RETRIEVAL_ENABLED=1` triggers a one-time CPU embedding build of the filesystem corpora | Wait it out (several minutes on a laptop CPU, once per backend process); other routes stay responsive meanwhile. Codebook's own model load at startup is the same kind of one-time cost (~1–2 min). |
| `ERR_PNPM_IGNORED_BUILDS` during `pnpm install` | `node_modules` has native postinstall scripts pnpm refuses to run by default | `pnpm approve-builds` then retry `pnpm install`. |
| Port 8000/8010/3000 already in use | A previous run's process never exited | Find and stop it (`lsof -i :8000` / `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess`), or run on a different port and point the frontend at it. |

## Repository layout

- `backend/app/` — FastAPI app (agents/, ingest, schedule, supply_chain, commissioning, impact,
  cost_risk, evidence_links, kg, overview, standards, trace, codebook_client/codebook_router,
  retrieval/ — the flag-gated Knowledge Base package, off by default)
- `backend/data/` — synthetic project documents, real standards clauses, and reference PDFs
- `backend/eval/` — labelled test sets and the 18 benchmark runners
- `standards-service/` — Codebook, a standalone MCP-consumable standards service (optional,
  off by default) — its own app/, eval/ (3 more runners), run.sh, .venv
- `frontend/app/` — the Command Center UI: one page per pillar (`compliance/`, `copilot/`,
  `schedule/`, `timeline/`, `supply-chain/`, `commissioning/`, `graph/`), plus `codebook/` (and
  `codebook/console/`) and `knowledge-base/`
- `CONTRACT.md` — the API contract · `docs/ARCHITECTURE.md` — full system diagram
  (Codebook's architecture, corpora, and MCP interface included) · `docs/features.md` — every
  page, feature, and eval script inventoried in detail, incl. known caveats

## Roadmap

The compliance engine is clause-driven: every check maps to a real digitised clause, so breadth
scales by adding clauses, not by retraining anything. Planned next:
- **IS 875 Parts 1, 2, 4, 5** (dead / imposed / snow / load combinations — Part 3 wind is covered today)
- **IS 13920** (ductile seismic detailing) · **IS 800** (steel platforms, busway supports, racking)
  · **IS 1893 Part 4** (seismic for industrial structures and equipment)
- **NBC 2016** (fire, egress, electrical) — the most-cited code in real data-centre permitting

Out of scope by design: petroleum/oil-gas codes (wrong domain) and international data-centre
standards like TIA-942 or the Uptime Institute tiers (no Indian-standard grounding available).
