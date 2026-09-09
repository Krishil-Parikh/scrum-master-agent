"""Backlog items / tasks.

A ``Task`` is the unit of work an agent picks up. It carries its own change
history (PRD §10) so a reviewer or the final report can reconstruct exactly how
it evolved — priority changes, reassignments, every state transition.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..ids import now_ts, task_id
from .enums import (
    BacklogItemKind,
    Priority,
    TaskStatus,
    validate_transition,
)


class AcceptanceCriterion(BaseModel):
    """One checkable statement of done-ness.

    ``check`` is an optional shell command whose exit code 0 means satisfied;
    when absent the criterion is validated by the reviewer agent / LLM judge.
    """

    text: str
    check: str | None = None
    satisfied: bool | None = None  # None = not yet evaluated


class TaskHistoryEntry(BaseModel):
    ts: float = Field(default_factory=now_ts)
    field: str                      # "status" | "priority" | "assignee" | ...
    old: Any = None
    new: Any = None
    note: str | None = None
    actor: str | None = None        # agent id or "scrum-master" / "human"


class Task(BaseModel):
    id: str = Field(default_factory=task_id)
    kind: BacklogItemKind = BacklogItemKind.TASK
    title: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.BACKLOG

    parent_id: str | None = None                 # epic/feature/story linkage
    assignee: str | None = None                  # agent id
    role: str | None = None                      # suggested owner role (backend|frontend|...)
    dependencies: list[str] = Field(default_factory=list)  # task ids that must be DONE first

    estimate: float | None = None                # story points or hours (unit is project config)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)

    sprint_id: str | None = None
    branch: str | None = None                    # task/T-xxxxx working branch
    labels: list[str] = Field(default_factory=list)

    # Evidence of completion (PRD §12) — never trust a bare "done".
    commits: list[str] = Field(default_factory=list)
    pull_request: str | None = None
    artifacts: list[str] = Field(default_factory=list)

    created_at: float = Field(default_factory=now_ts)
    updated_at: float = Field(default_factory=now_ts)
    history: list[TaskHistoryEntry] = Field(default_factory=list)

    # --- mutation helpers (all record history + bump updated_at) ----------

    def _record(self, field: str, old: Any, new: Any, *, actor: str | None, note: str | None) -> None:
        self.history.append(
            TaskHistoryEntry(field=field, old=old, new=new, actor=actor, note=note)
        )
        self.updated_at = now_ts()

    def transition(
        self,
        target: TaskStatus,
        *,
        actor: str | None = None,
        note: str | None = None,
    ) -> None:
        """Move to ``target``, enforcing the state machine in ``enums``."""
        validate_transition(self.status, target)
        if target == self.status:
            return
        old = self.status
        self.status = target
        self._record("status", old.value, target.value, actor=actor, note=note)

    def advance_to(
        self,
        target: TaskStatus,
        *,
        actor: str | None = None,
        note: str | None = None,
    ) -> bool:
        """Walk allowed transitions to reach ``target`` (shortest path).

        Returns True if ``target`` was reached. Used when a caller knows the
        destination but not the exact intermediate states (e.g. BACKLOG->ASSIGNED
        goes via READY).
        """
        from collections import deque

        from .enums import (
            COMPLETED_TASK_STATES,
            TERMINAL_TASK_STATES,
            allowed_task_transitions,
        )

        if self.status == target:
            return True
        # BFS over the transition graph; never *route through* a completed or
        # terminal state (so "advance to BLOCKED" can't sneak via DONE).
        blocked_intermediate = (COMPLETED_TASK_STATES | TERMINAL_TASK_STATES) - {target}
        prev: dict[TaskStatus, TaskStatus] = {}
        seen = {self.status}
        q: deque[TaskStatus] = deque([self.status])
        while q:
            cur = q.popleft()
            if cur == target:
                break
            for nxt in allowed_task_transitions(cur):
                if nxt in seen or nxt in blocked_intermediate:
                    continue
                seen.add(nxt)
                prev[nxt] = cur
                q.append(nxt)
        if target not in prev and self.status != target:
            return False
        # reconstruct path
        path: list[TaskStatus] = [target]
        while path[-1] != self.status:
            path.append(prev[path[-1]])
        for step in reversed(path[:-1]):
            self.transition(step, actor=actor, note=note)
        return True

    def reassign(self, agent: str | None, *, actor: str | None = None, note: str | None = None) -> None:
        if agent == self.assignee:
            return
        old = self.assignee
        self.assignee = agent
        self._record("assignee", old, agent, actor=actor, note=note)

    def set_priority(self, priority: Priority, *, actor: str | None = None, note: str | None = None) -> None:
        if priority == self.priority:
            return
        old = self.priority
        self.priority = priority
        self._record("priority", old.value, priority.value, actor=actor, note=note)

    def add_dependency(self, dep_task_id: str, *, actor: str | None = None) -> None:
        if dep_task_id == self.id or dep_task_id in self.dependencies:
            return
        self.dependencies.append(dep_task_id)
        self._record("dependencies", None, dep_task_id, actor=actor, note="added dependency")

    def add_evidence(
        self,
        *,
        commit: str | None = None,
        pull_request: str | None = None,
        artifact: str | None = None,
        actor: str | None = None,
    ) -> None:
        if commit:
            self.commits.append(commit)
            self._record("commits", None, commit, actor=actor, note="commit")
        if pull_request:
            self.pull_request = pull_request
            self._record("pull_request", None, pull_request, actor=actor, note="PR")
        if artifact:
            self.artifacts.append(artifact)
            self._record("artifacts", None, artifact, actor=actor, note="artifact")

    @property
    def has_evidence(self) -> bool:
        return bool(self.commits or self.pull_request or self.artifacts)
