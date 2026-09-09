from aamt.config import Settings
from aamt.integration.merge import integrate_branch
from aamt.tools.workspace import Workspace


def _repo(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ws.ensure_git_repo()
    ws.write_file("app.py", "x = 1\n")
    ws.write_file("tests/test_app.py", "def test_ok():\n    assert 1 == 1\n")
    ws.write_file("pytest.ini", "[pytest]\ntestpaths = tests\n")
    ws.commit_all("init")
    ws.run_argv(["git", "branch", "main"])
    return ws


def _settings(tmp_path):
    return Settings(
        data_dir=tmp_path / "d", workspace_dir=tmp_path / "w",
        test_command="python -m pytest -q", integration_target_branch="main",
        enable_integration=True,
    )


def test_clean_merge(tmp_path):
    ws = _repo(tmp_path)
    ws.create_branch("task/T-1")
    ws.write_file("feature.py", "y = 2\n")
    ws.commit_all("feat: add feature")

    res = integrate_branch(ws, "task/T-1", settings=_settings(tmp_path))
    assert res.ok and res.merged
    assert (ws.root / "feature.py").exists()
    assert ws.current_branch() == "main"


def test_merge_conflict_is_detected_and_aborted(tmp_path):
    ws = _repo(tmp_path)
    # main advances
    ws.run_argv(["git", "checkout", "main"])
    ws.write_file("app.py", "x = 999\n")
    ws.commit_all("main: change app")
    # task branch from the original commit changes the same line
    ws.run_argv(["git", "checkout", "-b", "task/T-2", "HEAD~1"])
    ws.write_file("app.py", "x = 42\n")
    ws.commit_all("task: change app")

    res = integrate_branch(ws, "task/T-2", settings=_settings(tmp_path))
    assert not res.ok
    assert "app.py" in res.conflicts
    # working tree is clean again (merge --abort ran)
    assert ws.status_porcelain().strip() == ""


def test_regression_causes_revert(tmp_path):
    ws = _repo(tmp_path)
    ws.create_branch("task/T-3")
    ws.write_file("tests/test_app.py", "def test_ok():\n    assert 1 == 2\n")
    ws.commit_all("test: break the suite")

    res = integrate_branch(ws, "task/T-3", settings=_settings(tmp_path))
    assert not res.ok
    assert res.regression is not None and not res.regression.passed
    assert "reverted" in res.note
    # main is back to green
    ws.run_argv(["git", "checkout", "main"])
    assert "assert 1 == 2" not in (ws.root / "tests" / "test_app.py").read_text()


def test_integration_disabled(tmp_path):
    ws = _repo(tmp_path)
    s = _settings(tmp_path)
    s.enable_integration = False
    res = integrate_branch(ws, "main", settings=s)
    assert not res.merged and "disabled" in res.note
