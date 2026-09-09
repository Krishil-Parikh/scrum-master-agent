"""Agent identity and capability declaration (phased plan §2.1, §2.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..ids import agent_id, now_ts
from .enums import AgentStatus


class AgentSpec(BaseModel):
    """Static definition of a role — the template a runtime agent is built from."""

    role: str                              # "scrum-master", "backend", "frontend", ...
    title: str                             # human label, e.g. "Backend Engineer"
    capabilities: list[str] = Field(default_factory=list)  # ["python", "fastapi", "rest", ...]
    system_prompt: str = ""
    is_coordinator: bool = False           # True only for the Scrum Master
    model: str | None = None               # override the project default model
    max_task_retries: int = 3


class Agent(BaseModel):
    """A live agent in a project."""

    id: str = Field(default_factory=agent_id)
    spec: AgentSpec
    status: AgentStatus = AgentStatus.IDLE
    current_task: str | None = None        # task id
    completed_tasks: list[str] = Field(default_factory=list)
    failed_tasks: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=now_ts)
    updated_at: float = Field(default_factory=now_ts)

    @property
    def role(self) -> str:
        return self.spec.role

    @property
    def name(self) -> str:
        return f"{self.spec.title} ({self.id})"

    def capability_score(self, required: list[str]) -> float:
        """Fraction of ``required`` capabilities this agent declares (0..1).

        Deterministic assignment input for the Scrum Master (phased plan §4.3).
        """
        if not required:
            return 1.0
        have = {c.lower() for c in self.spec.capabilities}
        hits = sum(1 for r in required if r.lower() in have)
        return hits / len(required)
