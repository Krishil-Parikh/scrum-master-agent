"""The Scrum Master — coordination, not implementation (PRD §6.1).

Owns: team formation, backlog generation, sprint planning/assignment, and
(lightweight, for now) sprint review. It leans on the deterministic planners in
``aamt.planning`` and only uses the LLM for the sprint *goal* sentence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings, get_settings
from ..events.bus import EventBus
from ..llm.provider import build_chat_model
from ..models.decision import Decision
from ..models.enums import BacklogItemKind, SprintStatus, TaskStatus
from ..models.event import EventType
from ..models.project import Project
from ..models.sprint import Sprint, SprintReview
from ..planning.backlog_planner import BacklogPlanner, materialize_backlog
from ..planning.sprint_planner import SprintPlan, plan_sprint
from ..state.store import ProjectStore
from .manager import AgentManager


@dataclass
class SprintPlanResult:
    sprint: Sprint
    plan: SprintPlan


class ScrumMaster:
    def __init__(
        self,
        store: ProjectStore,
        bus: EventBus,
        *,
        settings: Settings | None = None,
    ):
        self.store = store
        self.bus = bus
        self.settings = settings or get_settings()
        self.manager = AgentManager(store)

    # --- team ------------------------------------------------------
    def initialize_team(self, project: Project):
        self.manager.form_team()
        team = self.manager.team()
        self.bus.emit(
            EventType.TEAM_FORMED,
            project_id=project.id,
            roles=[a.role for a in team],
            size=len(team),
        )
        return team

    # --- backlog -------------------------------------------------
    def generate_backlog(self, project: Project):
        planner = BacklogPlanner(self.settings)
        plan = planner.generate(project)
        tasks = materialize_backlog(plan, project_id=project.id)

        self.store.save_tasks(tasks)
        self.store.validate_backlog()  # raises on dependency cycle

        task_items = [t for t in tasks if t.kind is BacklogItemKind.TASK]
        self.bus.emit(
            EventType.BACKLOG_CREATED,
            project_id=project.id,
            epic=plan.epic,
            n_items=len(tasks),
            n_tasks=len(task_items),
        )
        for t in task_items:
            self.bus.emit(
                EventType.BACKLOG_ITEM_ADDED,
                project_id=project.id,
                task_id=t.id,
                title=t.title,
                role=t.role,
                priority=t.priority.value,
            )
        return tasks

    # --- sprint planning ---------------------------------------
    def _goal_sentence(self, project: Project, plan: SprintPlan) -> str:
        titles = [
            self.store.get_task(tid).title  # type: ignore[union-attr]
            for tid in plan.task_ids
        ]
        if not titles:
            return "No ready work — backlog is blocked or empty."
        try:
            model = build_chat_model(
                model=self.settings.coordinator_model, settings=self.settings, max_tokens=120
            )
            resp = model.invoke(
                [
                    ("system", "You are a Scrum Master. Reply with ONE sentence: the sprint goal."),
                    (
                        "user",
                        f"Problem: {project.problem_statement}\n"
                        f"Tasks this sprint:\n- " + "\n- ".join(titles),
                    ),
                ]
            )
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            return text.strip().split("\n")[0][:200] or plan.goal_hint
        except Exception:
            return plan.goal_hint or "Deliver the selected backlog items."

    def _capacity_from_lessons(self) -> tuple[float | None, int | None]:
        """Shrink next sprint if the last retro asked to reduce scope/capacity."""
        sprints = self.store.list_sprints()
        if not sprints or not sprints[-1].retrospective:
            return None, None
        text = " ".join(a.lower() for a in sprints[-1].retrospective.action_items)
        if "reduce" in text and ("scope" in text or "capacity" in text):
            return (
                max(6.0, self.settings.sprint_capacity_points * 0.6),
                max(2, int(self.settings.sprint_max_tasks * 0.6)),
            )
        return None, None

    def plan_sprint(self, project: Project) -> SprintPlanResult:
        tasks = self.store.list_tasks()
        agents = self.manager.team()
        workload = self.manager.workload()

        cap_points, cap_tasks = self._capacity_from_lessons()
        plan = plan_sprint(
            tasks, agents, settings=self.settings, workload=workload,
            capacity_points=cap_points, max_tasks=cap_tasks,
        )

        number = project.sprint_count + 1
        sprint = Sprint(
            number=number,
            goal=self._goal_sentence(project, plan),
            status=SprintStatus.PLANNING,
            task_ids=list(plan.task_ids),
            assignments=dict(plan.assignments),
            planned_ticks=self.settings.sprint_length_ticks,
        )

        by_id = {t.id: t for t in tasks}
        for tid in plan.task_ids:
            t = by_id[tid]
            agent_id = plan.assignments[tid]
            t.sprint_id = sprint.id
            t.reassign(agent_id, actor="scrum-master", note=f"sprint {number} assignment")
            t.advance_to(TaskStatus.ASSIGNED, actor="scrum-master", note="sprint planned")
            self.store.save_task(t)
            self.manager.assign(agent_id, tid)
            self.bus.emit(
                EventType.TASK_ASSIGNED,
                project_id=project.id,
                sprint_id=sprint.id,
                task_id=tid,
                agent_id=agent_id,
            )

        self.store.save_sprint(sprint)
        project.current_sprint_id = sprint.id
        project.sprint_count = number
        self.store.save_project(project)

        self.record_decision(
            project,
            context=f"Sprint {number} planning",
            decision=f"Committed {len(plan.task_ids)} tasks; deferred {len(plan.deferred)}.",
            reason="; ".join(plan.rationale[:6]),
            sprint_id=sprint.id,
        )
        self.bus.emit(
            EventType.SPRINT_PLANNED,
            project_id=project.id,
            sprint_id=sprint.id,
            number=number,
            goal=sprint.goal,
            task_ids=list(plan.task_ids),
            deferred=list(plan.deferred),
        )
        return SprintPlanResult(sprint=sprint, plan=plan)

    def start_sprint(self, project: Project, sprint: Sprint) -> Sprint:
        from ..ids import now_ts

        sprint.status = SprintStatus.ACTIVE
        sprint.started_at = now_ts()
        self.store.save_sprint(sprint)
        self.bus.emit(EventType.SPRINT_STARTED, project_id=project.id,
                      sprint_id=sprint.id, number=sprint.number)
        return sprint

    # --- sprint review (lightweight; full ceremony is Phase 8) -----
    def review_sprint(self, project: Project, sprint: Sprint) -> SprintReview:
        from ..ids import now_ts

        tasks = [self.store.get_task(t) for t in sprint.task_ids]
        tasks = [t for t in tasks if t is not None]
        completed = [t.id for t in tasks if t.status is TaskStatus.DONE]
        blocked = [t.id for t in tasks if t.status is TaskStatus.BLOCKED]
        incomplete = [t.id for t in tasks if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)]

        commits = sum(len(t.commits) for t in tasks)
        velocity = sum((t.estimate or 0.0) for t in tasks if t.status is TaskStatus.DONE)

        review = SprintReview(
            planned=list(sprint.task_ids),
            completed=completed,
            incomplete=incomplete,
            blocked=blocked,
            commits=commits,
            velocity=velocity,
            notes=f"{len(completed)}/{len(sprint.task_ids)} tasks done",
        )
        sprint.review = review
        sprint.status = SprintStatus.REVIEW
        sprint.ended_at = now_ts()
        self.store.save_sprint(sprint)

        self.bus.emit(
            EventType.SPRINT_REVIEWED,
            project_id=project.id,
            sprint_id=sprint.id,
            completed=len(completed),
            planned=len(sprint.task_ids),
            blocked=len(blocked),
            velocity=velocity,
        )
        return review

    def complete_sprint(self, project: Project, sprint: Sprint) -> None:
        sprint.status = SprintStatus.COMPLETE
        self.store.save_sprint(sprint)
        self.bus.emit(EventType.SPRINT_COMPLETED, project_id=project.id,
                      sprint_id=sprint.id, number=sprint.number)

    # --- decisions ---------------------------------------------
    def record_decision(
        self,
        project: Project,
        *,
        context: str,
        decision: str,
        reason: str = "",
        sprint_id: str | None = None,
        related_tasks: list[str] | None = None,
    ) -> Decision:
        d = Decision(
            context=context,
            decision=decision,
            reason=reason,
            author="scrum-master",
            sprint_id=sprint_id,
            related_tasks=related_tasks or [],
        )
        self.store.save_decision(d)
        self.bus.emit(
            EventType.DECISION_RECORDED,
            project_id=project.id,
            sprint_id=sprint_id,
            decision=decision,
            context=context,
        )
        return d
