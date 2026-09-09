import pytest

from aamt.models import InvalidTransition, Priority, Task, TaskStatus


def test_happy_path_transitions_and_history():
    t = Task(title="demo")
    assert t.status is TaskStatus.BACKLOG

    for target in [
        TaskStatus.READY,
        TaskStatus.ASSIGNED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.TESTING,
        TaskStatus.DONE,
    ]:
        t.transition(target, actor="A-1")

    assert t.status is TaskStatus.DONE
    status_changes = [h for h in t.history if h.field == "status"]
    assert [h.new for h in status_changes] == [
        "READY", "ASSIGNED", "IN_PROGRESS", "TESTING", "DONE",
    ]
    assert all(h.actor == "A-1" for h in status_changes)


def test_invalid_transition_rejected():
    t = Task(title="demo")
    with pytest.raises(InvalidTransition):
        t.transition(TaskStatus.DONE)          # BACKLOG -> DONE not allowed
    assert t.status is TaskStatus.BACKLOG      # unchanged


def test_idempotent_transition_is_noop():
    t = Task(title="demo")
    t.transition(TaskStatus.READY)
    n = len(t.history)
    t.transition(TaskStatus.READY)             # same state
    assert len(t.history) == n


def test_blocked_and_reopen_cycle():
    t = Task(title="demo")
    for s in [TaskStatus.READY, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
        t.transition(s)
    t.transition(TaskStatus.BLOCKED, note="waiting on schema")
    t.transition(TaskStatus.IN_PROGRESS)
    t.transition(TaskStatus.TESTING)
    t.transition(TaskStatus.DONE)
    t.transition(TaskStatus.REOPENED, actor="scrum-master", note="regression")
    assert t.status is TaskStatus.REOPENED
    t.transition(TaskStatus.IN_PROGRESS)
    assert t.status is TaskStatus.IN_PROGRESS


def test_priority_and_assignee_history():
    t = Task(title="demo")
    t.set_priority(Priority.HIGH, actor="scrum-master")
    t.reassign("A-2", actor="scrum-master")
    fields = {h.field for h in t.history}
    assert {"priority", "assignee"} <= fields


def test_evidence_tracking():
    t = Task(title="demo")
    assert not t.has_evidence
    t.add_evidence(commit="abc123", actor="A-1")
    assert t.has_evidence and "abc123" in t.commits
