from aamt.ceremonies.retrospective import run_retrospective
from aamt.ceremonies.standup import run_standup
from aamt.config import Settings
from aamt.events.bus import EventBus
from aamt.models import Agent, Sprint, SprintReview, Task, TaskStatus
from aamt.agents.roles import DEVELOPER_ROLES
from aamt.state.store import ProjectStore


def _ctx(tmp_path):
    store = ProjectStore(tmp_path / "s.db")
    bus = EventBus(tmp_path / "e.db")
    settings = Settings(
        data_dir=tmp_path / "d", workspace_dir=tmp_path / "w",
        enable_standups=False, enable_retro=False,   # deterministic paths only
    )
    return store, bus, settings


def test_standup_builds_entries_and_flags_blockers(tmp_path):
    store, bus, settings = _ctx(tmp_path)
    be = Agent(spec=DEVELOPER_ROLES["backend"])
    qa = Agent(spec=DEVELOPER_ROLES["qa"])
    store.save_agent(be); store.save_agent(qa)

    done = Task(title="api", role="backend", assignee=be.id, estimate=3)
    done.advance_to(TaskStatus.DONE, actor=be.id)
    blocked = Task(title="tests", role="qa", assignee=qa.id)
    blocked.advance_to(TaskStatus.IN_PROGRESS, actor=qa.id)
    blocked.transition(TaskStatus.BLOCKED, actor=qa.id)
    store.save_tasks([done, blocked])

    sprint = Sprint(number=1, task_ids=[done.id, blocked.id],
                    assignments={done.id: be.id, blocked.id: qa.id})
    store.save_sprint(sprint)

    su = run_standup(store, bus, sprint, tick=1, settings=settings)
    roles = {e.role for e in su.entries}
    assert roles == {"backend", "qa"}
    assert blocked.id in su.flagged_blockers
    be_entry = next(e for e in su.entries if e.role == "backend")
    assert "DONE" in be_entry.yesterday
    assert store.list_standups(sprint_id=sprint.id)[0].id == su.id
    assert bus.query(sprint_id=sprint.id)  # events emitted


def test_retrospective_deterministic_from_review(tmp_path):
    store, bus, settings = _ctx(tmp_path)
    sprint = Sprint(number=1, goal="ship the API", task_ids=["T-1", "T-2", "T-3"])
    sprint.review = SprintReview(
        planned=["T-1", "T-2", "T-3"], completed=["T-1"],
        incomplete=["T-2", "T-3"], blocked=["T-2"], tests_failed=1,
    )
    store.save_sprint(sprint)

    retro = run_retrospective(store, bus, sprint, settings=settings)
    cats = {i.category for i in retro.items}
    assert "went_poorly" in cats
    assert retro.action_items                       # something to carry forward
    assert store.get_sprint(sprint.id).retrospective is not None
    assert any(e.type.value == "RETROSPECTIVE_COMPLETED" for e in bus.query(sprint_id=sprint.id))
