"""Git & Branches endpoints (PRD §20-23)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.git_layer.git_manager import get_git_manager
from app.memory.project_memory import get_current_project_id

router = APIRouter(prefix="/api/git", tags=["git"])


def _git():
    project_id = get_current_project_id()
    if not project_id:
        raise HTTPException(404, "No active project.")
    settings = get_settings()
    return get_git_manager(project_id, remote_url=settings.demo_project_git_remote)


@router.get("/branches")
async def list_branches() -> list[str]:
    return _git().list_branches()


@router.get("/commits")
async def recent_commits(limit: int = 30) -> list[dict]:
    return _git().recent_commits(limit=limit)


@router.get("/status/{agent_id}")
async def agent_git_status(agent_id: str) -> dict:
    return {"agent_id": agent_id, "status": _git().status(agent_id)}
