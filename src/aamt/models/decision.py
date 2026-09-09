"""Decisions and agent-to-agent messages — persisted, not left in transient context.

PRD §16: "Important decisions should be persisted as project artifacts rather
than existing only in transient agent context."
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..ids import decision_id, message_id, now_ts


class Decision(BaseModel):
    id: str = Field(default_factory=decision_id)
    context: str                     # what prompted it
    decision: str                    # what was decided
    reason: str = ""                 # why
    author: str = "scrum-master"     # agent id / "scrum-master" / "human"
    sprint_id: str | None = None
    related_tasks: list[str] = Field(default_factory=list)
    ts: float = Field(default_factory=now_ts)


class AgentMessage(BaseModel):
    """Structured inter-agent message (phased plan §2.5)."""

    id: str = Field(default_factory=message_id)
    sender: str                      # agent id
    recipient: str                   # agent id | "scrum-master" | "broadcast"
    type: str                        # "API_CONTRACT_UPDATE" | "DEPENDENCY_NOTICE" | "QUESTION" | ...
    content: str
    related_tasks: list[str] = Field(default_factory=list)
    ts: float = Field(default_factory=now_ts)
    read: bool = False
