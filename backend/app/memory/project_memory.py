"""
ProjectMemory: the single facade the rest of the backend uses to read/write
persistent project state. Combines the JSON structural stores, the Markdown
narrative writer, and append-only JSONL logs for events/messages/SME Q&A.

The MVP runs one active project at a time (matching the roadmap's "one real
end-to-end project" success gate), so there's a lightweight "current
project" pointer file alongside full per-project isolation under
project_data/<project_id>/ -- nothing here prevents multiple projects
existing side by side later.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import PROJECT_DATA_DIR
from app.memory.markdown_store import MarkdownStore
from app.memory.project_context import AgentStatusStore, BacklogStore, ProjectContextStore
from app.schemas.agent import AgentStatus
from app.schemas.communication import Message, MessageChannel, SMEAnswer, SMEQuestion
from app.schemas.event import Event
from app.schemas.project import ProjectContext
from app.schemas.task import Backlog

_CURRENT_PROJECT_POINTER = PROJECT_DATA_DIR / "current_project.txt"


class ProjectMemory:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.base_dir = PROJECT_DATA_DIR / project_id
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.context_store = ProjectContextStore(self.base_dir / "context.json")
        self.backlog_store = BacklogStore(self.base_dir / "backlog.json")
        self.agent_status_store = AgentStatusStore(self.base_dir / "agents.json")
        self.md = MarkdownStore(self.base_dir / "docs")

        self.events_path = self.base_dir / "events.jsonl"
        self.messages_path = self.base_dir / "messages.jsonl"
        self.sme_questions_path = self.base_dir / "sme_questions.json"

    # ---- Context / Backlog / Agent status (thin pass-through) ----

    def load_context(self) -> ProjectContext:
        return self.context_store.load()

    def save_context(self, context: ProjectContext) -> None:
        self.context_store.save(context)

    def load_backlog(self) -> Backlog:
        return self.backlog_store.load()

    def save_backlog(self, backlog: Backlog) -> None:
        self.backlog_store.save(backlog)

    def load_agent_statuses(self) -> dict[str, AgentStatus]:
        return self.agent_status_store.load()

    def save_agent_statuses(self, statuses: dict[str, AgentStatus]) -> None:
        self.agent_status_store.save(statuses)

    # ---- Events (JSONL append-only log) ----

    # High-frequency/noisy event types that already have their own home
    # (raw terminal output, the conversation feed, live agent-status pings)
    # don't also get a line in DEVELOPMENT_LOG.md -- otherwise every git
    # command and every chat message would double as a "development log"
    # entry, burying the events that actually matter for a human skimming
    # project history.
    _DEV_LOG_EXCLUDED = {"RUN_LOG", "MESSAGE_POSTED", "AGENT_STATE_CHANGED"}

    def append_event(self, event: Event) -> None:
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
        if event.type.value not in self._DEV_LOG_EXCLUDED:
            self.md.append_development_log(event.type.value, event.summary())

    def read_events(self, limit: int = 500) -> list[Event]:
        if not self.events_path.exists():
            return []
        lines = self.events_path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [Event.model_validate(json.loads(l)) for l in lines if l.strip()]

    # ---- Messages (conversation feed) ----

    def append_message(self, message: Message) -> None:
        with self.messages_path.open("a", encoding="utf-8") as f:
            f.write(message.model_dump_json() + "\n")

    def read_messages(self, channel: MessageChannel | None = None, limit: int = 500) -> list[Message]:
        if not self.messages_path.exists():
            return []
        lines = self.messages_path.read_text(encoding="utf-8").splitlines()
        messages = [Message.model_validate(json.loads(l)) for l in lines if l.strip()]
        if channel is not None:
            messages = [m for m in messages if m.channel == channel]
        return messages[-limit:]

    # ---- SME Q&A ----

    def _load_sme_records(self) -> dict:
        if not self.sme_questions_path.exists():
            return {}
        return json.loads(self.sme_questions_path.read_text(encoding="utf-8"))

    def _save_sme_records(self, records: dict) -> None:
        self.sme_questions_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def record_sme_question(self, question: SMEQuestion) -> None:
        records = self._load_sme_records()
        records[question.question_id] = {"question": json.loads(question.model_dump_json()), "answer": None}
        self._save_sme_records(records)
        self.md.append_sme_discussion(question, None)

    def record_sme_answer(self, question_id: str, answer: SMEAnswer) -> SMEQuestion | None:
        records = self._load_sme_records()
        entry = records.get(question_id)
        if not entry:
            return None
        entry["answer"] = json.loads(answer.model_dump_json())
        self._save_sme_records(records)
        question = SMEQuestion.model_validate(entry["question"])
        self.md.append_sme_discussion(question, answer)
        return question

    def list_sme_questions(self, *, open_only: bool = False) -> list[dict]:
        records = self._load_sme_records()
        items = list(records.values())
        if open_only:
            items = [i for i in items if i["answer"] is None]
        return items


def list_project_ids() -> list[str]:
    if not PROJECT_DATA_DIR.exists():
        return []
    return sorted(
        p.name
        for p in PROJECT_DATA_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def get_current_project_id() -> str | None:
    if _CURRENT_PROJECT_POINTER.exists():
        pid = _CURRENT_PROJECT_POINTER.read_text(encoding="utf-8").strip()
        return pid or None
    return None


def set_current_project_id(project_id: str) -> None:
    PROJECT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _CURRENT_PROJECT_POINTER.write_text(project_id, encoding="utf-8")
    get_project_memory.cache_clear()


@lru_cache
def get_project_memory(project_id: str | None = None) -> ProjectMemory:
    """Cached per project_id so every caller in the process shares the same
    in-memory handle (and thus doesn't race on the same files pointlessly)."""
    pid = project_id or get_current_project_id()
    if not pid:
        raise ValueError("No current project set. Create/intake a project first.")
    return ProjectMemory(pid)
