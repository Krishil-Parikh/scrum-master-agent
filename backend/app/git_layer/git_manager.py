"""
GitManager: gives every developer agent an isolated Git branch + working
directory inside one shared repository (PRD §20-23), using `git worktree`
so six branches don't require six full clones.

Layout on disk (backend/workspace/<project_id>/):

    repo/                the actual .git repository, checked out to `main`
    worktrees/
      developer-1/        working tree checked out to branch `developer-1`
      developer-2/        working tree checked out to branch `developer-2`
      ...

Because every worktree shares one repo's object database, merging one
agent's branch into another's worktree (`git merge <other-branch>`) works
directly with no fetch/remote required -- the "Fetch -> Pull -> Merge"
dependency-sync flow in the PRD collapses to a local merge for this
single-repo MVP, which is the right simplification: the isolation the PRD
actually cares about is *working-tree* isolation (two agents can't stomp on
each other's uncommitted edits), not literal separate remotes.

All git output is returned as plain text lines so the caller can feed them
straight into the event bus / "Live Terminal" feed, which is deliberately
built to look like a real terminal transcript.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.config import WORKSPACE_DIR
from app.tools.command_runner import CommandResult, run_command

logger = logging.getLogger("ai_dev_pod.git")

MAIN_BRANCH = "main"


@dataclass
class GitOpResult:
    ok: bool
    log_lines: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)


class GitManager:
    def __init__(self, project_id: str, remote_url: str = ""):
        self.project_id = project_id
        self.project_dir = WORKSPACE_DIR / project_id
        self.repo_dir = self.project_dir / "repo"
        self.worktrees_dir = self.project_dir / "worktrees"
        self.remote_url = remote_url.strip()

    # ---- low-level ----

    def _git(self, cwd: Path, *args: str, timeout: int = 60) -> CommandResult:
        result = run_command(cwd, ["git", *args], timeout=timeout)
        logger.debug("git %s (cwd=%s) -> rc=%s", " ".join(args), cwd, result.returncode)
        return result

    def _log_line(self, result: CommandResult) -> str:
        prompt = f"$ git {result.command.removeprefix('git ')}" if not result.command.startswith("git ") else f"$ {result.command}"
        out = result.combined_output
        return f"{prompt}\n{out}" if out else prompt

    @property
    def is_initialized(self) -> bool:
        return (self.repo_dir / ".git").exists()

    # ---- repo lifecycle ----

    def init_repo(self, readme_content: str) -> GitOpResult:
        if self.is_initialized:
            return GitOpResult(ok=True, log_lines=["Repository already initialized."])

        self.repo_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []

        lines.append(self._log_line(self._git(self.repo_dir, "init", "-b", MAIN_BRANCH)))
        lines.append(self._log_line(self._git(self.repo_dir, "config", "user.email", "ai-dev-pod@local")))
        lines.append(self._log_line(self._git(self.repo_dir, "config", "user.name", "AI Dev Pod")))

        (self.repo_dir / "README.md").write_text(readme_content, encoding="utf-8")
        (self.repo_dir / ".gitignore").write_text(
            "__pycache__/\n*.pyc\nnode_modules/\ndist/\n.env\n", encoding="utf-8"
        )

        lines.append(self._log_line(self._git(self.repo_dir, "add", "-A")))
        commit = self._git(self.repo_dir, "commit", "-m", "Initial commit: project scaffold")
        lines.append(self._log_line(commit))

        if self.remote_url:
            lines.append(self._log_line(self._git(self.repo_dir, "remote", "add", "origin", self.remote_url)))

        return GitOpResult(ok=True, log_lines=lines)

    def ensure_agent_worktree(self, agent_id: str, branch: str) -> tuple[Path, GitOpResult]:
        worktree_path = self.worktrees_dir / agent_id
        if worktree_path.exists():
            return worktree_path, GitOpResult(ok=True, log_lines=[f"Worktree for {agent_id} already exists."])

        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        branch_list = self._git(self.repo_dir, "branch", "--list", branch)
        branch_exists = bool(branch_list.stdout.strip())

        if branch_exists:
            result = self._git(self.repo_dir, "worktree", "add", str(worktree_path), branch)
        else:
            result = self._git(
                self.repo_dir, "worktree", "add", "-b", branch, str(worktree_path), MAIN_BRANCH
            )
        return worktree_path, GitOpResult(ok=result.ok, log_lines=[self._log_line(result)])

    # ---- commit / push ----

    def write_and_commit(
        self, agent_id: str, branch: str, files: dict[str, str], message: str
    ) -> GitOpResult:
        from app.tools.filesystem import write_text

        worktree_path, ensure_result = self.ensure_agent_worktree(agent_id, branch)
        lines = list(ensure_result.log_lines)

        for rel_path, content in files.items():
            write_text(worktree_path, rel_path, content)

        lines.append(self._log_line(self._git(worktree_path, "add", "-A")))
        commit_result = self._git(worktree_path, "commit", "-m", message)
        lines.append(self._log_line(commit_result))

        if not commit_result.ok:
            if "nothing to commit" in commit_result.combined_output.lower():
                return GitOpResult(ok=True, log_lines=lines, data={"sha": None, "no_changes": True})
            return GitOpResult(ok=False, log_lines=lines)

        sha_result = self._git(worktree_path, "rev-parse", "--short", "HEAD")
        sha = sha_result.stdout.strip()
        return GitOpResult(ok=True, log_lines=lines, data={"sha": sha, "files": list(files.keys())})

    def push(self, agent_id: str, branch: str) -> GitOpResult:
        worktree_path = self.worktrees_dir / agent_id
        if not self.remote_url:
            return GitOpResult(ok=True, log_lines=[f"No remote configured; {branch} stays local to the pod's workspace."])
        # Every demo project reuses the same local branch names
        # (developer-1..6). Pushed as-is, a second project's push to a
        # shared remote gets rejected outright (non-fast-forward: the
        # remote branch already holds a *different* project's unrelated
        # history). Namespace the REMOTE branch by project id so multiple
        # projects can coexist on one GitHub repo -- local branch names
        # (and all the sync/merge logic keyed on them) stay unchanged.
        remote_branch = f"{self.project_id}/{branch}"
        result = self._git(worktree_path, "push", "-u", "origin", f"{branch}:{remote_branch}", timeout=120)
        return GitOpResult(ok=result.ok, log_lines=[self._log_line(result)], data={"remote_branch": remote_branch})

    # ---- sync / merge / conflicts ----

    def sync_branch(self, agent_id: str, from_branch: str) -> GitOpResult:
        """Merge `from_branch` into `agent_id`'s current branch/worktree."""
        worktree_path = self.worktrees_dir / agent_id
        merge_result = self._git(worktree_path, "merge", "--no-edit", from_branch)
        lines = [self._log_line(merge_result)]

        if merge_result.ok:
            status = "up_to_date" if "already up to date" in merge_result.combined_output.lower() else "merged"
            return GitOpResult(ok=True, log_lines=lines, data={"status": status})

        status_result = self._git(worktree_path, "status", "--porcelain=v1")
        conflicted = [
            line[3:].strip()
            for line in status_result.stdout.splitlines()
            if line.startswith("UU") or line.startswith("AA") or line.startswith("DD")
        ]
        return GitOpResult(ok=False, log_lines=lines, data={"status": "conflict", "conflicted_files": conflicted})

    def read_conflicted_file(self, agent_id: str, relative_path: str) -> str:
        from app.tools.filesystem import read_text

        worktree_path = self.worktrees_dir / agent_id
        return read_text(worktree_path, relative_path)

    def show_file_at_ref(self, agent_id: str, ref: str, relative_path: str) -> str:
        """Read a file's content as it exists at a given ref (branch/HEAD),
        independent of what's currently on disk -- used to pull the "ours"
        and "theirs" versions of a conflicted file for conflict resolution,
        since a failed merge leaves conflict markers in the working tree
        rather than either clean version."""
        worktree_path = self.worktrees_dir / agent_id
        posix_path = relative_path.replace("\\", "/")
        result = self._git(worktree_path, "show", f"{ref}:{posix_path}")
        return result.stdout if result.ok else ""

    def resolve_conflict(self, agent_id: str, resolved_files: dict[str, str], message: str) -> GitOpResult:
        from app.tools.filesystem import write_text

        worktree_path = self.worktrees_dir / agent_id
        lines: list[str] = []
        for rel_path, content in resolved_files.items():
            write_text(worktree_path, rel_path, content)
            lines.append(self._log_line(self._git(worktree_path, "add", rel_path)))

        commit_result = self._git(worktree_path, "commit", "-m", message)
        lines.append(self._log_line(commit_result))
        if not commit_result.ok:
            return GitOpResult(ok=False, log_lines=lines)

        sha = self._git(worktree_path, "rev-parse", "--short", "HEAD").stdout.strip()
        return GitOpResult(ok=True, log_lines=lines, data={"sha": sha})

    def abort_merge(self, agent_id: str) -> GitOpResult:
        worktree_path = self.worktrees_dir / agent_id
        result = self._git(worktree_path, "merge", "--abort")
        return GitOpResult(ok=result.ok, log_lines=[self._log_line(result)])

    # ---- introspection ----

    def status(self, agent_id: str) -> str:
        worktree_path = self.worktrees_dir / agent_id
        if not worktree_path.exists():
            return ""
        result = self._git(worktree_path, "status")
        return result.combined_output

    def list_branches(self) -> list[str]:
        if not self.is_initialized:
            return []
        result = self._git(self.repo_dir, "branch", "--list")
        # `git branch --list` prefixes the branch checked out in *this*
        # worktree with "* " and one checked out in *another* worktree
        # (which is the normal case here -- every developer branch lives in
        # its own worktree) with "+ ". Strip either.
        return [re.sub(r"^[*+]?\s*", "", b) for b in result.stdout.splitlines() if b.strip()]

    def recent_commits(self, limit: int = 20) -> list[dict]:
        if not self.is_initialized:
            return []
        fmt = "%H|%an|%ad|%s|%D"
        result = self._git(
            self.repo_dir, "log", "--all", f"--pretty=format:{fmt}", "--date=iso-strict", f"-n{limit}"
        )
        commits = []
        for line in result.stdout.splitlines():
            parts = line.split("|", 4)
            if len(parts) < 4:
                continue
            sha, author, date, subject = parts[0], parts[1], parts[2], parts[3]
            refs = parts[4] if len(parts) > 4 else ""
            commits.append({"sha": sha[:7], "author": author, "date": date, "subject": subject, "refs": refs})
        return commits


_managers: dict[str, GitManager] = {}


def get_git_manager(project_id: str, remote_url: str = "") -> GitManager:
    if project_id not in _managers:
        _managers[project_id] = GitManager(project_id, remote_url=remote_url)
    return _managers[project_id]
