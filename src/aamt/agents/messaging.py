"""Structured agent-to-agent messaging (phased plan §2.5, PRD §16).

Messages are persisted through the :class:`ProjectStore` so decisions and
contract changes survive outside any agent's transient context.
"""

from __future__ import annotations

from ..models.decision import AgentMessage
from ..state.store import ProjectStore

# Recognised message types — free-form is allowed but these are the ones the
# Scrum Master and developer agents act on.
API_CONTRACT_UPDATE = "API_CONTRACT_UPDATE"
DEPENDENCY_NOTICE = "DEPENDENCY_NOTICE"
BLOCKER_NOTICE = "BLOCKER_NOTICE"
QUESTION = "QUESTION"
NEW_TASK_PROPOSAL = "NEW_TASK_PROPOSAL"
DECISION_NOTICE = "DECISION_NOTICE"


class Mailbox:
    """Per-agent view over the shared message store."""

    def __init__(self, store: ProjectStore, agent_id: str):
        self._store = store
        self.agent_id = agent_id

    def send(
        self,
        recipient: str,
        type: str,
        content: str,
        *,
        related_tasks: list[str] | None = None,
    ) -> AgentMessage:
        msg = AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            type=type,
            content=content,
            related_tasks=related_tasks or [],
        )
        self._store.save_message(msg)
        return msg

    def broadcast(self, type: str, content: str, **kw) -> AgentMessage:
        return self.send("broadcast", type, content, **kw)

    def inbox(self, *, unread_only: bool = True) -> list[AgentMessage]:
        return self._store.list_messages(recipient=self.agent_id, unread_only=unread_only)

    def mark_read(self, *messages: AgentMessage) -> None:
        for m in messages:
            m.read = True
            self._store.save_message(m)

    def drain(self) -> list[AgentMessage]:
        """Return unread messages and mark them read in one step."""
        msgs = self.inbox(unread_only=True)
        self.mark_read(*msgs)
        return msgs
