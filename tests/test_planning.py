from aamt.agents.roles import MVP_TEAM
from aamt.models import Agent, BacklogItemKind, Priority, Task, TaskStatus
from aamt.planning.backlog_planner import materialize_backlog
from aamt.planning.schemas import (
    BacklogPlan,
    PlannedCriterion,
    PlannedFeature,
    PlannedStory,
    PlannedTask,
)
from aamt.planning.sprint_planner import plan_sprint


def _plan() -> BacklogPlan:
    return BacklogPlan(
        epic="Task list API",
        features=[
            PlannedFeature(
                title="Persistence",
                stories=[
                    PlannedStory(
                        title="Schema",
                        tasks=[
                            PlannedTask(
                                ref="t1", title="Create DB schema", description="users + tasks",
                                role="database", priority="HIGH", estimate=3,
                                acceptance_criteria=[PlannedCriterion(text="tables exist")],
                            ),
                            PlannedTask(
                                ref="t2", title="Tasks REST API", description="CRUD",
                                role="backend", priority="HIGH", estimate=5, depends_on=["t1"],
                                acceptance_criteria=[PlannedCriterion(text="GET /tasks 200", check="true")],
                            ),
                        ],
                    )
                ],
            ),
            PlannedFeature(
                title="UI",
                stories=[
                    PlannedStory(
                        title="List page",
                        tasks=[
                            PlannedTask(
                                ref="t3", title="Task list page", description="render tasks",
                                role="frontend", priority="MEDIUM", estimate=5, depends_on=["t2"],
                            )
                        ],
                    )
                ],
            ),
        ],
    )


def test_materialize_builds_hierarchy_and_wires_deps():
    tasks = materialize_backlog(_plan())
    kinds = {t.kind for t in tasks}
    assert {BacklogItemKind.EPIC, BacklogItemKind.FEATURE, BacklogItemKind.STORY, BacklogItemKind.TASK} <= kinds

    work = [t for t in tasks if t.kind is BacklogItemKind.TASK]
    assert len(work) == 3
    api = next(t for t in work if t.title == "Tasks REST API")
    schema = next(t for t in work if t.title == "Create DB schema")
    assert api.dependencies == [schema.id]
    assert api.role == "backend"
    assert api.acceptance_criteria[0].check == "true"


def _agents() -> list[Agent]:
    return [Agent(spec=s) for s in MVP_TEAM]


def test_sprint_planner_respects_priority_deps_and_capacity():
    tasks = materialize_backlog(_plan())
    for t in tasks:
        if t.kind is BacklogItemKind.TASK:
            t.status = TaskStatus.READY

    plan = plan_sprint(tasks, _agents(), capacity_points=3, max_tasks=8)
    # only the HIGH, dependency-free, estimate-3 schema task is eligible + fits
    selected = [t for t in tasks if t.id in plan.task_ids]
    assert [t.title for t in selected] == ["Create DB schema"]
    # dependency-blocked tasks are not eligible, so they're simply absent
    titles_in = {t.title for t in selected}
    assert "Tasks REST API" not in titles_in and "Task list page" not in titles_in


def test_sprint_planner_assigns_by_role():
    tasks = materialize_backlog(_plan())
    work = {t.title: t for t in tasks if t.kind is BacklogItemKind.TASK}
    for t in work.values():
        t.status = TaskStatus.READY
    # unblock the API task
    work["Tasks REST API"].dependencies = []

    agents = _agents()
    plan = plan_sprint(tasks, agents, capacity_points=100, max_tasks=8)
    role_by_agent = {a.id: a.role for a in agents}
    assert role_by_agent[plan.assignments[work["Create DB schema"].id]] == "database"
    assert role_by_agent[plan.assignments[work["Tasks REST API"].id]] == "backend"


def test_advance_to_walks_state_machine():
    t = Task(title="x")  # BACKLOG
    assert t.advance_to(TaskStatus.ASSIGNED)
    assert t.status is TaskStatus.ASSIGNED
    # history should show the intermediate READY hop
    assert [h.new for h in t.history if h.field == "status"] == ["READY", "ASSIGNED"]
    # REOPENED is only reachable *through* DONE, which advance_to won't route through
    assert not t.advance_to(TaskStatus.REOPENED)
    assert t.status is TaskStatus.ASSIGNED

    # but a real completion path still works
    assert t.advance_to(TaskStatus.DONE)
    assert t.status is TaskStatus.DONE
    assert t.advance_to(TaskStatus.REOPENED)  # now legal: DONE -> REOPENED
