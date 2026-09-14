"""
In-process, async pub/sub Event Bus (PRD §19; Roadmap Phase 9).

Every meaningful thing that happens in the pod -- a task changing state, a
push, a conflict, an SME question -- is published here exactly once. The bus
does two things with every event, in order:

  1. Persists it to the current project's append-only event log (so a
     freshly started agent, or a human, can reconstruct history).
  2. Fans it out to every subscriber -- the WebSocket manager (for the live
     dashboard), and any in-process listener (e.g. an agent reacting to a
     dependency being completed) that called `.subscribe(...)`.

Agents "subscribe only to events relevant to their work where possible"
per the PRD -- subscribers are expected to filter by `event.type` /
`event.payload` themselves rather than the bus doing fine-grained topic
routing, which keeps this class simple for an MVP-scale pod (7 agents).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from app.schemas.event import Event, EventType

logger = logging.getLogger("ai_dev_pod.event_bus")

Subscriber = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def subscribe(self, callback: Subscriber) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Subscriber) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def publish(self, event: Event) -> Event:
        try:
            from app.memory.project_memory import get_current_project_id, get_project_memory

            if get_current_project_id():
                get_project_memory().append_event(event)
        except Exception:
            logger.exception("Failed to persist event %s", event.event_id)

        results = await asyncio.gather(
            *(cb(event) for cb in list(self._subscribers)), return_exceptions=True
        )
        for r in results:
            if isinstance(r, Exception):
                logger.exception("Event subscriber raised", exc_info=r)
        return event

    async def emit(self, type: EventType, *, actor_id: str | None = None, **payload: Any) -> Event:
        event = Event(type=type, actor_id=actor_id, payload=payload)
        return await self.publish(event)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
