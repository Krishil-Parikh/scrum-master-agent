import pytest

from aamt.models import Task, TaskStatus
from aamt.state.backlog import (
    DependencyCycle,
    blocking_dependencies,
    ready_tasks,
    topological_order,
    validate_no_cycles,
)


def _task(title, deps=None, status=TaskStatus.READY):
    t = Task(title=title)
    t.status = status
    for d in deps or []:
        t.dependencies.append(d)
    return t


def test_blocking_dependencies_reports_unfinished():
    a = _task("a", status=TaskStatus.IN_PROGRESS)
    b = _task("b", deps=[a.id])
    assert blocking_dependencies(b, [a, b]) == [a.id]

    a.status = TaskStatus.DONE
    assert blocking_dependencies(b, [a, b]) == []


def test_ready_tasks_excludes_blocked_and_in_flight():
    a = _task("a")
    b = _task("b", deps=[a.id])
    c = _task("c", status=TaskStatus.IN_PROGRESS)
    ready = {t.id for t in ready_tasks([a, b, c])}
    assert ready == {a.id}          # b blocked by a, c already in progress


def test_missing_dependency_counts_as_blocking():
    b = _task("b", deps=["T-doesnotexist"])
    assert blocking_dependencies(b, [b]) == ["T-doesnotexist"]
    assert b not in ready_tasks([b])


def test_cycle_detection():
    a = _task("a")
    b = _task("b", deps=[a.id])
    a.dependencies.append(b.id)     # a <-> b
    with pytest.raises(DependencyCycle):
        validate_no_cycles([a, b])
    with pytest.raises(DependencyCycle):
        topological_order([a, b])


def test_topological_order_respects_dependencies():
    a = _task("a")
    b = _task("b", deps=[a.id])
    c = _task("c", deps=[b.id])
    order = [t.id for t in topological_order([c, b, a])]
    assert order.index(a.id) < order.index(b.id) < order.index(c.id)
