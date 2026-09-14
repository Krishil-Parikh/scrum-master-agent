"""
Pydantic schemas shared across the whole backend.

These are the data contracts the PRD calls out explicitly (agent config,
project config, task schema, event schema, agent state schema) -- every
layer (agents, orchestration, memory, API) imports from here rather than
redefining its own shape for the same concept, so "what does a Task look
like" has exactly one answer in the codebase.
"""

from app.schemas.agent import AgentSpecialty, AgentState, AgentStatus, AgentIdentity
from app.schemas.communication import Message, MessageChannel, SMEQuestion, SMEAnswer
from app.schemas.event import Event, EventType
from app.schemas.project import ProjectContext, Requirement, Decision, OpenQuestion
from app.schemas.task import Epic, UserStory, Task, TaskStatus, Sprint, TaskRisk

__all__ = [
    "AgentSpecialty",
    "AgentState",
    "AgentStatus",
    "AgentIdentity",
    "Message",
    "MessageChannel",
    "SMEQuestion",
    "SMEAnswer",
    "Event",
    "EventType",
    "ProjectContext",
    "Requirement",
    "Decision",
    "OpenQuestion",
    "Epic",
    "UserStory",
    "Task",
    "TaskStatus",
    "TaskRisk",
    "Sprint",
]
