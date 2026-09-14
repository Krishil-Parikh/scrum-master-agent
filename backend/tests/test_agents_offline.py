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
