"""Exercises horizontal agent scaling (roadmap priority #4): spawning extra
bounded instances of a specialty, and the orchestrator's decision logic for
when to do it."""

from __future__ import annotations

import pytest

from app.agents.registry import AgentRegistry
from app.schemas.agent import AgentSpecialty
from app.schemas.task import Backlog, Task, TaskStatus


def test_spawn_extra_instance_gets_distinct_identity():
    registry = AgentRegistry()
    primary = registry.get("backend")

    extra = registry.spawn_extra_instance(AgentSpecialty.BACKEND, 2)

    assert extra.agent_id == "backend-2"
    assert extra.identity.branch == "developer-2-2"
    assert extra.identity.branch != primary.identity.branch
    assert extra.agent_id != primary.agent_id
    # Same specialty semantically -- request_work / skill selection must
    # still treat this as "a backend agent".
    assert extra.profile.specialty == primary.profile.specialty == AgentSpecialty.BACKEND


def test_spawn_extra_instance_is_idempotent():
    registry = AgentRegistry()
    first = registry.spawn_extra_instance(AgentSpecialty.BACKEND, 2)
    second = registry.spawn_extra_instance(AgentSpecialty.BACKEND, 2)
    assert first is second


def test_spawn_extra_instance_registers_in_registry_and_developers():
    registry = AgentRegistry()
    extra = registry.spawn_extra_instance(AgentSpecialty.BACKEND, 2)

    assert registry.get("backend-2") is extra
    assert extra in registry.developers()
    assert extra in registry.extra_instances_for(AgentSpecialty.BACKEND)
    assert registry.extra_instances_for(AgentSpecialty.FRONTEND) == []


def test_extra_instance_can_claim_work_via_request_work():
    """The whole point: an extra instance must compete for the SAME
    specialty's shared task queue via the existing pull-based allocation,
    with no special-casing needed in request_work itself."""
    from app.agents.scrum_master import ScrumMasterAgent

    registry = AgentRegistry()
    extra = registry.spawn_extra_instance(AgentSpecialty.BACKEND, 2)

    backlog = Backlog()
    backlog.tasks = {
        "t1": Task(task_id="t1", story_id="s1", title="API 1", specialty=AgentSpecialty.BACKEND, status=TaskStatus.READY),
    }
    sm = ScrumMasterAgent.__new__(ScrumMasterAgent)

    task = sm.request_work(backlog, extra)

    assert task is not None
    assert task.task_id == "t1"
    assert task.assigned_agent_id == "backend-2"


@pytest.mark.asyncio
async def test_scale_team_to_backlog_spawns_for_a_busy_specialty():
    from app.orchestration.orchestrator import TASKS_PER_EXTRA_AGENT, Orchestrator

    orchestrator = Orchestrator()
    orchestrator.registry = AgentRegistry()  # fresh, isolated from the process-wide singleton
    backlog = Backlog()
    backlog.tasks = {
        f"t{i}": Task(task_id=f"t{i}", story_id="s1", title=f"Task {i}", specialty=AgentSpecialty.BACKEND, status=TaskStatus.READY)
        for i in range(TASKS_PER_EXTRA_AGENT * 2)  # enough for 2 extra instances
    }

    await orchestrator._scale_team_to_backlog(backlog)

    assert orchestrator.registry.get("backend-2") is not None
    assert orchestrator.registry.get("backend-3") is not None
    with pytest.raises(KeyError):
        orchestrator.registry.get("backend-4")  # capped at MAX_EXTRA_INSTANCES_PER_SPECIALTY


@pytest.mark.asyncio
async def test_scale_team_to_backlog_does_nothing_for_a_small_backlog():
    from app.orchestration.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    orchestrator.registry = AgentRegistry()  # fresh, isolated from the process-wide singleton
    backlog = Backlog()
    backlog.tasks = {
        "t1": Task(task_id="t1", story_id="s1", title="One task", specialty=AgentSpecialty.FRONTEND, status=TaskStatus.READY),
    }

    await orchestrator._scale_team_to_backlog(backlog)

    assert orchestrator.registry.extra_instances_for(AgentSpecialty.FRONTEND) == []
