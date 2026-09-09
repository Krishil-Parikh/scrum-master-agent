from aamt.events.bus import EventBus
from aamt.models import (
    Agent, Priority, Project, Sprint, SprintReview, Task, TaskStatus,
)
from aamt.models.enums import BacklogItemKind
from aamt.models.event import EventType
from aamt.agents.roles import DEVELOPER_ROLES
from aamt.reporting import (
    agent_report, daily_report, final_report, project_timeline, sprint_report,
)
from aamt.state.store import ProjectStore


def _seed(tmp_path):
    store = ProjectStore(tmp_path / "s.db")
    bus = EventBus(tmp_path / "e.db")

    project = Project(name="demo", problem_statement="build a task list API",
                      acceptance_criteria=["pytest passes"])
    project.sprint_count = 1
    store.save_project(project)

    be = Agent(spec=DEVELOPER_ROLES["backend"])
    be.completed_tasks = ["T-1"]
    store.save_agent(be)

    t1 = Task(id="T-1", kind=BacklogItemKind.TASK, title="build API", role="backend",
              priority=Priority.HIGH, estimate=3)
    t1.advance_to(TaskStatus.DONE, actor=be.id)
    t1.commits = ["abc12345"]
    t2 = Task(id="T-2", kind=BacklogItemKind.TASK, title="frontend", role="frontend")
    t2.advance_to(TaskStatus.BLOCKED, actor="scrum-master")
    store.save_tasks([t1, t2])

    sprint = Sprint(id="S-1", number=1, goal="ship API", task_ids=["T-1", "T-2"])
    sprint.review = SprintReview(planned=["T-1", "T-2"], completed=["T-1"],
                                 incomplete=["T-2"], blocked=["T-2"], velocity=3, commits=1)
    store.save_sprint(sprint)

    bus.emit(EventType.PROJECT_CREATED, project_id=project.id, name="demo")
    bus.emit(EventType.SPRINT_PLANNED, project_id=project.id, sprint_id="S-1", number=1)
    bus.emit(EventType.COMMIT_CREATED, project_id=project.id, task_id="T-1", hash="abc12345")
    bus.emit(EventType.TASK_COMPLETED, project_id=project.id, task_id="T-1")
    bus.emit(EventType.MERGE_COMPLETED, project_id=project.id, task_id="T-1", target="main")
    bus.emit(EventType.ESCALATED_TO_HUMAN, project_id=project.id, task_id="T-2", note="blocked")
    return store, bus, project


def test_all_reports_render(tmp_path):
    store, bus, project = _seed(tmp_path)

    final = final_report(store, bus)
    assert "Final project report" in final
    assert "build a task list API" in final
    assert "T-1" in final and "abc12345" in final
    assert "1/2 backlog tasks completed" in final

    sr = sprint_report(store)
    assert "Sprint 1" in sr and "[x] T-1" in sr

    ar = agent_report(store, bus)
    assert "backend" in ar and "| 1 |" in ar

    tl = project_timeline(bus, project.id)
    assert "MERGE_COMPLETED" in tl or "TASK_COMPLETED" in tl

    dr = daily_report(store, bus)
    assert "Daily report" in dr and "Blocked (1)" in dr
