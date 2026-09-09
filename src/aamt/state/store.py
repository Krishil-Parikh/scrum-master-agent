"""SQLite-backed project state (phased plan §3.5, §0.2).

One store == one project. Entities are stored as JSON documents keyed by id so
the schema follows the pydantic models without migrations during early phases.
The store survives process restart; callers reload it and resume.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from ..models import (
    Agent,
    AgentMessage,
    Decision,
    Project,
    Sprint,
    Standup,
    Task,
    TaskStatus,
)
from .backlog import ready_tasks, validate_no_cycles

_SCHEMA = """
CREATE TABLE IF NOT EXISTS project  (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agents   (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks    (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sprints  (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS standups (id TEXT PRIMARY KEY, doc TEXT NOT NULL);
"""

M = TypeVar("M", bound=BaseModel)


class ProjectStore:
    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- generic upsert / get -------------------------------------
    def _upsert(self, table: str, id_: str, model: BaseModel) -> None:
        with self._lock:
            self._conn.execute(
                f"INSERT INTO {table} (id, doc) VALUES (?, ?) "
                f"ON CONFLICT(id) DO UPDATE SET doc = excluded.doc",
                (id_, model.model_dump_json()),
            )
            self._conn.commit()

    def _get(self, table: str, id_: str, cls: type[M]) -> M | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT doc FROM {table} WHERE id = ?", (id_,)
            ).fetchone()
        return cls.model_validate_json(row[0]) if row else None

    def _all(self, table: str, cls: type[M]) -> list[M]:
        with self._lock:
            rows = self._conn.execute(f"SELECT doc FROM {table}").fetchall()
        return [cls.model_validate_json(r[0]) for r in rows]

    # --- project ------------------------------------------------
    def save_project(self, project: Project) -> None:
        self._upsert("project", project.id, project)

    def get_project(self) -> Project | None:
        with self._lock:
            row = self._conn.execute("SELECT doc FROM project LIMIT 1").fetchone()
        return Project.model_validate_json(row[0]) if row else None

    # --- agents -----------------------------------------------
    def save_agent(self, agent: Agent) -> None:
        self._upsert("agents", agent.id, agent)

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._get("agents", agent_id, Agent)

    def list_agents(self) -> list[Agent]:
        return self._all("agents", Agent)

    def agent_by_role(self, role: str) -> Agent | None:
        return next((a for a in self.list_agents() if a.role == role), None)

    # --- tasks ----------------------------------------------
    def save_task(self, task: Task) -> None:
        self._upsert("tasks", task.id, task)

    def get_task(self, task_id: str) -> Task | None:
        return self._get("tasks", task_id, Task)

    def list_tasks(self, *, status: TaskStatus | None = None, sprint_id: str | None = None) -> list[Task]:
        tasks = self._all("tasks", Task)
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if sprint_id is not None:
            tasks = [t for t in tasks if t.sprint_id == sprint_id]
        return sorted(tasks, key=lambda t: t.created_at)

    def save_tasks(self, tasks: Iterable[Task]) -> None:
        for t in tasks:
            self.save_task(t)

    def ready_tasks(self, *, sprint_id: str | None = None) -> list[Task]:
        pool = self.list_tasks(sprint_id=sprint_id) if sprint_id else self.list_tasks()
        # dependencies may point outside the sprint, so resolve against all tasks
        all_tasks = self.list_tasks()
        ready_ids = {t.id for t in ready_tasks(all_tasks)}
        return [t for t in pool if t.id in ready_ids]

    def validate_backlog(self) -> None:
        validate_no_cycles(self.list_tasks())

    # --- sprints --------------------------------------------
    def save_sprint(self, sprint: Sprint) -> None:
        self._upsert("sprints", sprint.id, sprint)

    def get_sprint(self, sprint_id: str) -> Sprint | None:
        return self._get("sprints", sprint_id, Sprint)

    def list_sprints(self) -> list[Sprint]:
        return sorted(self._all("sprints", Sprint), key=lambda s: s.number)

    def current_sprint(self) -> Sprint | None:
        project = self.get_project()
        if project and project.current_sprint_id:
            return self.get_sprint(project.current_sprint_id)
        return None

    # --- decisions / messages ------------------------------
    def save_decision(self, decision: Decision) -> None:
        self._upsert("decisions", decision.id, decision)

    def list_decisions(self) -> list[Decision]:
        return sorted(self._all("decisions", Decision), key=lambda d: d.ts)

    def save_standup(self, standup: Standup) -> None:
        self._upsert("standups", standup.id, standup)

    def list_standups(self, *, sprint_id: str | None = None) -> list[Standup]:
        rows = self._all("standups", Standup)
        if sprint_id is not None:
            rows = [s for s in rows if s.sprint_id == sprint_id]
        return sorted(rows, key=lambda s: (s.ts, s.tick))

    def save_message(self, message: AgentMessage) -> None:
        self._upsert("messages", message.id, message)

    def list_messages(self, *, recipient: str | None = None, unread_only: bool = False) -> list[AgentMessage]:
        msgs = sorted(self._all("messages", AgentMessage), key=lambda m: m.ts)
        if recipient is not None:
            msgs = [m for m in msgs if m.recipient in (recipient, "broadcast")]
        if unread_only:
            msgs = [m for m in msgs if not m.read]
        return msgs

    def close(self) -> None:
        with self._lock:
            self._conn.close()
