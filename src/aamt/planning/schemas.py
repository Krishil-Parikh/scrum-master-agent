"""LLM output schema for backlog decomposition (PRD §FR-2).

The model returns this shape; :func:`aamt.planning.backlog_planner.materialize_backlog`
turns it into persisted :class:`~aamt.models.task.Task` rows (Epic -> Feature ->
Story -> Task) with real ids and wired dependencies.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["backend", "frontend", "database", "ml", "qa", "devops"]
PriorityStr = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class PlannedCriterion(BaseModel):
    text: str = Field(description="One concrete, checkable statement of done-ness.")
    check: str | None = Field(
        default=None,
        description="Optional shell command that exits 0 iff the criterion holds.",
    )


class PlannedTask(BaseModel):
    ref: str = Field(description="Short local id like 't1' used to express dependencies.")
    title: str
    description: str = Field(description="What to build, precisely enough for one engineer.")
    role: Role = Field(description="Which engineer should own this.")
    priority: PriorityStr = "MEDIUM"
    estimate: float = Field(default=3.0, description="Rough effort in story points (1-8).")
    depends_on: list[str] = Field(
        default_factory=list, description="Refs of tasks that must finish first."
    )
    acceptance_criteria: list[PlannedCriterion] = Field(default_factory=list)


class PlannedStory(BaseModel):
    title: str
    tasks: list[PlannedTask] = Field(default_factory=list)


class PlannedFeature(BaseModel):
    title: str
    stories: list[PlannedStory] = Field(default_factory=list)


class BacklogPlan(BaseModel):
    epic: str = Field(description="One line naming the whole deliverable.")
    features: list[PlannedFeature] = Field(default_factory=list)

    def all_tasks(self) -> list[PlannedTask]:
        return [
            t
            for f in self.features
            for s in f.stories
            for t in s.tasks
        ]
