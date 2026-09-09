import pytest

from aamt.models import (
    Agent,
    Priority,
    Project,
    Sprint,
    Task,
    TaskStatus,
)
from aamt.agents.roles import DEVELOPER_ROLES
from aamt.state.backlog import DependencyCycle
from aamt.state.store import ProjectStore


def test_project_roundtrip(tmp_path):
    store = ProjectStore(tmp_path / "state.db")
    p = Project(name="demo", problem_statement="build a thing")
    store.save_project(p)

    store2 = ProjectStore(tmp_path / "state.db")
    loaded = store2.get_project()
    assert loaded is not None
    assert loaded.id == p.id
    assert loaded.problem_statement == "build a thing"


def test_task_listing_and_filters(tmp_path):
    store = ProjectStore(tmp_path / "state.db")
    a = Task(title="a", priority=Priority.HIGH)
    b = Task(title="b")
    b.status = TaskStatus.DONE
    store.save_tasks([a, b])

    assert {t.id for t in store.list_tasks()} == {a.id, b.id}
    assert [t.id for t in store.list_tasks(status=TaskStatus.DONE)] == [b.id]


def test_ready_tasks_uses_dependency_graph(tmp_path):
    store = ProjectStore(tmp_path / "state.db")
    a = Task(title="schema")
    a.status = TaskStatus.READY
    b = Task(title="api")
    b.status = TaskStatus.READY
    b.dependencies.append(a.id)
    store.save_tasks([a, b])

    ready_ids = {t.id for t in store.ready_tasks()}
    assert ready_ids == {a.id}

    a.status = TaskStatus.DONE
    store.save_task(a)
    ready_ids = {t.id for t in store.ready_tasks()}
    assert b.id in ready_ids


def test_validate_backlog_detects_cycle(tmp_path):
    store = ProjectStore(tmp_path / "state.db")
    a = Task(title="a")
    b = Task(title="b")
    a.dependencies.append(b.id)
    b.dependencies.append(a.id)
    store.save_tasks([a, b])
    with pytest.raises(DependencyCycle):
        store.validate_backlog()


def test_agent_and_sprint_persistence(tmp_path):
    store = ProjectStore(tmp_path / "state.db")
    agent = Agent(spec=DEVELOPER_ROLES["backend"])
    store.save_agent(agent)
    assert store.agent_by_role("backend").id == agent.id

    sprint = Sprint(number=1, goal="first slice")
    store.save_sprint(sprint)
    assert store.list_sprints()[0].goal == "first slice"
