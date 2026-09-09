"""A minimal append-only event bus backed by SQLite.

Design constraints from the plan:

* **Append-only** — events are never mutated or deleted; the log is the audit
  trail (phased plan §2.2, §9.1).
* **Durable** — every emit is committed to disk immediately so a crash mid-sprint
  loses nothing (phased plan §10.3).
* **Observable** — synchronous subscribers get each event as it lands, which is
  how the CLI / reporting layer render a live activity feed.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

from ..models.event import Event, EventType

Subscriber = Callable[[Event], None]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT NOT NULL UNIQUE,
    type       TEXT NOT NULL,
    ts         REAL NOT NULL,
    project_id TEXT,
    sprint_id  TEXT,
    agent_id   TEXT,
    task_id    TEXT,
    payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_project ON events(project_id, seq);
CREATE INDEX IF NOT EXISTS ix_events_task    ON events(task_id, seq);
CREATE INDEX IF NOT EXISTS ix_events_sprint  ON events(sprint_id, seq);
CREATE INDEX IF NOT EXISTS ix_events_type    ON events(type, seq);
"""


class EventBus:
    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._subscribers: list[Subscriber] = []

    # --- subscription -------------------------------------------------
    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        """Register ``fn``; returns an unsubscribe callable."""
        with self._lock:
            self._subscribers.append(fn)

        def _unsub() -> None:
            with self._lock:
                if fn in self._subscribers:
                    self._subscribers.remove(fn)

        return _unsub

    # --- emit -------------------------------------------------------
    def emit(
        self,
        type: EventType,
        *,
        project_id: str | None = None,
        sprint_id: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
        **payload: Any,
    ) -> Event:
        event = Event(
            type=type,
            project_id=project_id,
            sprint_id=sprint_id,
            agent_id=agent_id,
            task_id=task_id,
            payload=payload,
        )
        return self.emit_event(event)

    def emit_dict(
        self,
        ev: dict[str, Any],
        *,
        project_id: str | None = None,
        sprint_id: str | None = None,
        agent_id: str | None = None,
    ) -> Event:
        """Emit an event described as ``{"type": str, "payload": {...}}``.

        Routing keys (``task_id`` / ``sprint_id`` / ``agent_id`` / ``project_id``)
        are lifted out of the payload if present so callers don't have to.
        """
        payload = dict(ev.get("payload", {}))
        event = Event(
            type=EventType(ev["type"]),
            project_id=payload.pop("project_id", project_id),
            sprint_id=payload.pop("sprint_id", sprint_id),
            agent_id=payload.pop("agent_id", agent_id),
            task_id=payload.pop("task_id", None),
            payload=payload,
        )
        return self.emit_event(event)

    def emit_event(self, event: Event) -> Event:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (id, type, ts, project_id, sprint_id, agent_id, task_id, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.type.value,
                    event.ts,
                    event.project_id,
                    event.sprint_id,
                    event.agent_id,
                    event.task_id,
                    json.dumps(event.payload, default=str),
                ),
            )
            self._conn.commit()
            subs = list(self._subscribers)
        for fn in subs:
            try:
                fn(event)
            except Exception:  # a bad subscriber must never break the producer
                pass
        return event

    # --- read -----------------------------------------------------
    def _row_to_event(self, row: tuple) -> Event:
        (_seq, id_, type_, ts, pid, sid, aid, tid, payload) = row
        return Event(
            id=id_,
            type=EventType(type_),
            ts=ts,
            project_id=pid,
            sprint_id=sid,
            agent_id=aid,
            task_id=tid,
            payload=json.loads(payload),
        )

    def query(
        self,
        *,
        project_id: str | None = None,
        sprint_id: str | None = None,
        task_id: str | None = None,
        types: Iterable[EventType] | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if sprint_id:
            clauses.append("sprint_id = ?")
            params.append(sprint_id)
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if types:
            type_list = list(types)
            clauses.append(f"type IN ({','.join('?' for _ in type_list)})")
            params.extend(t.value for t in type_list)
        sql = "SELECT * FROM events"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq ASC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def __iter__(self) -> Iterator[Event]:
        yield from self.query()

    def count(self, *, project_id: str | None = None) -> int:
        with self._lock:
            if project_id:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM events WHERE project_id = ?", (project_id,)
                ).fetchone()
            else:
                row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
