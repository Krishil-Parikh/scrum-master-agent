"""The Project entity — the top-level container the human creates (PRD §FR-1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..ids import now_ts, project_id
from .enums import HumanMode, ProjectStatus


class ProjectConstraints(BaseModel):
    language: str | None = None
    framework: str | None = None
    infrastructure: str | None = None
    coding_standards: str | None = None
    testing_requirements: str | None = None
    deadline: str | None = None
    token_budget: int | None = None


class Project(BaseModel):
    id: str = Field(default_factory=project_id)
    name: str
    problem_statement: str
    requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: ProjectConstraints = Field(default_factory=ProjectConstraints)

    status: ProjectStatus = ProjectStatus.CREATED
    human_mode: HumanMode = HumanMode.APPROVAL

    repo_path: str | None = None       # absolute path to the shared working repo
    current_sprint_id: str | None = None
    sprint_count: int = 0

    created_at: float = Field(default_factory=now_ts)
    updated_at: float = Field(default_factory=now_ts)
