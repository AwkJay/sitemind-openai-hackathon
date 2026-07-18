"""SiteMind backend — FastAPI app exposing every endpoint in CONTRACT.md."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .agents.action_brief import router as action_brief_router
from .agents.compliance import router as compliance_router
from .agents.copilot import router as copilot_router
from .clock import router as clock_router
from .commissioning import router as commissioning_router
from .cost_risk import router as cost_risk_router
from .documents import router as documents_router
from .eval import router as eval_router
from .kg import router as kg_router
from .overview import router as overview_router
from .schedule import router as schedule_router
from .supply_chain import router as supply_chain_router
from .timeline import router as timeline_router
from .trace_api import router as trace_router

app = FastAPI(title="SiteMind", version="1.0.0")

# CORS for the Next.js frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    """offline_mode is True when no live LLM provider is configured. `provider` names
    the active backend (offline | codex | openai | anthropic). langfuse_enabled is
    True only when both LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY are configured —
    the local trace log (`/api/trace`) is written either way."""
    return {
        "status": "ok",
        "offline_mode": config.OFFLINE_MODE,
        "provider": config.LLM_PROVIDER,
        "langfuse_enabled": config.LANGFUSE_ENABLED,
    }


for r in (
    overview_router,
    documents_router,
    compliance_router,
    action_brief_router,
    copilot_router,
    commissioning_router,
    schedule_router,
    supply_chain_router,
    timeline_router,
    cost_risk_router,
    kg_router,
    eval_router,
    trace_router,
    clock_router,
):
    app.include_router(r)
