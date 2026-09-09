"""Enumerations and the task state machine.

The task lifecycle (PRD §30, phased plan §3.3) is enforced here: invalid
transitions raise instead of silently corrupting project state.
"""

from __future__ import annotations

from enum import Enum


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BacklogItemKind(str, Enum):
    EPIC = "EPIC"
    FEATURE = "FEATURE"
    STORY = "STORY"
    TASK = "TASK"
    SUBTASK = "SUBTASK"


class TaskStatus(str, Enum):
    BACKLOG = "BACKLOG"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    TESTING = "TESTING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    REOPENED = "REOPENED"
    CANCELLED = "CANCELLED"


class SprintStatus(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    RETROSPECTIVE = "RETROSPECTIVE"
    COMPLETE = "COMPLETE"


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class ProjectStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class HumanMode(str, Enum):
    """PRD §26 — configurable levels of human intervention."""
    AUTONOMOUS = "AUTONOMOUS"
    APPROVAL = "APPROVAL"
    SUPERVISED = "SUPERVISED"


# --- Task state machine ----------------------------------------------------

# Allowed transitions. Anything not listed is rejected by ``validate_transition``.
_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.BACKLOG: {TaskStatus.READY, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.ASSIGNED, TaskStatus.BACKLOG, TaskStatus.CANCELLED},
    TaskStatus.ASSIGNED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.READY,
        TaskStatus.BLOCKED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.IN_REVIEW,
        TaskStatus.TESTING,
        TaskStatus.BLOCKED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_REVIEW: {
        TaskStatus.TESTING,
        TaskStatus.IN_PROGRESS,  # review requested changes
        TaskStatus.BLOCKED,
    },
    TaskStatus.TESTING: {
        TaskStatus.DONE,
        TaskStatus.IN_PROGRESS,  # tests failed, back to the author
        TaskStatus.BLOCKED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.ASSIGNED,
        TaskStatus.READY,
        TaskStatus.CANCELLED,
    },
    TaskStatus.DONE: {TaskStatus.REOPENED},
    TaskStatus.REOPENED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.ASSIGNED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.CANCELLED: set(),
}

# Terminal-ish states an item can never leave (CANCELLED) or only leave via reopen.
TERMINAL_TASK_STATES: frozenset[TaskStatus] = frozenset({TaskStatus.CANCELLED})
COMPLETED_TASK_STATES: frozenset[TaskStatus] = frozenset({TaskStatus.DONE})


class InvalidTransition(ValueError):
    """Raised when a task is moved between states along a disallowed edge."""


def allowed_task_transitions(current: TaskStatus) -> set[TaskStatus]:
    return set(_TASK_TRANSITIONS.get(current, set()))


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    if current == target:
        return True  # idempotent no-op
    return target in _TASK_TRANSITIONS.get(current, set())


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(
            f"cannot move task {current.value} -> {target.value}; "
            f"allowed: {sorted(s.value for s in allowed_task_transitions(current))}"
        )
