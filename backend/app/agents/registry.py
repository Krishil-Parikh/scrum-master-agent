"""
AgentRegistry: instantiates and holds references to the full pod --
1 Scrum Master + 6 Developer Agents (PRD §7; Roadmap Phase 2 deliverable:
"Seven functional agents").

Everything else in the backend (orchestration, API routes) goes through
this registry rather than constructing agents itself, so there's exactly
one instance of each agent per process.
"""

from __future__ import annotations

from app.agents.ai_ml_agent import AiMlAgent
from app.agents.backend_agent import BackendAgent
from app.agents.base import BaseAgent
from app.agents.database_agent import DatabaseAgent
from app.agents.devops_agent import DevOpsAgent
from app.agents.frontend_agent import FrontendAgent
from app.agents.mlops_agent import MlOpsAgent
from app.agents.scrum_master import ScrumMasterAgent
from app.schemas.agent import AgentSpecialty, AgentStatus


class AgentRegistry:
    def __init__(self) -> None:
        self.scrum_master = ScrumMasterAgent()
        self._agents: dict[str, BaseAgent] = {
            AgentSpecialty.SCRUM_MASTER.value: self.scrum_master,
            AgentSpecialty.FRONTEND.value: FrontendAgent(),
            AgentSpecialty.BACKEND.value: BackendAgent(),
            AgentSpecialty.AI_ML.value: AiMlAgent(),
            AgentSpecialty.DEVOPS.value: DevOpsAgent(),
            AgentSpecialty.MLOPS.value: MlOpsAgent(),
            AgentSpecialty.DATABASE.value: DatabaseAgent(),
        }

    def get(self, agent_id: str) -> BaseAgent:
        return self._agents[agent_id]

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def developers(self) -> list[BaseAgent]:
        return [a for a in self._agents.values() if a.agent_id != AgentSpecialty.SCRUM_MASTER.value]

    def statuses(self) -> dict[str, AgentStatus]:
        return {aid: agent.status for aid, agent in self._agents.items()}

    def restore_statuses(self, saved: dict[str, AgentStatus]) -> None:
        for agent_id, status in saved.items():
            if agent_id in self._agents:
                self._agents[agent_id].status = status

    def persist_statuses(self) -> None:
        from app.memory.project_memory import get_current_project_id, get_project_memory

        if get_current_project_id():
            get_project_memory().save_agent_statuses(self.statuses())


_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
