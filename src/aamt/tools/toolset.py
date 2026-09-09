"""Expose a :class:`Workspace` as LangChain tools for a developer agent.

This is the "controlled tools" layer of phased plan §1.2 — the agent gets file
read/search/write, a terminal, git porcelain, and a test runner, and nothing
else. Each tool returns a plain string (what the model sees next).
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from ..config import Settings, get_settings
from .test_runner import run_tests
from .workspace import Workspace, WorkspaceError


def build_developer_toolset(
    workspace: Workspace,
    *,
    settings: Settings | None = None,
) -> list[BaseTool]:
    settings = settings or get_settings()
    ws = workspace

    @tool
    def list_files(path: str = ".") -> str:
        """List files and directories at a path relative to the repo root."""
        try:
            return "\n".join(ws.list_dir(path)) or "(empty)"
        except WorkspaceError as e:
            return f"ERROR: {e}"

    @tool
    def repo_tree() -> str:
        """Show all source files in the repository (truncated)."""
        return "\n".join(ws.tree()) or "(empty repo)"

    @tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file relative to the repo root."""
        try:
            return ws.read_file(path)
        except WorkspaceError as e:
            return f"ERROR: {e}"

    @tool
    def search_code(pattern: str, glob: str = "**/*") -> str:
        """Regex-search file contents. Returns 'path:line: text' hits."""
        try:
            hits = ws.search(pattern, glob=glob)
        except WorkspaceError as e:
            return f"ERROR: {e}"
        except Exception as e:  # bad regex
            return f"ERROR: invalid pattern: {e}"
        return "\n".join(hits) if hits else "(no matches)"

    @tool
    def write_file(path: str, content: str) -> str:
        """Create or overwrite a text file with the given full content."""
        try:
            written = ws.write_file(path, content)
            return f"wrote {written} ({len(content)} bytes)"
        except WorkspaceError as e:
            return f"ERROR: {e}"

    @tool
    def run_command(command: str) -> str:
        """Run a shell command in the repo root (no network). Returns stdout/stderr."""
        try:
            return ws.run(command).render()
        except WorkspaceError as e:
            return f"ERROR: {e}"

    @tool
    def git_status() -> str:
        """Show `git status --porcelain` and the current branch."""
        return f"branch: {ws.current_branch()}\n{ws.status_porcelain() or '(clean)'}"

    @tool
    def git_diff(staged: bool = False) -> str:
        """Show the working-tree diff (or the staged diff if staged=True)."""
        return ws.diff(staged=staged) or "(no diff)"

    @tool
    def run_test_suite() -> str:
        """Run the project's configured test command and return a pass/fail summary."""
        outcome = run_tests(ws, settings.test_command, timeout=settings.agent_timeout_seconds)
        return outcome.render()

    return [
        list_files,
        repo_tree,
        read_file,
        search_code,
        write_file,
        run_command,
        git_status,
        git_diff,
        run_test_suite,
    ]
