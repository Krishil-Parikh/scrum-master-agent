"""Sprint entity and the sprint lifecycle (phased plan §4.4)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..ids import now_ts, sprint_id
from .enums import SprintStatus


class SprintReview(BaseModel):
    planned: list[str] = Field(default_factory=list)     # task ids committed to
    completed: list[str] = Field(default_factory=list)
    incomplete: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)
    commits: int = 0
    prs_merged: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    velocity: float = 0.0                                 # completed estimate sum
    notes: str = ""
    generated_at: float = Field(default_factory=now_ts)


class RetroItem(BaseModel):
    category: str          # "went_well" | "went_poorly" | "change"
    text: str


class Retrospective(BaseModel):
    items: list[RetroItem] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)  # carried into next sprint
    generated_at: float = Field(default_factory=now_ts)


class Sprint(BaseModel):
    id: str = Field(default_factory=sprint_id)
    number: int                                           # 1-based, per project
    goal: str = ""
    status: SprintStatus = SprintStatus.PLANNING
    task_ids: list[str] = Field(default_factory=list)
    assignments: dict[str, str] = Field(default_factory=dict)  # task id -> agent id

    # "duration" is measured in standup ticks, not wall-clock (see config).
    planned_ticks: int = 5
    elapsed_ticks: int = 0

    started_at: float | None = None
    ended_at: float | None = None

    review: SprintReview | None = None
    retrospective: Retrospective | None = None

    created_at: float = Field(default_factory=now_ts)
    updated_at: float = Field(default_factory=now_ts)
