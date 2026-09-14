"""One combined snapshot for the frontend's initial load, so the dashboard
doesn't need to sequence half a dozen requests before it can render.
After this, the WebSocket carries live updates."""

from __future__ import annotations

from fastapi import APIRouter

from app.agents.registry import get_agent_registry
from app.communication.websocket_manager import get_connection_manager
from app.memory.project_memory import get_current_project_id, get_project_memory
from app.orchestration.run_control import get_run_controller

router = APIRouter(prefix="/api", tags=["bootstrap"])


@router.get("/bootstrap")
async def bootstrap() -> dict:
    project_id = get_current_project_id()
    registry = get_agent_registry()
    controller = get_run_controller()
    connections = get_connection_manager()

    agents = [
        {
            "agent_id": a.agent_id,
            "display_name": a.identity.display_name,
            "specialty": a.identity.specialty.value,
            "branch": a.identity.branch,
            "color": a.identity.color,
            "avatar_initials": a.identity.avatar_initials,
            "state": a.status.state.value,
            "online": a.status.online,
        }
        for a in registry.all()
    ]

    if not project_id:
        return {
            "has_project": False,
            "context": None,
            "backlog": None,
            "agents": agents,
            "messages": [],
            "events": [],
            "run": {"status": controller.status.value, "current_phase": controller.current_phase},
            "ws_clients": connections.connection_count,
        }

    memory = get_project_memory()
    context = memory.load_context()
    backlog = memory.load_backlog()
    return {
        "has_project": True,
        "context": context,
        "backlog": backlog,
        "agents": agents,
        "messages": memory.read_messages(limit=300),
        "events": memory.read_events(limit=300),
        "sme_questions": memory.list_sme_questions(open_only=True),
        "run": {
            "status": controller.status.value,
            "current_phase": controller.current_phase,
            "elapsed_seconds": controller.elapsed_seconds,
        },
        "ws_clients": connections.connection_count,
    }
