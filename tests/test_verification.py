from aamt.models import AcceptanceCriterion, Task
from aamt.runtime.verification import (
    VerificationReport,
    _task_requires_tests,
    verify_task,
)
from aamt.tools.test_runner import TestOutcome
from aamt.tools.workspace import Workspace


def test_requires_tests_heuristic():
    assert _task_requires_tests(Task(title="Implement POST /tasks endpoint", role="backend"))
    assert _task_requires_tests(Task(title="Write pytest tests for login", role="qa"))
    assert not _task_requires_tests(Task(title="Create project directory structure", role="devops"))
    assert not _task_requires_tests(Task(title="Add a README and LICENSE", role="devops"))
    # a task fully covered by executable checks doesn't also need a suite
    t = Task(title="Add config loader", role="backend",
             acceptance_criteria=[AcceptanceCriterion(text="loads", check="true")])
    assert not _task_requires_tests(t)


def _report(*, present, tests, required):
    return VerificationReport(
        implementation_present=present, diff_stat="x", tests=tests, tests_required=required
    )


def test_no_tests_accepted_only_when_not_required():
    empty = TestOutcome(command="pytest", ran=True, passed=True, exit_code=5, no_tests=True)
    assert _report(present=True, tests=empty, required=False).passed
    assert not _report(present=True, tests=empty, required=True).passed


def test_failing_suite_never_passes():
    failed = TestOutcome(command="pytest", ran=True, passed=False, exit_code=1, n_failed=2)
    assert not _report(present=True, tests=failed, required=False).passed


def test_no_implementation_never_passes():
    ok = TestOutcome(command="pytest", ran=True, passed=True, exit_code=0, n_passed=3)
    assert not _report(present=False, tests=ok, required=True).passed


def test_verify_task_end_to_end_scaffold(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ws.ensure_git_repo()
    ws.write_file("pytest.ini", "[pytest]\ntestpaths = tests\n")
    base = ws.last_commit_hash()
    ws.write_file("docs/structure.md", "- src/\n- tests/\n")

    task = Task(title="Create project directory structure", role="devops",
                description="scaffold the folders")
    report = verify_task(
        task, ws, base_commit=base,
        settings=type("S", (), {"test_command": "python -m pytest -q", "agent_timeout_seconds": 60})(),
    )
    assert report.implementation_present
    assert report.tests is not None and report.tests.no_tests
    assert not report.tests_required
    assert report.passed
