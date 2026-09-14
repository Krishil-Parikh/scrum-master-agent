"""Git Layer (PRD §20-23, §39; Roadmap Phase 10-12): branch isolation via
`git worktree`, commit/push, and merge-conflict detection for the demo
project the pod is building. See git_manager.py."""

from app.git_layer.git_manager import GitManager, get_git_manager

__all__ = ["GitManager", "get_git_manager"]
