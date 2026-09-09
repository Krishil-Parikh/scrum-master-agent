"""End-to-end orchestration with every LLM touchpoint mocked (fully offline).

Exercises the Phase 3-10 wiring: team -> backlog -> sprint -> execute -> review
-> integrate -> standup -> retro -> final report.
"""

from __future__ import annotations

import pytest

from aamt.config import Settings
from aamt.models.enums import TaskStatus
from aamt.models.task import Task
from aamt.planning.schemas import (
    BacklogPlan, PlannedCriterion, PlannedFeature, PlannedStory, PlannedTask,
)
from aamt.runtime.task_graph import TaskRunResult


@pytest.fixture
def offline(monkeypatch, tmp_path):
    # 1) deterministic backlog (no LLM)
    plan = BacklogPlan(
        epic="Task list",
        features=[PlannedFeature(title="Core", stories=[PlannedStory(title="Store", tasks=[
            PlannedTask(ref="t1", title="Create store module", description="in-memory store",
                        role="backend", priority="HIGH", estimate=2,
                        acceptance_criteria=[PlannedCriterion(text="module exists")]),
            PlannedTask(ref="t2", title="Add tests for store", description="pytest",
                        role="qa", priority="HIGH", estimate=2, depends_on=["t1"],
                        acceptance_criteria=[PlannedCriterion(text="tests pass")]),
        ])])],
    )
    monkeypatch.setattr(
        "aamt.agents.scrum_master.BacklogPlanner.generate", lambda self, project: plan
    )
    # 2) scrum master goal sentence -> deterministic
    monkeypatch.setattr(
        "aamt.agents.scrum_master.ScrumMaster._goal_sentence",
        lambda self, project, plan: "Deliver the store slice.",
    )
    # 3) task execution -> succeed, create a real commit on a branch
    def fake_run_task(task: Task, *, workspace_root, agent_role, **kw):
        from aamt.tools.workspace import Workspace

        ws = Workspace(workspace_root)
        ws.ensure_git_repo()
        base = ws.last_commit_hash()
        branch = f"task/{task.id}"
        ws.create_branch(branch)
        ws.write_file(f"src/{task.id}.py", f"# {task.title}\nvalue = 1\n")
        ws.commit_all(f"feat: {task.title}")
        t = task.model_copy(deep=True)
        t.advance_to(TaskStatus.IN_PROGRESS, actor=agent_role)
        t.advance_to(TaskStatus.TESTING, actor=agent_role)
        t.transition(TaskStatus.DONE, actor=agent_role)
        t.add_evidence(commit=ws.last_commit_hash(), actor=agent_role)
        t.branch = branch
        ws.run_argv(["git", "checkout", base and "-" or "master"]) if base else None
        return TaskRunResult(task=t, outcome="done", attempts=1, branch=branch,
                             commit_hash=ws.last_commit_hash(), agent_summary="done",
                             events=[{"type": "TASK_COMPLETED", "payload": {"task_id": t.id}}])

    monkeypatch.setattr("aamt.orchestrator.orchestrator.run_task", fake_run_task)
    # 4) reviewer -> approve without LLM
    monkeypatch.setattr(
        "aamt.orchestrator.orchestrator.ReviewerAgent.review",
        lambda self, task, ws, **kw: __import__(
            "aamt.integration.reviewer", fromlist=["ReviewResult"]
        ).ReviewResult(approved=True, comments=["ok"]),
    )

    settings = Settings(
        data_dir=tmp_path / "d", workspace_dir=tmp_path / "w",
        enable_standups=False, enable_retro=False, enable_llm_judge=False,
        enable_review=True, enable_integration=True,
        inter_task_seconds=0, max_sprints=3, test_command="python -m pytest -q",
    )
    settings.ensure_dirs()
    return settings, tmp_path


def test_full_offline_run(offline, monkeypatch):
    settings, tmp_path = offline
    monkeypatch.setattr("aamt.config.get_settings", lambda reload=False: settings)

    from aamt.orchestrator import Orchestrator

    orch = Orchestrator(settings)
    repo = tmp_path / "repo"
    project = orch.run(
        name="demo", problem_statement="build a task list store",
        repo_path=str(repo), acceptance_criteria=["pytest passes"], max_sprints=3,
    )

    # team formed
    assert len(orch.manager.team()) == 7
    # backlog materialized (epic + feature + story + 2 tasks)
    work = [t for t in orch.store.list_tasks() if t.kind.value == "TASK"]
    assert len(work) == 2
    assert all(t.status is TaskStatus.DONE for t in work)
    # project completed + final report on disk
    assert project.status.value == "COMPLETED"
    assert (settings.data_dir / f"final_report_{project.id}.md").exists()

    # events cover the pipeline
    kinds = {e.type.value for e in orch.bus.query(project_id=project.id)}
    assert {"TEAM_FORMED", "BACKLOG_CREATED", "SPRINT_PLANNED", "SPRINT_STARTED",
            "TASK_ASSIGNED", "CODE_REVIEW_COMPLETED", "MERGE_COMPLETED",
            "SPRINT_REVIEWED", "SPRINT_COMPLETED", "PROJECT_COMPLETED"} <= kinds
    orch.close()


def test_pause_control_stops_the_loop(offline, monkeypatch):
    settings, tmp_path = offline
    monkeypatch.setattr("aamt.config.get_settings", lambda reload=False: settings)
    from aamt.orchestrator import Orchestrator

    orch = Orchestrator(settings)
    orch.signal("PAUSE")  # stop before the first sprint
    project = orch.run(
        name="demo", problem_statement="x", repo_path=str(tmp_path / "r2"), max_sprints=3
    )
    assert project.status.value == "IN_PROGRESS"
    assert not [t for t in orch.store.list_tasks() if t.status is TaskStatus.DONE]
    orch.close()
