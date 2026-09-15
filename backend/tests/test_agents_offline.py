"""
Exercises agent behavior with the LLM call stubbed out -- proves the
prompt-building / response-parsing plumbing works without spending real
OpenRouter credits on every test run. Live-model correctness is verified
separately via scripts/run_demo.py against the real API (see backend/README.md).
"""

from __future__ import annotations

import pytest

import app.agents.base as base_module
from app.agents.frontend_agent import FrontendAgent
from app.agents.scrum_master import ScrumMasterAgent
from app.schemas.project import ProjectContext, Requirement
from app.schemas.task import Task, TaskStatus


class FakeLlmClient:
    def __init__(self, json_response=None, text_response=""):
        self._json_response = json_response
        self._text_response = text_response
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append(("chat", messages))
        return self._text_response

    async def chat_json(self, messages, **kwargs):
        self.calls.append(("chat_json", messages))
        return self._json_response


@pytest.fixture
def context():
    ctx = ProjectContext(name="Test Project", objective="Build a thing.")
    ctx.requirements.append(Requirement(text="Users can log in.", kind="functional"))
    return ctx


@pytest.mark.asyncio
async def test_analyze_requirements_parses_llm_json(monkeypatch, context):
    fake = FakeLlmClient(
        json_response={
            "summary": "Needs a login page.",
            "key_considerations": ["Accessible form"],
            "questions": [{"text": "Should sessions persist across tabs?", "reason": "unclear", "priority": "low"}],
        }
    )
    monkeypatch.setattr(base_module, "get_llm_client", lambda: fake)
    agent = FrontendAgent()

    result = await agent.analyze_requirements(context)

    assert result["summary"] == "Needs a login page."
    assert len(result["questions"]) == 1
    assert agent.status.state.value == "idle"  # returns to idle after analysis


@pytest.mark.asyncio
async def test_implement_task_produces_files(monkeypatch, context):
    fake = FakeLlmClient(
        json_response={
            "files": {"src/Login.jsx": "export default function Login() { return null; }"},
            "summary": "Added a login component.",
            "tests_note": "Manually verified it renders.",
        }
    )
    monkeypatch.setattr(base_module, "get_llm_client", lambda: fake)
    agent = FrontendAgent()
    task = Task(task_id="t1", story_id="s1", title="Build login page", specialty=agent.profile.specialty)

    result = await agent.implement_task(context, task)

    assert "src/Login.jsx" in result["files"]
    assert not result.get("error")


@pytest.mark.asyncio
async def test_implement_task_handles_malformed_response_gracefully(monkeypatch, context):
    fake = FakeLlmClient(json_response={"not_files": "oops"})
    monkeypatch.setattr(base_module, "get_llm_client", lambda: fake)
    agent = FrontendAgent()
    task = Task(task_id="t1", story_id="s1", title="Build login page", specialty=agent.profile.specialty)

    result = await agent.implement_task(context, task)

    assert result["error"] is True
    assert result["files"] == {}
    assert agent.status.state.value == "blocked"


def test_scrum_master_allocate_tasks_promotes_ready_when_deps_complete():
    from app.schemas.task import Backlog, Task, TaskRisk
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    dep = Task(task_id="dep", story_id="s1", title="Schema", specialty=AgentSpecialty.DATABASE, status=TaskStatus.COMPLETED)
    blocked = Task(
        task_id="main", story_id="s1", title="API", specialty=AgentSpecialty.BACKEND,
        depends_on=["dep"], status=TaskStatus.BACKLOG,
    )
    backlog.tasks = {"dep": dep, "main": blocked}

    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)  # skip __init__ (no LLM client needed for pure logic)
    result = sm.allocate_tasks(backlog)

    assert result.tasks["main"].status == TaskStatus.READY
    assert result.tasks["main"].assigned_agent_id == "backend"


def test_scrum_master_allocate_tasks_leaves_unmet_dependency_in_backlog():
    from app.schemas.task import Backlog, Task
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    dep = Task(task_id="dep", story_id="s1", title="Schema", specialty=AgentSpecialty.DATABASE, status=TaskStatus.IN_PROGRESS)
    waiting = Task(task_id="main", story_id="s1", title="API", specialty=AgentSpecialty.BACKEND, depends_on=["dep"])
    backlog.tasks = {"dep": dep, "main": waiting}

    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)
    result = sm.allocate_tasks(backlog)

    assert result.tasks["main"].status == TaskStatus.BACKLOG


class _FakeRequester:
    """Stand-in for a BaseAgent for request_work tests -- only needs
    .profile.specialty.value and .agent_id, no LLM client required."""

    def __init__(self, specialty):
        from app.schemas.agent import AgentSpecialty

        class _P:
            pass

        self.profile = _P()
        self.profile.specialty = AgentSpecialty(specialty)
        self.agent_id = specialty


def test_request_work_serves_own_specialty_first():
    from app.schemas.task import Backlog, Task
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    own = Task(task_id="t1", story_id="s1", title="Login form", specialty=AgentSpecialty.FRONTEND, status=TaskStatus.READY)
    other = Task(task_id="t2", story_id="s1", title="Login API", specialty=AgentSpecialty.BACKEND, status=TaskStatus.READY)
    backlog.tasks = {"t1": own, "t2": other}

    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)
    frontend = _FakeRequester("frontend")

    task = sm.request_work(backlog, frontend)

    assert task is not None and task.task_id == "t1"
    assert task.assigned_agent_id == "frontend"


def test_request_work_waits_when_own_specialty_has_pending_dependency():
    """A specialty that DOES have work in this project, just not READY yet,
    should wait rather than poach someone else's queue."""
    from app.schemas.task import Backlog, Task
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    waiting_own = Task(
        task_id="t1", story_id="s1", title="Dashboard", specialty=AgentSpecialty.FRONTEND,
        status=TaskStatus.BACKLOG, depends_on=["t2"],
    )
    other_ready = Task(task_id="t2", story_id="s1", title="Dashboard API", specialty=AgentSpecialty.BACKEND, status=TaskStatus.READY)
    backlog.tasks = {"t1": waiting_own, "t2": other_ready}

    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)
    frontend = _FakeRequester("frontend")

    assert sm.request_work(backlog, frontend) is None


def test_request_work_helps_busiest_specialty_when_own_has_no_work_at_all():
    """The core fix: a specialty this project never assigned any task to
    (e.g. MLOps on a to-do list) should pick up someone else's READY work
    instead of getting a forced filler task or sitting idle."""
    from app.schemas.task import Backlog, Task
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    backend_1 = Task(task_id="t1", story_id="s1", title="API 1", specialty=AgentSpecialty.BACKEND, status=TaskStatus.READY)
    backend_2 = Task(task_id="t2", story_id="s1", title="API 2", specialty=AgentSpecialty.BACKEND, status=TaskStatus.READY)
    db_task = Task(task_id="t3", story_id="s1", title="Schema", specialty=AgentSpecialty.DATABASE, status=TaskStatus.READY)
    backlog.tasks = {"t1": backend_1, "t2": backend_2, "t3": db_task}

    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)
    mlops = _FakeRequester("mlops")  # no MLOps task exists in this backlog at all

    task = sm.request_work(backlog, mlops)

    assert task is not None
    assert task.specialty == AgentSpecialty.BACKEND  # the busier of the two READY queues
    assert task.assigned_agent_id == "mlops"


def test_request_work_returns_none_when_nothing_left_anywhere():
    from app.schemas.task import Backlog, Task
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    done = Task(task_id="t1", story_id="s1", title="API", specialty=AgentSpecialty.BACKEND, status=TaskStatus.COMPLETED)
    backlog.tasks = {"t1": done}

    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)
    mlops = _FakeRequester("mlops")

    assert sm.request_work(backlog, mlops) is None


def test_needed_specialties_reflects_only_specialties_with_tasks():
    from app.schemas.task import Backlog, Task
    from app.schemas.agent import AgentSpecialty

    backlog = Backlog()
    backlog.tasks = {
        "t1": Task(task_id="t1", story_id="s1", title="UI", specialty=AgentSpecialty.FRONTEND),
        "t2": Task(task_id="t2", story_id="s1", title="API", specialty=AgentSpecialty.BACKEND),
    }
    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)

    assert sm.needed_specialties(backlog) == {"frontend", "backend"}
