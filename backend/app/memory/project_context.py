"""JSON persistence for the structured project state: ProjectContext,
Backlog, and per-agent AgentStatus. Markdown narrative generation lives in
markdown_store.py; this module is purely "load/save the typed objects"."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.schemas.agent import AgentStatus
from app.schemas.project import ProjectContext
from app.schemas.task import Backlog

logger = logging.getLogger("ai_dev_pod.memory")


class JsonModelStore:
    """Tiny helper: load/save one Pydantic model to/from a JSON file,
    tolerating a missing file (returns the provided default)."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, model_cls, default_factory):
        if not self.path.exists():
            return default_factory()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return model_cls.model_validate(raw)
        except Exception:
            logger.exception("Failed to load %s; falling back to default.", self.path)
            return default_factory()

    def save(self, model) -> None:
        self.path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


class ProjectContextStore(JsonModelStore):
    def load(self) -> ProjectContext:  # type: ignore[override]
        return super().load(ProjectContext, ProjectContext)

    def save(self, context: ProjectContext) -> None:  # type: ignore[override]
        context.touch()
        super().save(context)


class BacklogStore(JsonModelStore):
    def load(self) -> Backlog:  # type: ignore[override]
        return super().load(Backlog, Backlog)

    def save(self, backlog: Backlog) -> None:  # type: ignore[override]
        super().save(backlog)


class AgentStatusStore:
    """A small dict-of-AgentStatus persisted as one JSON file."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, AgentStatus]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {k: AgentStatus.model_validate(v) for k, v in raw.items()}
        except Exception:
            logger.exception("Failed to load %s; starting with no agent status.", self.path)
            return {}

    def save(self, statuses: dict[str, AgentStatus]) -> None:
        raw = {k: json.loads(v.model_dump_json()) for k, v in statuses.items()}
        self.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
