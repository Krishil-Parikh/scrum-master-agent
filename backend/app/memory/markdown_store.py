"""Writers for the Markdown project memory required by PRD §25/§26.

Two kinds of file:
  - "rewritten" docs (PROJECT.md, REQUIREMENTS.md, ARCHITECTURE.md, AGILE.md)
    reflect current structural state, so they're fully regenerated each time
    something material changes -- there's nothing to "contradict" if the
    whole file is always freshly derived from the JSON source of truth.
  - "append-only" logs (STANDUPS.md, SME_DISCUSSIONS.md, DECISIONS.md,
    DEVELOPMENT_LOG.md, GIT_ACTIVITY.md, RETROSPECTIVES.md) are a timestamped
    history; each event gets one more entry, never edited in place.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.schemas.communication import SMEAnswer, SMEQuestion
from app.schemas.project import Decision, ProjectContext
from app.schemas.task import Backlog, TaskStatus


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class MarkdownStore:
    def __init__(self, docs_dir: Path):
        self.docs_dir = docs_dir
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.docs_dir / name

    def _write(self, name: str, content: str) -> None:
        self._path(name).write_text(content, encoding="utf-8")

    def _append(self, name: str, block: str) -> None:
        path = self._path(name)
        if not path.exists():
            path.write_text(f"# {name.removesuffix('.md').replace('_', ' ').title()}\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as f:
            f.write(block.rstrip() + "\n\n---\n\n")

    # ---- Rewritten docs -------------------------------------------------

    def write_project_md(self, context: ProjectContext, team: list[str]) -> None:
        lines = [
            "# PROJECT.md",
            "",
            f"**Project:** {context.name}",
            f"**Status:** {context.status}",
            f"**Last updated:** {_now()}",
            "",
            "## Objective",
            "",
            context.objective or "_Not yet defined._",
            "",
            "## Business Context",
            "",
            context.business_context or "_Not yet defined._",
            "",
            "## Technology Stack",
            "",
            "\n".join(f"- {t}" for t in context.technology_stack) or "_Not yet defined._",
            "",
            "## Stakeholders",
            "",
            "\n".join(f"- {s}" for s in context.stakeholders) or "_Not yet defined._",
            "",
            "## Team",
            "",
            "\n".join(f"- {m}" for m in team),
            "",
        ]
        self._write("PROJECT.md", "\n".join(lines))

    def write_requirements_md(self, context: ProjectContext) -> None:
        functional = [r for r in context.requirements if r.kind == "functional"]
        non_functional = [r for r in context.requirements if r.kind == "non_functional"]
        lines = [
            "# REQUIREMENTS.md",
            "",
            f"_Last updated: {_now()}_",
            "",
            "## Functional Requirements",
            "",
        ]
        lines += [f"- **{r.requirement_id}**: {r.text}" for r in functional] or ["_None captured yet._"]
        lines += ["", "## Non-Functional Requirements", ""]
        lines += [f"- **{r.requirement_id}**: {r.text}" for r in non_functional] or ["_None captured yet._"]
        lines += ["", "## Constraints", ""]
        lines += [f"- {c}" for c in context.constraints] or ["_None captured yet._"]
        lines += ["", "## Acceptance Criteria", ""]
        lines += [f"- {a}" for a in context.acceptance_criteria] or ["_None captured yet._"]
        lines += ["", "## Open Questions", ""]
        lines += (
            [
                f"- **Q:** {q.question}  \n  _Reason: {q.reason}. Owner: {q.owner}. Priority: {q.priority}._"
                for q in context.open_questions
            ]
            or ["_None open._"]
        )
        self._write("REQUIREMENTS.md", "\n".join(lines))

    def write_architecture_md(self, context: ProjectContext) -> None:
        lines = [
            "# ARCHITECTURE.md",
            "",
            f"_Last updated: {_now()}_",
            "",
            context.architecture_notes or "_Architecture notes not yet produced._",
        ]
        self._write("ARCHITECTURE.md", "\n".join(lines))

    def write_agile_md(self, backlog: Backlog) -> None:
        lines = ["# AGILE.md", "", f"_Last updated: {_now()}_", ""]
        for epic in backlog.epics.values():
            lines.append(f"## Epic: {epic.title} (`{epic.epic_id}`)")
            lines.append("")
            if epic.description:
                lines.append(epic.description)
                lines.append("")
            for story_id in epic.story_ids:
                story = backlog.stories.get(story_id)
                if not story:
                    continue
                lines.append(f"### Story: {story.title} (`{story.story_id}`)")
                lines.append(f"> {story.statement}")
                lines.append("")
                if story.acceptance_criteria:
                    lines.append("**Acceptance criteria:**")
                    lines += [f"- {c}" for c in story.acceptance_criteria]
                    lines.append("")
                lines.append("**Tasks:**")
                lines.append("")
                for task_id in story.task_ids:
                    task = backlog.tasks.get(task_id)
                    if not task:
                        continue
                    lines.append(
                        f"- [{'x' if task.status == TaskStatus.COMPLETED else ' '}] "
                        f"`{task.task_id}` **{task.title}** — {task.specialty.value} — "
                        f"status: {task.status.value} — risk: {task.risk.value}"
                        + (f" — depends on: {', '.join(task.depends_on)}" if task.depends_on else "")
                    )
                lines.append("")
        if backlog.current_sprint_id:
            sprint = backlog.sprints.get(backlog.current_sprint_id)
            if sprint:
                lines.append(f"## Current Sprint: {sprint.name} (`{sprint.sprint_id}`)")
                lines.append(f"**Goal:** {sprint.goal}")
                lines.append(f"**Status:** {sprint.status}")
                lines.append("")
        self._write("AGILE.md", "\n".join(lines))

    # ---- Append-only logs -------------------------------------------------

    def append_standup(self, sprint_name: str, entries: list[dict]) -> None:
        lines = [f"## Stand-up — {_now()} ({sprint_name})", ""]
        for e in entries:
            lines.append(f"**{e['agent']}**")
            lines.append(f"- Yesterday: {e.get('yesterday', '—')}")
            lines.append(f"- Today: {e.get('today', '—')}")
            lines.append(f"- Blockers: {e.get('blockers', 'None')}")
            lines.append(f"- Dependencies: {e.get('dependencies', 'None')}")
            lines.append("")
        self._append("STANDUPS.md", "\n".join(lines))

    def append_sme_discussion(self, question: SMEQuestion, answer: SMEAnswer | None) -> None:
        lines = [
            f"## {_now()}",
            "",
            f"**Question ({question.priority} priority, asked by {question.asked_by_name}):** {question.text}",
            f"**Reason:** {question.reason}" if question.reason else "",
            f"**SME Response:** {answer.text if answer else '_Pending._'}",
            f"**Decision:** {answer.decision if answer else '_Pending._'}",
            (
                f"**Impacted requirements:** {', '.join(question.impacted_requirements)}"
                if question.impacted_requirements
                else ""
            ),
        ]
        self._append("SME_DISCUSSIONS.md", "\n".join(l for l in lines if l))

    def append_decision(self, decision: Decision) -> None:
        lines = [
            f"## {decision.decision_id} — {_now()}",
            "",
            f"**Context:** {decision.context}",
            f"**Decision:** {decision.decision}",
            (f"**Alternatives considered:** {', '.join(decision.alternatives)}" if decision.alternatives else ""),
            f"**Reason:** {decision.reason}" if decision.reason else "",
            f"**Impact:** {decision.impact}" if decision.impact else "",
        ]
        self._append("DECISIONS.md", "\n".join(l for l in lines if l))

    def append_development_log(self, title: str, body: str) -> None:
        self._append("DEVELOPMENT_LOG.md", f"## {_now()} — {title}\n\n{body}")

    def append_git_activity(
        self, *, agent: str, branch: str, commit: str, purpose: str, files_changed: list[str], dependencies: str = ""
    ) -> None:
        lines = [
            f"## {_now()}",
            "",
            f"**Agent:** {agent}",
            f"**Branch:** {branch}",
            f"**Commit:** {commit}",
            f"**Purpose:** {purpose}",
            f"**Files changed:** {', '.join(files_changed) if files_changed else '—'}",
        ]
        if dependencies:
            lines.append(f"**Dependencies:** {dependencies}")
        self._append("GIT_ACTIVITY.md", "\n".join(lines))

    def append_retrospective(
        self, *, sprint_name: str, went_well: list[str], went_wrong: list[str], action_items: list[str]
    ) -> None:
        lines = [f"## Retrospective — {sprint_name} ({_now()})", ""]
        lines.append("**What went well:**")
        lines += [f"- {w}" for w in went_well] or ["- —"]
        lines.append("")
        lines.append("**What went wrong:**")
        lines += [f"- {w}" for w in went_wrong] or ["- —"]
        lines.append("")
        lines.append("**Action items:**")
        lines += [f"- [ ] {a}" for a in action_items] or ["- —"]
        self._append("RETROSPECTIVES.md", "\n".join(lines))
