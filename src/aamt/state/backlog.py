"""Pure functions over a set of tasks: dependency resolution, ready-set, cycles.

Kept free of I/O so it is trivially testable (phased plan §3.2).
"""

from __future__ import annotations

from collections.abc import Iterable

from ..models.enums import COMPLETED_TASK_STATES, TaskStatus
from ..models.task import Task


class DependencyCycle(ValueError):
    """Raised when task dependencies form a cycle (phased plan §32)."""


def _by_id(tasks: Iterable[Task]) -> dict[str, Task]:
    return {t.id: t for t in tasks}


def blocking_dependencies(task: Task, tasks: Iterable[Task]) -> list[str]:
    """Dependency task ids that are not yet DONE (or don't exist)."""
    index = _by_id(tasks)
    blocking: list[str] = []
    for dep in task.dependencies:
        dep_task = index.get(dep)
        if dep_task is None or dep_task.status not in COMPLETED_TASK_STATES:
            blocking.append(dep)
    return blocking


def is_ready(task: Task, tasks: Iterable[Task]) -> bool:
    """A task is ready if it's actionable and all its dependencies are DONE."""
    if task.status in {
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.IN_REVIEW,
        TaskStatus.TESTING,
    }:
        return False
    return not blocking_dependencies(task, tasks)


def ready_tasks(tasks: Iterable[Task]) -> list[Task]:
    tasks = list(tasks)
    return [t for t in tasks if is_ready(t, tasks)]


def validate_no_cycles(tasks: Iterable[Task]) -> None:
    """Raise :class:`DependencyCycle` if the dependency graph has a cycle."""
    index = _by_id(tasks)
    WHITE, GRAY, BLACK = 0, 1, 2
    colour = {tid: WHITE for tid in index}

    def visit(tid: str, path: list[str]) -> None:
        colour[tid] = GRAY
        path.append(tid)
        for dep in index[tid].dependencies:
            if dep not in index:
                continue
            if colour[dep] == GRAY:
                cycle = path[path.index(dep):] + [dep]
                raise DependencyCycle(" -> ".join(cycle))
            if colour[dep] == WHITE:
                visit(dep, path)
        path.pop()
        colour[tid] = BLACK

    for tid in index:
        if colour[tid] == WHITE:
            visit(tid, [])


def topological_order(tasks: Iterable[Task]) -> list[Task]:
    """Return tasks ordered so dependencies come before dependents.

    Raises :class:`DependencyCycle` if that is impossible.
    """
    tasks = list(tasks)
    index = _by_id(tasks)
    validate_no_cycles(tasks)

    visited: set[str] = set()
    order: list[Task] = []

    def visit(tid: str) -> None:
        if tid in visited:
            return
        visited.add(tid)
        for dep in index[tid].dependencies:
            if dep in index:
                visit(dep)
        order.append(index[tid])

    for t in tasks:
        visit(t.id)
    return order
