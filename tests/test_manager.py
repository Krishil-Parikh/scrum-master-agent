from aamt.agents.manager import AgentManager
from aamt.models import AgentStatus, Task, TaskStatus
from aamt.state.store import ProjectStore


def _store(tmp_path) -> ProjectStore:
    return ProjectStore(tmp_path / "state.db")


def test_form_team_is_idempotent(tmp_path):
    store = _store(tmp_path)
    mgr = AgentManager(store)
    first = mgr.form_team()
    assert len(first) == 7
    again = mgr.form_team()
    assert again == []                      # nothing new created
    assert len(mgr.team()) == 7
    assert mgr.scrum_master() is not None
    assert len(mgr.developers()) == 6


def test_assign_and_record_result(tmp_path):
    store = _store(tmp_path)
    mgr = AgentManager(store)
    mgr.form_team()
    backend = store.agent_by_role("backend")

    mgr.assign(backend.id, "T-1")
    assert mgr.get(backend.id).status is AgentStatus.WORKING
    assert mgr.get(backend.id).current_task == "T-1"

    mgr.record_result(backend.id, "T-1", ok=True)
    a = mgr.get(backend.id)
    assert a.status is AgentStatus.IDLE
    assert a.current_task is None
    assert "T-1" in a.completed_tasks

    mgr.record_result(backend.id, "T-2", ok=False)
    a = mgr.get(backend.id)
    assert a.status is AgentStatus.FAILED and "T-2" in a.failed_tasks
    mgr.recover(backend.id)
    assert mgr.get(backend.id).status is AgentStatus.IDLE


def test_workload_and_best_for(tmp_path):
    store = _store(tmp_path)
    mgr = AgentManager(store)
    mgr.form_team()

    t = Task(title="Build the REST API with authentication", role="backend")
    t.status = TaskStatus.ASSIGNED
    t.assignee = store.agent_by_role("backend").id
    store.save_task(t)

    load = mgr.workload()
    assert load[store.agent_by_role("backend").id] == 1

    pick = mgr.best_for(role_hint="backend", required_caps=["rest", "authentication"])
    assert pick.role == "backend"


def test_mailbox_roundtrip(tmp_path):
    store = _store(tmp_path)
    mgr = AgentManager(store)
    mgr.form_team()
    be = store.agent_by_role("backend").id
    fe = store.agent_by_role("frontend").id

    mgr.mailbox(be).send(fe, "API_CONTRACT_UPDATE", "POST /tasks now returns 201")
    inbox = mgr.mailbox(fe).drain()
    assert len(inbox) == 1 and inbox[0].type == "API_CONTRACT_UPDATE"
    assert mgr.mailbox(fe).drain() == []   # marked read
