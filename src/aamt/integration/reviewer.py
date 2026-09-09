"""Reviewer agent (phased plan §6.5, §19).

Evaluates a task's diff against a fixed checklist and returns an approve/reject
verdict with comments. Kept cheap and defensive: if the diff is empty or the LLM
call fails, it approves (the objective verification gate has already passed by
the time we get here — review is an *additional* filter, not the only one).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..config import Settings, get_settings
from ..llm.provider import build_chat_model
from ..models.task import Task
from ..tools.workspace import Workspace

_CHECKLIST = """\
You are a senior reviewer. Review this diff for ONE task. Check:
- correctness (does it do what the task asks?)
- the acceptance criteria are actually met
- tests exist for changed behaviour and are meaningful
- no obvious security issues (injection, secrets, unsafe eval)
- style / consistency with the surrounding code
- no unrelated or out-of-scope changes

Reply with ONLY JSON: {"approved": true|false, "severity": "none|minor|major",
"comments": ["short actionable point", ...]}
Approve unless there is a real correctness, security, or acceptance-criteria problem.
"""


@dataclass
class ReviewResult:
    approved: bool
    severity: str = "none"                 # none | minor | major
    comments: list[str] = field(default_factory=list)
    raw: str = ""

    def feedback(self) -> str:
        return "Code review requested changes:\n" + "\n".join(f"- {c}" for c in self.comments)


class ReviewerAgent:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def review(
        self,
        task: Task,
        workspace: Workspace,
        *,
        base_commit: str | None = None,
    ) -> ReviewResult:
        if not self.settings.enable_review:
            return ReviewResult(approved=True, comments=["review disabled"])

        diff = (
            workspace.git(f"diff {base_commit}..HEAD").stdout
            if base_commit
            else workspace.git("show --stat HEAD").stdout
        )
        diff = diff.strip()
        if not diff:
            return ReviewResult(approved=True, comments=["empty diff — nothing to review"])

        ac = "\n".join(f"- {c.text}" for c in task.acceptance_criteria) or "- (infer from description)"
        prompt = (
            f"# Task: {task.title}\n{task.description}\n\n"
            f"# Acceptance criteria\n{ac}\n\n"
            f"# Diff (truncated)\n```diff\n{diff[:12000]}\n```"
        )
        try:
            model = build_chat_model(
                model=self.settings.reviewer_model, settings=self.settings, max_tokens=1000
            )
            resp = model.invoke([("system", _CHECKLIST), ("user", prompt)])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(m.group(0)) if m else {}
            return ReviewResult(
                approved=bool(data.get("approved", True)),
                severity=str(data.get("severity", "none")),
                comments=[str(c) for c in data.get("comments", [])][:8],
                raw=text[:2000],
            )
        except Exception as exc:  # noqa: BLE001 - never let review crash the pipeline
            return ReviewResult(
                approved=True, comments=[f"review skipped ({type(exc).__name__})"]
            )
