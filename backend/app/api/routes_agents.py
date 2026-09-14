"""Agent roster + live status, for the dashboard sidebar."""

from __future__ import annotations

from fastapi import APIRouter

from app.agents.registry import get_agent_registry
from app.skills.loader import get_skill_loader

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents() -> list[dict]:
    registry = get_agent_registry()
    skills = get_skill_loader()
    out = []
    for agent in registry.all():
        out.append(
            {
                "agent_id": agent.agent_id,
                "display_name": agent.identity.display_name,
                "specialty": agent.identity.specialty.value,
                "branch": agent.identity.branch,
                "color": agent.identity.color,
                "avatar_initials": agent.identity.avatar_initials,
                "state": agent.status.state.value,
                "note": agent.status.note,
                "online": agent.status.online,
                "current_task_id": agent.status.current_task_id,
                "skills_used": skills.skills_used_by(agent.agent_id),
                "last_active_at": agent.status.last_active_at.isoformat(),
            }
        )
    return out
