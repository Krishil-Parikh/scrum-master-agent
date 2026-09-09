import pytest

from aamt.tools.workspace import Workspace, WorkspaceError


def test_path_jail(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ws.write_file("a/b.txt", "hi")
    assert ws.read_file("a/b.txt") == "hi"
    with pytest.raises(WorkspaceError):
        ws.read_file("../secret")
    with pytest.raises(WorkspaceError):
        ws.write_file("../../evil", "x")


def test_search(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ws.write_file("src/mod.py", "def foo():\n    return 42\n")
    ws.write_file("src/other.py", "x = 1\n")
    hits = ws.search(r"def \w+")
    assert any("mod.py" in h for h in hits)
    assert all("other.py" not in h for h in hits)


def test_shell_denylist(tmp_path):
    ws = Workspace(tmp_path / "repo", allow_network=False)
    with pytest.raises(WorkspaceError):
        ws.run("curl http://example.com")
    with pytest.raises(WorkspaceError):
        ws.run("sudo rm -rf /")


def test_git_init_commit(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ws.ensure_git_repo()
    ws.write_file("README.md", "# demo\n")
    res = ws.commit_all("feat: initial", trailer="Co-Authored-By: x <x@y.z>")
    assert res.ok, res.render()
    assert ws.last_commit_hash()
    assert ws.status_porcelain().strip() == ""


def test_run_captures_exit_code(tmp_path):
    ws = Workspace(tmp_path / "repo")
    ok = ws.run("python -c \"print('hello')\"")
    assert ok.ok and "hello" in ok.stdout
    bad = ws.run("python -c \"import sys; sys.exit(3)\"")
    assert bad.exit_code == 3 and not bad.ok
