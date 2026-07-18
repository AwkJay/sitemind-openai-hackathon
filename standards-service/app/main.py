"""Codebook (standards-service) — a standalone FastAPI process exposing
SiteMind's standards/company-document retrieval layer as its own named
service (see docs/BUILD_PLAN_CODEBOOK.md).

Step 1/2 of that spec: this process boots independently on its own port
(8010 — 8000/8001 are already spoken for by manak-dev and SiteMind's own
backend) and mounts the relocated retrieval package
(`app/retrieval/`, copied from `backend/app/retrieval/` — see that
package's own docstrings for what changed vs. the original), plus (step 3)
Codebook's own MCP server (`app/mcp_server.py`) exposing `list_corpora`/
`search_standards`/`get_clause` over streamable-HTTP at `/mcp` — the same
transport + mounting pattern manak-dev's own `main.py` uses (`build_mcp()`
-> `mcp.streamable_http_app()`, session manager run for the app's lifespan).
`check_document_against_corpus` is a later step in the spec, not built yet.

House style matches `backend/app/main.py`: a FastAPI() app, permissive CORS
for local dev, a `/health` endpoint, routers included in a tuple loop.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .mcp_server import build_mcp
from .retrieval.router import router as retrieval_router

# In-process MCP server, mounted below at /mcp. Its streamable-HTTP
# transport has a session manager that must run for the lifetime of the app
# (mirrors manak-dev/app/backend/main.py's create_app() exactly).
mcp = build_mcp()
mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Codebook (standards-service)", version="0.1.0", lifespan=_lifespan)

# CORS — permissive for local dev; this service is only ever called by
# SiteMind's own backend (as an MCP/HTTP client) or directly during testing,
# never by a browser today.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "codebook"}


routers = (retrieval_router,)

for r in routers:
    app.include_router(r)

# MCP transport at /mcp — mounted after the REST routers (order doesn't
# matter for FastAPI's own routing, but mirrors manak-dev's file layout).
app.mount("/mcp", mcp_app)
