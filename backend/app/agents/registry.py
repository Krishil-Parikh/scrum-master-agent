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
from app.agents.profiles import PROFILES
from app.agents.scrum_master import ScrumMasterAgent
from app.schemas.agent import AgentSpecialty, AgentStatus


class AgentRegistry:
    def __init__(self) -> None:
        self.scrum_master = ScrumMasterAgent()
        self._agent_classes: dict[AgentSpecialty, type[BaseAgent]] = {
            AgentSpecialty.FRONTEND: FrontendAgent,
            AgentSpecialty.BACKEND: BackendAgent,
            AgentSpecialty.AI_ML: AiMlAgent,
            AgentSpecialty.DEVOPS: DevOpsAgent,
            AgentSpecialty.MLOPS: MlOpsAgent,
            AgentSpecialty.DATABASE: DatabaseAgent,
        }
        self._agents: dict[str, BaseAgent] = {
            AgentSpecialty.SCRUM_MASTER.value: self.scrum_master,
            **{specialty.value: cls() for specialty, cls in self._agent_classes.items()},
        }
        # agent_id ("backend-2") -> instance, for extra instances spawned
        # beyond the one primary agent per specialty (scaling roadmap #4).
        self._extra_instances: dict[str, BaseAgent] = {}

    def get(self, agent_id: str) -> BaseAgent:
        return self._agents[agent_id]

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def developers(self) -> list[BaseAgent]:
        return [a for a in self._agents.values() if a.agent_id != AgentSpecialty.SCRUM_MASTER.value]

    # ---- Horizontal scaling (roadmap #4): more bounded agents for a
    # specialty carrying more work than one agent can reasonably churn
    # through, instead of a bigger context for one agent. Each extra
    # instance is a full new agent object of the right subclass (so its
    # prompts/behavior are identical to the primary) with its own
    # agent_id/branch (so concurrent commits from sibling instances of the
    # same specialty never race on one shared git worktree) but the SAME
    # `.profile` (so specialty-matching in request_work, skill selection,
    # etc. all still treat it as "this specialty" everywhere that matters
    # semantically, not just this one git identity). ----

    def spawn_extra_instance(self, specialty: AgentSpecialty, index: int) -> BaseAgent:
        """Idempotent: calling this again for the same (specialty, index)
        returns the existing instance rather than creating a duplicate."""
        agent_id = f"{specialty.value}-{index}"
        if agent_id in self._agents:
            return self._agents[agent_id]
        base_profile = PROFILES[specialty]
        agent = self._agent_classes[specialty]()
        agent.identity = agent.identity.model_copy(update={
            "agent_id": agent_id,
            "display_name": f"{base_profile.display_name} #{index}",
            "branch": f"{base_profile.branch}-{index}",
        })
        agent.status.agent_id = agent_id
        self._extra_instances[agent_id] = agent
        self._agents[agent_id] = agent
        return agent

    def extra_instances_for(self, specialty: AgentSpecialty) -> list[BaseAgent]:
        prefix = f"{specialty.value}-"
        return [a for aid, a in self._extra_instances.items() if aid.startswith(prefix)]

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
