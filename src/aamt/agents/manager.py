"""AgentManager — lifecycle and bookkeeping for the team (phased plan §2.4).

The manager owns *state* about agents (who exists, what they're doing, their
track record). It does not run agents itself — the task-execution graph does
that — but it is the single place the Scrum Master asks "who is free?" and
"who is good at this?".
"""

from __future__ import annotations

from ..models.agent import Agent, AgentSpec, AgentStatus
from ..state.store import ProjectStore
from .roles import MVP_TEAM
from .messaging import Mailbox


class AgentManager:
    def __init__(self, store: ProjectStore):
        self.store = store

    # --- team formation --------------------------------------------
    def form_team(self, specs: list[AgentSpec] | None = None) -> list[Agent]:
        """Create agents for each spec that doesn't already exist (idempotent)."""
        specs = specs or MVP_TEAM
        created: list[Agent] = []
        for spec in specs:
            if self.store.agent_by_role(spec.role) is None:
                agent = Agent(spec=spec)
                self.store.save_agent(agent)
                created.append(agent)
        return created

    def team(self) -> list[Agent]:
        return self.store.list_agents()

    def developers(self) -> list[Agent]:
        return [a for a in self.team() if not a.spec.is_coordinator]

    def scrum_master(self) -> Agent | None:
        return self.store.agent_by_role("scrum-master")

    def get(self, agent_id: str) -> Agent | None:
        return self.store.get_agent(agent_id)

    def mailbox(self, agent_id: str) -> Mailbox:
        return Mailbox(self.store, agent_id)

    # --- status transitions ---------------------------------------
    def _save(self, agent: Agent) -> Agent:
        from ..ids import now_ts

        agent.updated_at = now_ts()
        self.store.save_agent(agent)
        return agent

    def set_status(self, agent_id: str, status: AgentStatus) -> Agent:
        agent = self._require(agent_id)
        agent.status = status
        return self._save(agent)

    def assign(self, agent_id: str, task_id: str) -> Agent:
        agent = self._require(agent_id)
        agent.current_task = task_id
        agent.status = AgentStatus.WORKING
        return self._save(agent)

    def record_result(self, agent_id: str, task_id: str, *, ok: bool) -> Agent:
        agent = self._require(agent_id)
        if ok:
            if task_id not in agent.completed_tasks:
                agent.completed_tasks.append(task_id)
        else:
            if task_id not in agent.failed_tasks:
                agent.failed_tasks.append(task_id)
        agent.current_task = None
        agent.status = AgentStatus.IDLE if ok else AgentStatus.FAILED
        return self._save(agent)

    def recover(self, agent_id: str) -> Agent:
        """Bring a FAILED/PAUSED agent back to IDLE so it can take new work."""
        agent = self._require(agent_id)
        if agent.status in (AgentStatus.FAILED, AgentStatus.PAUSED, AgentStatus.BLOCKED):
            agent.status = AgentStatus.IDLE
            agent.current_task = None
            self._save(agent)
        return agent

    def pause_all(self) -> None:
        for a in self.team():
            if a.status not in (AgentStatus.FAILED,):
                a.status = AgentStatus.PAUSED
                self._save(a)

    def resume_all(self) -> None:
        for a in self.team():
            if a.status == AgentStatus.PAUSED:
                a.status = AgentStatus.IDLE
                self._save(a)

    # --- selection helpers (inputs to Scrum Master assignment) -----
    def workload(self) -> dict[str, int]:
        """agent_id -> number of tasks currently assigned to it in the backlog."""
        counts = {a.id: 0 for a in self.team()}
        for t in self.store.list_tasks():
            if t.assignee in counts and t.status.value in {
                "ASSIGNED", "IN_PROGRESS", "IN_REVIEW", "TESTING", "BLOCKED", "REOPENED"
            }:
                counts[t.assignee] += 1
        return counts

    def best_for(self, *, role_hint: str | None, required_caps: list[str]) -> Agent | None:
        devs = self.developers()
        if not devs:
            return None
        load = self.workload()

        def score(a: Agent) -> tuple[float, float, int]:
            role_bonus = 1.0 if role_hint and a.role == role_hint else 0.0
            cap = a.capability_score(required_caps)
            # higher is better: role match, then capability, then *lower* load
            return (role_bonus, cap, -load.get(a.id, 0))

        return max(devs, key=score)

    def _require(self, agent_id: str) -> Agent:
        agent = self.store.get_agent(agent_id)
        if agent is None:
            raise KeyError(f"no such agent: {agent_id}")
        return agent
