"""Backlog / Sprint endpoints, for the Tasks & Backlog and Agile Board pages."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.memory.project_memory import get_current_project_id, get_project_memory
from app.schemas.task import Backlog

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/backlog", response_model=Backlog)
async def get_backlog() -> Backlog:
    if not get_current_project_id():
        raise HTTPException(404, "No active project.")
    return get_project_memory().load_backlog()


@router.get("/sprint/current")
async def get_current_sprint() -> dict:
    if not get_current_project_id():
        raise HTTPException(404, "No active project.")
    backlog = get_project_memory().load_backlog()
    if not backlog.current_sprint_id:
        return {"sprint": None, "tasks": []}
    sprint = backlog.sprints.get(backlog.current_sprint_id)
    if not sprint:
        return {"sprint": None, "tasks": []}
    tasks = [backlog.tasks[t] for t in sprint.task_ids if t in backlog.tasks]
    completed = sum(1 for t in tasks if t.status.value == "completed")
    return {
        "sprint": sprint,
        "tasks": tasks,
        "completed_count": completed,
        "total_count": len(tasks),
        "progress_pct": round(100 * completed / len(tasks), 1) if tasks else 0.0,
    }
