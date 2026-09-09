"""Sprint retrospective (phased plan §8.5-8.6, PRD §21).

Generates went-well / went-poorly / change items plus concrete action items,
grounded in the sprint's actual event log and review. Action items are persisted
on the sprint and carried into the next sprint's planning context.
"""

from __future__ import annotations

import json
import re

from ..config import Settings, get_settings
from ..events.bus import EventBus
from ..models.event import EventType
from ..models.sprint import RetroItem, Retrospective, Sprint
from ..state.store import ProjectStore


def _deterministic(sprint: Sprint) -> Retrospective:
    rv = sprint.review
    items: list[RetroItem] = []
    actions: list[str] = []
    if rv:
        if rv.completed:
            items.append(RetroItem(category="went_well",
                                   text=f"Delivered {len(rv.completed)} task(s) with evidence."))
        if rv.blocked:
            items.append(RetroItem(category="went_poorly",
                                   text=f"{len(rv.blocked)} task(s) ended blocked."))
            actions.append("Resolve or re-scope blocked tasks before next sprint planning.")
        if rv.incomplete and len(rv.incomplete) > len(rv.completed):
            items.append(RetroItem(category="went_poorly", text="More tasks incomplete than done."))
            actions.append("Reduce sprint scope / capacity next sprint.")
        if rv.tests_failed:
            actions.append("Add a test-stability check before marking tasks done.")
    if not items:
        items.append(RetroItem(category="change", text="Not enough signal — keep process steady."))
    return Retrospective(items=items, action_items=actions)


def run_retrospective(
    store: ProjectStore,
    bus: EventBus,
    sprint: Sprint,
    *,
    project_id: str | None = None,
    settings: Settings | None = None,
) -> Retrospective:
    settings = settings or get_settings()
    retro = _deterministic(sprint)

    if settings.enable_retro:
        try:
            from ..llm.provider import build_chat_model

            events = bus.query(sprint_id=sprint.id)
            ev_lines = "\n".join(f"{e.type.value} {e.payload}" for e in events[-60:])
            rv = sprint.review
            model = build_chat_model(
                model=settings.coordinator_model, settings=settings, max_tokens=900
            )
            resp = model.invoke([
                ("system",
                 "You are a Scrum Master running a retrospective. From the sprint's event "
                 "log, produce ONLY JSON: "
                 '{"went_well":[".."],"went_poorly":[".."],"change":[".."],'
                 '"action_items":["concrete change for next sprint"]}'),
                ("user",
                 f"Sprint goal: {sprint.goal}\n"
                 f"Review: completed={len(rv.completed) if rv else 0} "
                 f"blocked={len(rv.blocked) if rv else 0} "
                 f"incomplete={len(rv.incomplete) if rv else 0}\n\n"
                 f"Events:\n{ev_lines}"),
            ])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                items = (
                    [RetroItem(category="went_well", text=str(x)) for x in data.get("went_well", [])]
                    + [RetroItem(category="went_poorly", text=str(x)) for x in data.get("went_poorly", [])]
                    + [RetroItem(category="change", text=str(x)) for x in data.get("change", [])]
                )
                actions = [str(a) for a in data.get("action_items", [])][:8]
                if items or actions:
                    retro = Retrospective(items=items or retro.items,
                                          action_items=actions or retro.action_items)
        except Exception:  # noqa: BLE001 - keep the deterministic retro
            pass

    sprint.retrospective = retro
    store.save_sprint(sprint)
    bus.emit(
        EventType.RETROSPECTIVE_COMPLETED,
        project_id=project_id, sprint_id=sprint.id,
        action_items=retro.action_items, n_items=len(retro.items),
    )
    return retro
