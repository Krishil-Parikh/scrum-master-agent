"""Drive the task-execution graph with a fake agent + fake verifier (no LLM)."""

from __future__ import annotations

import pytest

from aamt.config import Settings
from aamt.models import AcceptanceCriterion, Task, TaskStatus
from aamt.agents.base import AgentRunResult
from aamt.runtime import task_graph as tg
from aamt.runtime.verification import VerificationReport
from aamt.tools.test_runner import TestOutcome
from aamt.tools.workspace import Workspace


@pytest.fixture
def repo(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ws.ensure_git_repo()
    ws.write_file("README.md", "x\n")
    ws.commit_all("init")
    return str(ws.root)


def _settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path / "d", workspace_dir=tmp_path / "w",
        max_task_retries=3, test_command="python -m pytest -q",
    )


def _patch_agent(monkeypatch, results: list[AgentRunResult]):
    calls = {"n": 0}

    class FakeAgent:
        def __init__(self, *a, **k): ...
        def implement(self, task, ws, **kw):
            r = results[min(calls["n"], len(results) - 1)]
            calls["n"] += 1
            # actually touch a file so "implementation_present" can be real if needed
            ws.write_file(f"src/impl_{calls['n']}.py", "x = 1\n")
            return r

    monkeypatch.setattr(tg, "DeveloperAgent", FakeAgent)
    return calls


def _patch_verify(monkeypatch, verdicts: list[bool]):
    seq = list(verdicts)

    def fake_verify(task, ws, **kw):
        ok = seq.pop(0) if seq else True
        return VerificationReport(
            implementation_present=True,
            diff_stat="1 file",
            tests=TestOutcome(command="pytest", ran=True, passed=ok, exit_code=0 if ok else 1,
                              n_passed=1 if ok else 0, n_failed=0 if ok else 1),
            tests_required=True,
        )

    monkeypatch.setattr(tg, "verify_task", fake_verify)


def test_happy_path_commits_and_marks_done(tmp_path, repo, monkeypatch):
    _patch_agent(monkeypatch, [AgentRunResult(ok=True, summary="did it", steps=3, tool_calls=["write_file"])])
    _patch_verify(monkeypatch, [True])

    res = tg.run_task(
        Task(title="add feature", role="backend"),
        workspace_root=repo, agent_role="backend", settings=_settings(tmp_path),
    )
    assert res.ok and res.outcome == "done"
    assert res.commit_hash and res.task.status is TaskStatus.DONE
    assert res.task.commits


def test_agent_crash_then_success_retries(tmp_path, repo, monkeypatch):
    calls = _patch_agent(monkeypatch, [
        AgentRunResult(ok=False, summary="", error="ValueError: boom"),
        AgentRunResult(ok=True, summary="recovered", steps=2, tool_calls=["write_file"]),
    ])
    _patch_verify(monkeypatch, [True])

    res = tg.run_task(
        Task(title="add feature", role="backend"),
        workspace_root=repo, agent_role="backend",
        settings=_settings(tmp_path), max_attempts=3,
    )
    assert res.ok and res.outcome == "done"
    assert calls["n"] == 2                      # retried once
    assert any("RETRY_SCHEDULED" == e["type"] for e in res.events)


def test_verify_fails_until_retries_exhausted_then_escalates(tmp_path, repo, monkeypatch):
    _patch_agent(monkeypatch, [AgentRunResult(ok=True, summary="attempt", tool_calls=["write_file"])])
    _patch_verify(monkeypatch, [False, False])

    res = tg.run_task(
        Task(title="tricky", role="backend"),
        workspace_root=repo, agent_role="backend",
        settings=_settings(tmp_path), max_attempts=2,
    )
    assert not res.ok and res.outcome == "escalated"
    assert res.task.status is TaskStatus.BLOCKED
    assert not res.commit_hash


def test_agent_reports_blocked_escalates_immediately(tmp_path, repo, monkeypatch):
    _patch_agent(monkeypatch, [AgentRunResult(ok=True, summary="BLOCKED: waiting on schema task")])
    _patch_verify(monkeypatch, [True])

    res = tg.run_task(
        Task(title="dependent", role="frontend"),
        workspace_root=repo, agent_role="frontend", settings=_settings(tmp_path),
    )
    assert res.outcome == "blocked"
    assert res.task.status is TaskStatus.BLOCKED
