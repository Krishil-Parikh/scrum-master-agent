"""Agile backlog schema: Epic -> Story -> Task -> Sprint (PRD §13, §14, §30)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.agent import AgentSpecialty


class TaskStatus(StrEnum):
    """PRD §14 task state machine."""

    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETED = "completed"


class TaskRisk(StrEnum):
    """Risk is classified by blast radius/reversibility, not difficulty --
    see .claude/skills/task-decomposition. A hard-but-isolated task can be
    LOW; an easy change to shared auth/data code can be HIGH."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(BaseModel):
    task_id: str
    story_id: str
    title: str
    description: str = ""
    specialty: AgentSpecialty
    assigned_agent_id: str | None = None
    status: TaskStatus = TaskStatus.BACKLOG
    risk: TaskRisk = TaskRisk.LOW
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    branch: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    blocked_reason: str | None = None
    files_changed: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class UserStory(BaseModel):
    story_id: str
    epic_id: str
    title: str
    as_a: str = "user"
    i_want: str = ""
    so_that: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)

    @property
    def statement(self) -> str:
        return f"As a {self.as_a}, I want {self.i_want}, so that {self.so_that}"


class Epic(BaseModel):
    epic_id: str
    title: str
    description: str = ""
    story_ids: list[str] = Field(default_factory=list)


class Sprint(BaseModel):
    sprint_id: str
    name: str
    goal: str = ""
    story_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    days: int = 6
    status: str = "planned"  # planned | active | review | completed


class Backlog(BaseModel):
    """The full machine-readable Agile backlog for one project (Roadmap
    Phase 7 deliverable)."""

    epics: dict[str, Epic] = Field(default_factory=dict)
    stories: dict[str, UserStory] = Field(default_factory=dict)
    tasks: dict[str, Task] = Field(default_factory=dict)
    sprints: dict[str, Sprint] = Field(default_factory=dict)
    current_sprint_id: str | None = None
