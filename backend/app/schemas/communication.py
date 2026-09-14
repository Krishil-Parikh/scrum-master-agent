"""Agent<->agent and agent<->SME communication schema (PRD §12, §18)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from app.utils.ids import new_id


class MessageChannel(StrEnum):
    """Matches the frontend's conversation filter tabs (All/Scrum/Developers/
    SME/System/Git/Tasks)."""

    SCRUM = "scrum"
    DEVELOPERS = "developers"
    SME = "sme"
    SYSTEM = "system"
    GIT = "git"
    TASKS = "tasks"


class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: new_id("msg"))
    channel: MessageChannel
    sender_id: str  # agent_id, "sme", or "human"
    sender_name: str
    sender_role: str = ""  # e.g. "Scrum" / "Developer" -- shown as a badge
    text: str
    mentions: list[str] = Field(default_factory=list)
    reply_to: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SMEQuestion(BaseModel):
    """An agent's question to the Business SME (PRD §12, §6.2)."""

    question_id: str = Field(default_factory=lambda: new_id("q"))
    asked_by: str  # agent_id
    asked_by_name: str
    text: str
    reason: str = ""
    priority: str = "medium"  # low | medium | high
    impacted_requirements: list[str] = Field(default_factory=list)
    status: str = "open"  # open | answered | cancelled
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SMEAnswer(BaseModel):
    answer_id: str = Field(default_factory=lambda: new_id("a"))
    question_id: str
    text: str
    decision: str = ""
    answered_by: str = "Business SME"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
