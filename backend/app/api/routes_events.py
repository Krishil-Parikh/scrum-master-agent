"""Raw event feed -- backs the "Live Terminal" panel (git/test output) and
gives a freshly-loaded frontend its history before the WebSocket takes over
for live updates."""

from __future__ import annotations

from fastapi import APIRouter

from app.memory.project_memory import get_current_project_id, get_project_memory
from app.schemas.event import Event

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(channel: str | None = None, limit: int = 300) -> list[Event]:
    if not get_current_project_id():
        return []
    events = get_project_memory().read_events(limit=1000)
    if channel:
        events = [e for e in events if e.payload.get("channel") == channel]
    return events[-limit:]
