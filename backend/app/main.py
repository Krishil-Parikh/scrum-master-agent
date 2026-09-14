"""
FastAPI application entrypoint.

Wires together every layer built elsewhere in app/: config, the agent
registry, the event bus -> WebSocket bridge, and every API router. Run
with:

    uvicorn app.main:app --reload --port 8000

(from the backend/ directory, with the virtualenv from requirements.txt
active and backend/.env populated -- see backend/README.md).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.registry import get_agent_registry
from app.api import (
    routes_agents,
    routes_bootstrap,
    routes_conversations,
    routes_events,
    routes_git,
    routes_project,
    routes_run,
    routes_sme,
    routes_tasks,
    ws,
)
from app.communication.event_bus import get_event_bus
from app.communication.websocket_manager import get_connection_manager
from app.config import get_settings
from app.llm.openrouter_client import get_llm_client
from app.schemas.event import Event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai_dev_pod")

settings = get_settings()

app = FastAPI(
    title="AI Dev Pod API",
    description="Backend for the AI Agile Software Development Pod.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    routes_project.router,
    routes_run.router,
    routes_agents.router,
    routes_conversations.router,
    routes_tasks.router,
    routes_git.router,
    routes_sme.router,
    routes_events.router,
    routes_bootstrap.router,
    ws.router,
):
    app.include_router(router)


@app.on_event("startup")
async def on_startup() -> None:
    # Instantiate the pod once at startup (rather than lazily on first use)
    # so agent identities are ready before the frontend's first request.
    get_agent_registry()

    bus = get_event_bus()
    manager = get_connection_manager()

    async def _forward_to_websockets(event: Event) -> None:
        await manager.broadcast({"kind": "event", "event": event.model_dump(mode="json")})

    bus.subscribe(_forward_to_websockets)

    llm_client = get_llm_client()
    if not llm_client.configured:
        logger.warning(
            "No OpenRouter API keys configured -- LLM-backed endpoints will fail until "
            "backend/.env has at least one OPENROUTER_API_KEY_N set."
        )
    logger.info("AI Dev Pod backend started (env=%s, model=%s).", settings.app_env, settings.openrouter_model)


@app.get("/api/health")
async def health() -> dict:
    from app.llm.openrouter_client import get_llm_client

    llm_client = get_llm_client()
    return {
        "status": "ok",
        "env": settings.app_env,
        "model": settings.openrouter_model,
        "llm_keys_configured": llm_client.key_count,
        "sme_mode": settings.sme_mode,
    }
