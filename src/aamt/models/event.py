"""The event model and the canonical event-type vocabulary (PRD §29, phase 9.1).

The event log is append-only and is the project's source of truth for reporting
and for answering "what actually happened during Sprint 2?".
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ..ids import event_id, now_ts


class EventType(str, Enum):
    # project / lifecycle
    PROJECT_CREATED = "PROJECT_CREATED"
    TEAM_FORMED = "TEAM_FORMED"
    BACKLOG_CREATED = "BACKLOG_CREATED"
    BACKLOG_ITEM_ADDED = "BACKLOG_ITEM_ADDED"
    PROJECT_COMPLETED = "PROJECT_COMPLETED"
    PROJECT_ABANDONED = "PROJECT_ABANDONED"

    # sprint
    SPRINT_PLANNED = "SPRINT_PLANNED"
    SPRINT_STARTED = "SPRINT_STARTED"
    SPRINT_REVIEW_STARTED = "SPRINT_REVIEW_STARTED"
    SPRINT_REVIEWED = "SPRINT_REVIEWED"
    RETROSPECTIVE_COMPLETED = "RETROSPECTIVE_COMPLETED"
    SPRINT_COMPLETED = "SPRINT_COMPLETED"

    # task
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_STARTED = "TASK_STARTED"
    TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED"
    AGENT_PROGRESS_REPORTED = "AGENT_PROGRESS_REPORTED"
    TASK_COMPLETION_CLAIMED = "TASK_COMPLETION_CLAIMED"
    TASK_VERIFIED = "TASK_VERIFIED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_REOPENED = "TASK_REOPENED"
    NEW_TASK_PROPOSED = "NEW_TASK_PROPOSED"

    # blockers / collaboration
    BLOCKER_CREATED = "BLOCKER_CREATED"
    BLOCKER_RESOLVED = "BLOCKER_RESOLVED"
    AGENT_MESSAGE_SENT = "AGENT_MESSAGE_SENT"
    DECISION_RECORDED = "DECISION_RECORDED"

    # repository / integration
    COMMIT_CREATED = "COMMIT_CREATED"
    BRANCH_CREATED = "BRANCH_CREATED"
    PULL_REQUEST_CREATED = "PULL_REQUEST_CREATED"
    CODE_REVIEW_COMPLETED = "CODE_REVIEW_COMPLETED"
    MERGE_COMPLETED = "MERGE_COMPLETED"
    MERGE_CONFLICT = "MERGE_CONFLICT"

    # testing
    TEST_RUN_STARTED = "TEST_RUN_STARTED"
    TEST_PASSED = "TEST_PASSED"
    TEST_FAILED = "TEST_FAILED"

    # standups
    STANDUP_STARTED = "STANDUP_STARTED"
    STANDUP_COMPLETED = "STANDUP_COMPLETED"

    # failure handling
    AGENT_FAILED = "AGENT_FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"


class Event(BaseModel):
    id: str = Field(default_factory=event_id)
    type: EventType
    ts: float = Field(default_factory=now_ts)
    project_id: str | None = None
    sprint_id: str | None = None
    agent_id: str | None = None
    task_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def summary(self) -> str:
        who = self.agent_id or "system"
        what = self.task_id or self.sprint_id or self.project_id or ""
        return f"{self.type.value} {who} {what}".strip()
