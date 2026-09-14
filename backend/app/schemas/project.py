"""Project Context Engine schema (PRD §10, §32; Roadmap Phase 4)."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.utils.ids import new_id


class Requirement(BaseModel):
    requirement_id: str = Field(default_factory=lambda: new_id("req"))
    text: str
    kind: str = "functional"  # functional | non_functional | constraint
    source: str = "intake"


class Decision(BaseModel):
    """DECISIONS.md entry (PRD §26)."""

    decision_id: str = Field(default_factory=lambda: new_id("dec"))
    context: str
    decision: str
    alternatives: list[str] = Field(default_factory=list)
    reason: str = ""
    impact: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpenQuestion(BaseModel):
    question: str
    reason: str = ""
    owner: str = ""
    priority: str = "medium"
    raised_by: str = ""


class ProjectContext(BaseModel):
    """The canonical, persistent understanding of the project (PRD §10).
    Agents retrieve this rather than relying solely on their own
    conversation history -- see ProjectContextStore in
    memory/project_context.py for the load/save side of this."""

    project_id: str = Field(default_factory=lambda: new_id("proj"))
    name: str = "Untitled Project"
    objective: str = ""
    business_context: str = ""
    requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    domain_terms: dict[str, str] = Field(default_factory=dict)
    acceptance_criteria: list[str] = Field(default_factory=list)
    technology_stack: list[str] = Field(default_factory=list)
    architecture_notes: str = ""
    decisions: list[Decision] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    raw_source_text: str = ""
    current_sprint_id: str | None = None
    status: str = "intake"  # intake | analyzing | planning | in_progress | review | completed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
