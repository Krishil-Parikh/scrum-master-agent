"""Tool Layer (PRD §39): the only place agents/orchestration touch the real
filesystem or spawn a subprocess. Every other module writes files or runs
commands through here, scoped to an explicit root, so "what can an agent
actually do to this machine" has one answer."""

from app.tools.command_runner import CommandResult, run_command
from app.tools.filesystem import safe_join, read_text, write_text

__all__ = ["CommandResult", "run_command", "safe_join", "read_text", "write_text"]
