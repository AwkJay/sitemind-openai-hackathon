# Setup, Windows instructions & troubleshooting

Detailed operational reference, split out of the main `README.md` to keep that file readable.
Read this if the quick start in the README doesn't cover your OS/situation.

## Prerequisites

| Tool | Version | Check | Notes |
|---|---|---|---|
| Python | 3.12 (3.11 OK) | `python3 --version` (Linux/macOS) / `py -3.12 --version` (Windows) | The pinned numpy/pandas wheels don't build on 3.13+/3.14 yet. Both `run.sh` scripts prefer `python3.12` over `python3` if it's on PATH. |
| Node.js | 18+ | `node --version` | Needed for the Next.js frontend. |
| A JS package manager | npm **or** pnpm | `npm --version` / `pnpm --version` | Either works. If neither is present, install Node via [nodejs.org](https://nodejs.org) (bundles npm) or `corepack enable` for pnpm. |
| curl | any | `curl --version` | Used to health-check the backend. On Windows, PowerShell's `curl` alias or `Invoke-WebRequest` works fine. |

No LLM API key is required — the app runs fully offline by default.

## Backend

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
If port 8000 is taken, run on a different port (`--port 8001`) and point the frontend at it (see below).

**If `pip install` fails with `pip: command not found` inside `run.sh`/the venv:** the venv was created
without pip bundled. Fix:
```bash
rm -rf .venv
python3.12 -m venv .venv --upgrade-deps
source .venv/bin/activate
pip install -r requirements.txt
```
On Debian/Ubuntu, install `python3.12-venv` first if venv creation itself fails.

Confirm the backend is up before starting the frontend:
```bash
curl localhost:8000/api/health   # -> {"status":"ok","offline_mode":true,"provider":"offline",...}
```

### Optional: a live LLM (prose + answering unseen questions)
Copy `.env.example` → `backend/.env` and set `LLM_PROVIDER` to `openai` (`OPENAI_API_KEY`) or
`anthropic` (`ANTHROPIC_API_KEY`). The compliance decision and citations stay deterministic
regardless of provider — only prose/answers change.

## Frontend

```bash
cd frontend
npm install          # or: pnpm install
npm run dev          # or: pnpm run dev   -> http://localhost:3000
```
If `node_modules` was previously installed with a *different* package manager, delete it first to
avoid a corrupted install. Using pnpm and it refuses native postinstall scripts
(`ERR_PNPM_IGNORED_BUILDS`)? Run `pnpm approve-builds` and retry.

If the backend runs on anything other than `http://localhost:8000`, point the frontend at it
**before** `npm run dev`:
```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8001" > .env.local
```
Restart the dev server after changing `.env.local`. Then check the top-bar status indicator on
`http://localhost:3000`: green means the frontend reached the real backend; red means mock data.

## One command: boot the full stack (Codebook + backend + frontend, both optional flags on)

The manual two-terminal quick start runs with `CODEBOOK_ENABLED`/`RETRIEVAL_ENABLED` **off** (the
checked-in default), so `/codebook` and `/knowledge-base` show "not enabled" banners. Use this
instead whenever you intend to demo either:

> First run after `RETRIEVAL_ENABLED=1` will feel stuck — it isn't. The first request to any
> `/api/retrieval/*` route triggers a one-time CPU-bound embedding build of ~6,000+ chunks (several
> minutes on a laptop, no progress bar). Happens once per backend process; other routes stay
> responsive. Same one-time cost applies to Codebook's own model load at startup (~1–2 min).

**macOS / Linux — one command:**
```bash
npm run dev    # from the repo root — Codebook + backend (RETRIEVAL_ENABLED=1 CODEBOOK_ENABLED=1) + frontend
```

**Windows (PowerShell)** — `run-full.sh` won't run natively; do the same three steps by hand, in
three separate PowerShell windows, in order:
1. Codebook: `cd standards-service` → same venv steps as backend above → `uvicorn app.main:app --port 8010`. Wait for `curl.exe localhost:8010/health`.
2. Backend, with both flags for *this* session: `$env:CODEBOOK_ENABLED = "1"; $env:RETRIEVAL_ENABLED = "1"` before `uvicorn app.main:app --port 8000`. Wait for `curl.exe localhost:8000/api/health`.
3. Frontend: `cd frontend; npm run dev`.

### Codebook — the standalone standards service
```bash
cd standards-service
./run.sh            # creates .venv, installs deps, serves on :8010
curl localhost:8010/health   # -> {"status":"ok","service":"codebook"}
```
To let SiteMind's backend use it (`/codebook` page), set in `backend/.env`:
```
CODEBOOK_ENABLED=1
CODEBOOK_MCP_URL=http://127.0.0.1:8010/mcp   # default
```
Restart the backend after changing this.

### Optional: Knowledge Base (`/knowledge-base`)
Off by default (`RETRIEVAL_ENABLED=0` in `backend/.env`). Set to `1` and restart to mount
`/api/retrieval/*` and use `/knowledge-base` to upload documents into a searchable corpus.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `npm: command not found` | Only `pnpm` (or neither) is installed | `pnpm install && pnpm run dev` instead. |
| `pip: command not found` inside `run.sh` / a venv | venv created without pip bundled | `rm -rf .venv && python3.12 -m venv .venv --upgrade-deps` then reinstall. |
| Backend build fails on numpy/pandas wheels | Python 3.13+/3.14 default, not 3.12 | Install/point at Python 3.12 explicitly (`python3.12`, `py -3.12`). |
| Frontend loads but everything looks like canned data, status pill is red | Backend isn't running, or `NEXT_PUBLIC_API_URL` points at the wrong port | Confirm `curl localhost:8000/api/health` succeeds first; set `.env.local` if on a non-default port. |
| `/codebook` or `/knowledge-base` say "not enabled" | Backend started without `CODEBOOK_ENABLED=1` / `RETRIEVAL_ENABLED=1` | Use the full-stack boot path above instead of the plain two-terminal quick start. |
| Knowledge Base's first query hangs for minutes | Expected — first hit after `RETRIEVAL_ENABLED=1` triggers a one-time CPU embedding build | Wait it out (once per backend process); other routes stay responsive. |
| `ERR_PNPM_IGNORED_BUILDS` during `pnpm install` | pnpm refuses native postinstall scripts by default | `pnpm approve-builds` then retry. |
| Port 8000/8010/3000 already in use | A previous run's process never exited | Find and stop it (`lsof -i :8000`), or run on a different port and point the frontend at it. |

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
