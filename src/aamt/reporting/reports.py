"""Markdown report generators (PRD §24, phased plan §9).

Everything is derived from the persisted project state + the append-only event
log, so a report is always a faithful replay of what actually happened.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict

from ..events.bus import EventBus
from ..models.enums import BacklogItemKind, TaskStatus
from ..models.event import Event, EventType
from ..state.store import ProjectStore


def _ts(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def _day(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t))


# --------------------------------------------------------------------------
def project_timeline(bus: EventBus, project_id: str | None = None) -> str:
    events = bus.query(project_id=project_id) if project_id else list(bus)
    if not events:
        return "# Timeline\n\n_(no events)_\n"
    by_day: dict[str, list[Event]] = defaultdict(list)
    for e in events:
        by_day[_day(e.ts)].append(e)

    out = ["# Project timeline\n"]
    for day in sorted(by_day):
        out.append(f"## {day}\n")
        counts = Counter(e.type.value for e in by_day[day])
        highlight = {
            EventType.SPRINT_PLANNED, EventType.SPRINT_STARTED, EventType.SPRINT_REVIEWED,
            EventType.RETROSPECTIVE_COMPLETED, EventType.TASK_COMPLETED,
            EventType.MERGE_COMPLETED, EventType.MERGE_CONFLICT,
            EventType.BLOCKER_CREATED, EventType.ESCALATED_TO_HUMAN,
            EventType.PROJECT_COMPLETED,
        }
        for e in by_day[day]:
            if e.type in highlight:
                bits = " ".join(f"{k}={v}" for k, v in list(e.payload.items())[:3])
                out.append(f"- `{_ts(e.ts)}` **{e.type.value}** {e.task_id or e.sprint_id or ''} {bits}")
        summary = ", ".join(f"{k}×{v}" for k, v in counts.most_common(8))
        out.append(f"\n  <sub>{summary}</sub>\n")
    return "\n".join(out)


def daily_report(store: ProjectStore, bus: EventBus, *, day: str | None = None) -> str:
    project = store.get_project()
    events = bus.query(project_id=project.id if project else None)
    day = day or (_day(events[-1].ts) if events else _day(time.time()))
    todays = [e for e in events if _day(e.ts) == day]

    def n(t: EventType) -> int:
        return sum(1 for e in todays if e.type is t)

    tasks = store.list_tasks()
    in_progress = [t for t in tasks if t.status is TaskStatus.IN_PROGRESS]
    blocked = [t for t in tasks if t.status is TaskStatus.BLOCKED]
    standups = [s for s in store.list_standups() if _day(s.ts) == day]

    out = [f"# Daily report — {day}\n"]
    if project:
        out.append(f"**Project:** {project.name} · status {project.status.value}\n")
    if standups:
        out.append("## Standups\n")
        for su in standups:
            out.append(f"- tick {su.tick}: {su.team_summary}")
    out.append("\n## Activity\n")
    out.append(f"- commits: {n(EventType.COMMIT_CREATED)}")
    out.append(f"- tasks completed: {n(EventType.TASK_COMPLETED)}")
    out.append(f"- tests: {n(EventType.TEST_PASSED)} passed / {n(EventType.TEST_FAILED)} failed")
    out.append(f"- blockers raised: {n(EventType.BLOCKER_CREATED)}")
    out.append(f"- merges: {n(EventType.MERGE_COMPLETED)} ok / {n(EventType.MERGE_CONFLICT)} conflict")
    out.append(f"\n## In progress ({len(in_progress)})\n")
    out += [f"- {t.id} {t.title} — {t.assignee}" for t in in_progress] or ["- _(none)_"]
    out.append(f"\n## Blocked ({len(blocked)})\n")
    out += [f"- {t.id} {t.title}" for t in blocked] or ["- _(none)_"]
    return "\n".join(out)


def agent_report(store: ProjectStore, bus: EventBus) -> str:
    agents = store.list_agents()
    tasks = {t.id: t for t in store.list_tasks()}
    out = ["# Agent report\n", "| agent | role | done | failed | commits | current |",
           "|---|---|---|---|---|---|"]
    for a in sorted(agents, key=lambda x: x.role):
        commits = sum(len(tasks[tid].commits) for tid in a.completed_tasks if tid in tasks)
        out.append(
            f"| {a.id} | {a.role} | {len(a.completed_tasks)} | {len(a.failed_tasks)} "
            f"| {commits} | {a.current_task or '-'} |"
        )
    return "\n".join(out)


def sprint_report(store: ProjectStore, sprint_id: str | None = None) -> str:
    sprints = store.list_sprints()
    if sprint_id:
        sprints = [s for s in sprints if s.id == sprint_id]
    if not sprints:
        return "# Sprint report\n\n_(no sprints)_\n"
    tasks = {t.id: t for t in store.list_tasks()}
    out: list[str] = []
    for sp in sprints:
        rv, retro = sp.review, sp.retrospective
        out.append(f"# Sprint {sp.number} — {sp.goal}\n")
        out.append(f"status: {sp.status.value} · ticks {sp.elapsed_ticks}/{sp.planned_ticks}\n")
        out.append("## Planned vs delivered\n")
        for tid in sp.task_ids:
            t = tasks.get(tid)
            mark = {"DONE": "x"}.get(t.status.value if t else "", " ")
            out.append(f"- [{mark}] {tid} {t.title if t else ''} — {t.status.value if t else '?'}")
        if rv:
            out.append(
                f"\n**velocity:** {rv.velocity:g} · **completed:** {len(rv.completed)}/"
                f"{len(rv.planned)} · **blocked:** {len(rv.blocked)} · **commits:** {rv.commits}\n"
            )
        for su in store.list_standups(sprint_id=sp.id):
            out.append(f"- standup {su.tick}: {su.team_summary}")
        if retro:
            out.append("\n## Retrospective\n")
            for cat in ("went_well", "went_poorly", "change"):
                pts = [i.text for i in retro.items if i.category == cat]
                if pts:
                    out.append(f"**{cat.replace('_', ' ').title()}**")
                    out += [f"- {p}" for p in pts]
            if retro.action_items:
                out.append("\n**Action items**")
                out += [f"- {a}" for a in retro.action_items]
        out.append("\n---\n")
    return "\n".join(out)


def final_report(store: ProjectStore, bus: EventBus) -> str:
    project = store.get_project()
    if not project:
        return "# Final report\n\n_(no project)_\n"
    tasks = store.list_tasks()
    work = [t for t in tasks if t.kind is BacklogItemKind.TASK]
    done = [t for t in work if t.status is TaskStatus.DONE]
    events = bus.query(project_id=project.id)

    out = [
        f"# Final project report — {project.name}\n",
        f"_generated {_ts(time.time())}_\n",
        "## Problem statement\n", project.problem_statement + "\n",
    ]
    if project.acceptance_criteria:
        out.append("## Acceptance criteria\n")
        out += [f"- {c}" for c in project.acceptance_criteria]
    out.append(f"\n## Outcome\n\n**{project.status.value}** — "
               f"{len(done)}/{len(work)} backlog tasks completed across {project.sprint_count} sprint(s).\n")

    out.append("## Team contributions\n")
    out.append(agent_report(store, bus).split("\n", 1)[1])

    out.append("\n## Backlog (final state)\n")
    for t in work:
        out.append(f"- {t.id} [{t.status.value}] {t.title}"
                   + (f" — commits: {', '.join(c[:8] for c in t.commits)}" if t.commits else ""))

    out.append("\n## Sprint-by-sprint\n")
    out.append(sprint_report(store))

    decisions = store.list_decisions()
    if decisions:
        out.append("## Key decisions\n")
        out += [f"- **{d.context}** — {d.decision}" + (f" _({d.reason})_" if d.reason else "")
                for d in decisions]

    merges = [e for e in events if e.type is EventType.MERGE_COMPLETED]
    conflicts = [e for e in events if e.type is EventType.MERGE_CONFLICT]
    escal = [e for e in events if e.type is EventType.ESCALATED_TO_HUMAN]
    out.append(
        f"\n## Repository & integration\n\n"
        f"- merges to `{store.get_project().repo_path and 'main'}`: {len(merges)}\n"
        f"- merge conflicts: {len(conflicts)}\n"
        f"- escalations to human: {len(escal)}\n"
    )
    if escal:
        out.append("### Known limitations / unfinished\n")
        out += [f"- {e.task_id or ''}: {e.payload.get('note') or e.payload.get('reason')}" for e in escal]

    out.append(f"\n## Event volume\n\n{len(events)} events recorded. "
               "Full timeline available via `aamt report --kind timeline`.\n")
    return "\n".join(out)
