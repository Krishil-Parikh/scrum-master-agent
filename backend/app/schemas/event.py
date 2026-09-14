"""Event bus schema (PRD §19, §9 architecture; Roadmap Phase 9)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.utils.ids import new_id


class EventType(StrEnum):
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_STARTED = "TASK_STARTED"
    TASK_BLOCKED = "TASK_BLOCKED"
    TASK_COMPLETED = "TASK_COMPLETED"

    PUSH_CREATED = "PUSH_CREATED"
    BRANCH_UPDATED = "BRANCH_UPDATED"
    MERGE_REQUIRED = "MERGE_REQUIRED"
    MERGE_CONFLICT = "MERGE_CONFLICT"
    MERGE_RESOLVED = "MERGE_RESOLVED"

    HELP_REQUESTED = "HELP_REQUESTED"
    HELP_COMPLETED = "HELP_COMPLETED"

    SME_QUESTION_CREATED = "SME_QUESTION_CREATED"
    SME_RESPONSE_RECEIVED = "SME_RESPONSE_RECEIVED"

    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVIEW_COMPLETED = "REVIEW_COMPLETED"

    SPRINT_STARTED = "SPRINT_STARTED"
    SPRINT_COMPLETED = "SPRINT_COMPLETED"
    RETROSPECTIVE_CREATED = "RETROSPECTIVE_CREATED"

    STANDUP_POSTED = "STANDUP_POSTED"
    MESSAGE_POSTED = "MESSAGE_POSTED"
    AGENT_STATE_CHANGED = "AGENT_STATE_CHANGED"
    PHASE_STARTED = "PHASE_STARTED"
    PHASE_COMPLETED = "PHASE_COMPLETED"
    RUN_LOG = "RUN_LOG"


class Event(BaseModel):
    """A single, persisted, broadcastable fact about something that happened
    in the pod. Every event is appended to GIT_ACTIVITY.md/DEVELOPMENT_LOG.md
    (as relevant) and pushed to connected frontend clients over the
    WebSocket -- this is the single source of truth the "Live Terminal" and
    conversation feed are rendered from."""

    event_id: str = Field(default_factory=lambda: new_id("evt"))
    type: EventType
    actor_id: str | None = None  # agent_id, or None for system events
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> str:
        """One-line human-readable rendering, used by the terminal feed."""
        actor = self.actor_id or "system"
        extra = ", ".join(f"{k}={v}" for k, v in self.payload.items() if k != "detail")
        return f"[{self.type}] {actor}" + (f" ({extra})" if extra else "")
