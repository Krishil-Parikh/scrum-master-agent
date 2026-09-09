"""Deterministic sprint planning + assignment (phased plan §4.2, §4.3).

No optimisation, no LLM — a transparent scoring pass so a failed sprint is easy
to diagnose. Inputs: the backlog, the team, remaining capacity. Output: which
tasks enter the sprint and who owns each.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Settings, get_settings
from ..models.agent import Agent
from ..models.enums import BacklogItemKind, Priority, TaskStatus
from ..models.task import Task
from ..state.backlog import is_ready

_PRIORITY_RANK = {
    Priority.CRITICAL: 3,
    Priority.HIGH: 2,
    Priority.MEDIUM: 1,
    Priority.LOW: 0,
}

_SELECTABLE = {
    TaskStatus.BACKLOG,
    TaskStatus.READY,
    TaskStatus.ASSIGNED,
    TaskStatus.REOPENED,
}


@dataclass
class SprintPlan:
    task_ids: list[str] = field(default_factory=list)
    assignments: dict[str, str] = field(default_factory=dict)   # task_id -> agent_id
    goal_hint: str = ""
    rationale: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)           # eligible but over capacity


def _required_caps(task: Task) -> list[str]:
    from ..agents.roles import DEVELOPER_ROLES  # lazy: avoids planning<->agents cycle

    spec = DEVELOPER_ROLES.get(task.role or "")
    if not spec:
        return []
    text = f"{task.title} {task.description}".lower()
    hit = [c for c in spec.capabilities if c.lower() in text]
    return hit or spec.capabilities[:2]


def _pick_agent(task: Task, agents: list[Agent], load: dict[str, str | int]) -> Agent | None:
    devs = [a for a in agents if not a.spec.is_coordinator]
    if not devs:
        return None
    caps = _required_caps(task)

    def score(a: Agent) -> tuple[float, float, int]:
        role_bonus = 1.0 if task.role and a.role == task.role else 0.0
        return (role_bonus, a.capability_score(caps), -int(load.get(a.id, 0)))

    return max(devs, key=score)


def plan_sprint(
    tasks: list[Task],
    agents: list[Agent],
    *,
    settings: Settings | None = None,
    workload: dict[str, int] | None = None,
    capacity_points: float | None = None,
    max_tasks: int | None = None,
) -> SprintPlan:
    settings = settings or get_settings()
    capacity = settings.sprint_capacity_points if capacity_points is None else capacity_points
    cap_tasks = settings.sprint_max_tasks if max_tasks is None else max_tasks
    default_est = settings.default_task_estimate

    by_id = {t.id: t for t in tasks}
    load: dict[str, int] = dict(workload or {})

    eligible = [
        t
        for t in tasks
        if t.kind is BacklogItemKind.TASK
        and t.status in _SELECTABLE
        and is_ready(t, tasks)
    ]
    eligible.sort(
        key=lambda t: (
            -_PRIORITY_RANK.get(t.priority, 1),
            t.estimate or default_est,
            t.created_at,
        )
    )

    plan = SprintPlan()
    spent = 0.0
    for t in eligible:
        est = t.estimate or default_est
        if len(plan.task_ids) >= cap_tasks or (plan.task_ids and spent + est > capacity):
            plan.deferred.append(t.id)
            continue
        agent = _pick_agent(t, agents, load)
        if agent is None:
            plan.deferred.append(t.id)
            plan.rationale.append(f"{t.id}: no developer agent available")
            continue
        plan.task_ids.append(t.id)
        plan.assignments[t.id] = agent.id
        load[agent.id] = load.get(agent.id, 0) + 1
        spent += est
        plan.rationale.append(
            f"{t.id} [{t.priority.value} est={est:g}] -> {agent.role} ({agent.id})"
        )

    if plan.task_ids:
        roles = sorted({by_id[tid].role or "misc" for tid in plan.task_ids})
        plan.goal_hint = "Advance: " + ", ".join(roles)
    return plan
