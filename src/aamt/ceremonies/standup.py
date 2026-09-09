"""Daily standup engine (phased plan §8.1-8.3).

Standups are built deterministically from task history + the event log — no LLM
needed for the per-agent Yesterday/Today/Blockers. The Scrum Master's team
summary is a short LLM call with a deterministic fallback.
"""

from __future__ import annotations

from ..config import Settings, get_settings
from ..events.bus import EventBus
from ..models.enums import TaskStatus
from ..models.event import EventType
from ..models.sprint import Sprint
from ..models.standup import Standup, StandupEntry
from ..state.store import ProjectStore


def _recent_status_changes(task, since_ts: float) -> list[str]:
    return [
        f"{h.old}->{h.new}"
        for h in task.history
        if h.field == "status" and h.ts >= since_ts
    ]


def run_standup(
    store: ProjectStore,
    bus: EventBus,
    sprint: Sprint,
    *,
    tick: int,
    since_ts: float = 0.0,
    settings: Settings | None = None,
) -> Standup:
    settings = settings or get_settings()
    bus.emit(EventType.STANDUP_STARTED, sprint_id=sprint.id, tick=tick)

    tasks = {tid: store.get_task(tid) for tid in sprint.task_ids}
    tasks = {k: v for k, v in tasks.items() if v is not None}
    agents = {a.id: a for a in store.list_agents()}

    entries: list[StandupEntry] = []
    flagged: list[str] = []
    stalled: list[str] = []

    # group sprint tasks by assignee
    by_agent: dict[str, list] = {}
    for t in tasks.values():
        if t.assignee:
            by_agent.setdefault(t.assignee, []).append(t)

    for agent_id, agent_tasks in by_agent.items():
        agent = agents.get(agent_id)
        done_recent = [t for t in agent_tasks if t.status is TaskStatus.DONE]
        in_flight = [t for t in agent_tasks
                     if t.status in (TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED,
                                     TaskStatus.TESTING, TaskStatus.IN_REVIEW, TaskStatus.REOPENED)]
        blocked = [t for t in agent_tasks if t.status is TaskStatus.BLOCKED]

        yesterday = (
            "; ".join(f"{t.id} {t.title} -> DONE" for t in done_recent)
            or "no tasks completed since last standup"
        )
        today = (
            "; ".join(f"{t.id} {t.title} ({t.status.value})" for t in in_flight)
            or "awaiting assignment / nothing in flight"
        )
        blockers = "; ".join(f"{t.id}: {t.title}" for t in blocked) or ""

        for t in blocked:
            flagged.append(t.id)
        # a task assigned but never moved is stalled
        for t in in_flight:
            if not _recent_status_changes(t, since_ts) and t.status is not TaskStatus.IN_PROGRESS:
                stalled.append(t.id)

        entries.append(StandupEntry(
            agent_id=agent_id,
            role=agent.role if agent else "?",
            yesterday=yesterday,
            today=today,
            blockers=blockers,
        ))

    summary = _team_summary(sprint, entries, flagged, stalled, settings)

    standup = Standup(
        sprint_id=sprint.id, tick=tick, entries=entries,
        team_summary=summary, flagged_blockers=flagged, stalled_tasks=stalled,
    )
    store.save_standup(standup)
    sprint.elapsed_ticks = max(sprint.elapsed_ticks, tick)
    store.save_sprint(sprint)

    bus.emit(
        EventType.STANDUP_COMPLETED,
        sprint_id=sprint.id, tick=tick,
        blockers=len(flagged), stalled=len(stalled), summary=summary[:400],
    )
    return standup


def _team_summary(sprint, entries, flagged, stalled, settings) -> str:
    deterministic = (
        f"Tick {sprint.elapsed_ticks + 1}: {len(entries)} agents reporting, "
        f"{len(flagged)} blocker(s), {len(stalled)} stalled task(s)."
    )
    if not settings.enable_standups:
        return deterministic
    try:
        from ..llm.provider import build_chat_model

        lines = "\n".join(
            f"- {e.role}: yesterday[{e.yesterday}] today[{e.today}] blockers[{e.blockers or 'none'}]"
            for e in entries
        )
        model = build_chat_model(
            model=settings.coordinator_model, settings=settings, max_tokens=180
        )
        resp = model.invoke([
            ("system", "You are a Scrum Master. Summarise this standup in 2 sentences: "
                       "progress and the single most important risk/blocker."),
            ("user", lines or "no reports"),
        ])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        return text.strip().split("\n\n")[0][:400] or deterministic
    except Exception:  # noqa: BLE001
        return deterministic
