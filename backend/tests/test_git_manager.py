"""Exercises GitManager against a real local git repository (git must be on
PATH; no network access required or used)."""

import shutil

import pytest

from app.git_layer.git_manager import GitManager

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed on PATH")


def _manager(tmp_path) -> GitManager:
    gm = GitManager(project_id="test-project")
    # Redirect onto a throwaway tmp dir instead of the real workspace/.
    gm.project_dir = tmp_path
    gm.repo_dir = tmp_path / "repo"
    gm.worktrees_dir = tmp_path / "worktrees"
    return gm


def test_init_repo_creates_main_branch_with_initial_commit(tmp_path):
    gm = _manager(tmp_path)
    result = gm.init_repo("# Test Project\n")
    assert result.ok
    assert (gm.repo_dir / ".git").exists()
    assert (gm.repo_dir / "README.md").exists()
    assert gm.list_branches() == ["main"]


def test_ensure_agent_worktree_creates_isolated_branch(tmp_path):
    gm = _manager(tmp_path)
    gm.init_repo("# Test\n")
    worktree, result = gm.ensure_agent_worktree("backend", "developer-2")
    assert result.ok
    assert worktree.exists()
    assert "developer-2" in gm.list_branches()


def test_two_agents_write_independently_without_clobbering(tmp_path):
    """Roadmap Phase 10 success gate: two agents can simultaneously modify
    their own workspaces without overwriting each other's changes."""
    gm = _manager(tmp_path)
    gm.init_repo("# Test\n")

    r1 = gm.write_and_commit("frontend", "developer-1", {"src/App.jsx": "// frontend code"}, "Add App shell")
    r2 = gm.write_and_commit("backend", "developer-2", {"src/main.py": "# backend code"}, "Add entrypoint")

    assert r1.ok and r1.data["sha"]
    assert r2.ok and r2.data["sha"]
    assert (gm.worktrees_dir / "frontend" / "src" / "App.jsx").exists()
    assert (gm.worktrees_dir / "backend" / "src" / "main.py").exists()
    # Frontend's worktree must not contain backend's file and vice versa.
    assert not (gm.worktrees_dir / "frontend" / "src" / "main.py").exists()
    assert not (gm.worktrees_dir / "backend" / "src" / "App.jsx").exists()


def test_sync_branch_merges_cleanly_when_no_overlap(tmp_path):
    gm = _manager(tmp_path)
    gm.init_repo("# Test\n")
    gm.write_and_commit("database", "developer-6", {"schema.sql": "CREATE TABLE users (id INT);"}, "Add schema")
    gm.ensure_agent_worktree("backend", "developer-2")

    result = gm.sync_branch("backend", "developer-6")
    assert result.ok
    assert (gm.worktrees_dir / "backend" / "schema.sql").exists()


def test_sync_branch_detects_real_conflict(tmp_path):
    gm = _manager(tmp_path)
    gm.init_repo("# Test\n")
    gm.write_and_commit("frontend", "developer-1", {"shared.md": "frontend's version"}, "FE writes shared.md")
    gm.write_and_commit("backend", "developer-2", {"shared.md": "backend's version"}, "BE writes shared.md")

    result = gm.sync_branch("frontend", "developer-2")
    assert not result.ok
    assert result.data["status"] == "conflict"
    assert "shared.md" in result.data["conflicted_files"]


def test_resolve_conflict_completes_the_merge(tmp_path):
    gm = _manager(tmp_path)
    gm.init_repo("# Test\n")
    gm.write_and_commit("frontend", "developer-1", {"shared.md": "frontend's version"}, "FE writes shared.md")
    gm.write_and_commit("backend", "developer-2", {"shared.md": "backend's version"}, "BE writes shared.md")
    gm.sync_branch("frontend", "developer-2")

    result = gm.resolve_conflict("frontend", {"shared.md": "merged version"}, "Merge developer-2: resolve conflict")
    assert result.ok
    assert (gm.worktrees_dir / "frontend" / "shared.md").read_text() == "merged version"
    # git status should be clean again -- no unresolved conflict left behind.
    assert "Unmerged paths" not in gm.status("frontend")
