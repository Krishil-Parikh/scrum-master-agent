"""The developer agent: implements one task against one workspace."""

from __future__ import annotations

from ..config import Settings, get_settings
from ..models.task import Task
from ..tools.toolset import build_developer_toolset
from ..tools.workspace import Workspace
from .base import AgentRunResult, BaseAgent
from .roles import role_spec


def render_task_context(task: Task, *, project_summary: str = "", extra: str = "") -> str:
    """The prompt an agent receives for a task (phased plan §5.2 — scoped, not the whole history)."""
    ac = "\n".join(
        f"  - {c.text}" + (f"  [check: {c.check}]" if c.check else "")
        for c in task.acceptance_criteria
    ) or "  (none specified — infer reasonable criteria from the description)"
    deps = ", ".join(task.dependencies) if task.dependencies else "none"
    parts = [
        f"# Task {task.id}: {task.title}",
        f"\nPriority: {task.priority.value}   Dependencies: {deps}",
        f"\n## Description\n{task.description or '(none)'}",
        f"\n## Acceptance criteria\n{ac}",
    ]
    if project_summary:
        parts.append(f"\n## Project\n{project_summary}")
    if extra:
        parts.append(f"\n## Additional context\n{extra}")
    return "\n".join(parts)


class DeveloperAgent(BaseAgent):
    def __init__(self, role: str = "backend", *, settings: Settings | None = None):
        super().__init__(role_spec(role), settings=settings or get_settings())

    def implement(
        self,
        task: Task,
        workspace: Workspace,
        *,
        project_summary: str = "",
        extra_context: str = "",
        max_steps: int | None = None,
    ) -> AgentRunResult:
        tools = build_developer_toolset(workspace, settings=self.settings)
        objective = render_task_context(
            task, project_summary=project_summary, extra=extra_context
        )
        return self.run(
            objective,
            tools=tools,
            system_prompt=self.spec.system_prompt,
            max_steps=max_steps,
        )
