"""Agent identity and state schema (PRD §7, §31, §32; Roadmap Phase 1/2)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class AgentSpecialty(StrEnum):
    """A developer agent's primary specialization. Scrum Master has no
    development specialty of its own -- it coordinates."""

    SCRUM_MASTER = "scrum_master"
    FRONTEND = "frontend"
    BACKEND = "backend"
    AI_ML = "ai_ml"
    DEVOPS = "devops"
    MLOPS = "mlops"
    DATABASE = "database"


class AgentState(StrEnum):
    """Lifecycle state of a single agent (PRD §31)."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"
    HELPING = "helping"
    SYNCING = "syncing"
    RESOLVING_CONFLICT = "resolving_conflict"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentIdentity(BaseModel):
    """Static identity for one agent -- who it is, not what it's doing right
    now (that's AgentStatus, tracked separately by the registry)."""

    agent_id: str
    display_name: str
    specialty: AgentSpecialty
    branch: str | None = None  # e.g. "developer-2"; None for the Scrum Master
    color: str = "#94d82d"
    avatar_initials: str = "AG"


class AgentStatus(BaseModel):
    """Live, mutable status for one agent. Owned by the AgentRegistry and
    updated as work progresses; this is what the dashboard's agent list and
    "online" indicators are built from."""

    agent_id: str
    state: AgentState = AgentState.IDLE
    current_task_id: str | None = None
    loaded_skills: list[str] = Field(default_factory=list)
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    online: bool = True
    note: str = ""

    def touch(self) -> None:
        self.last_active_at = datetime.now(timezone.utc)
