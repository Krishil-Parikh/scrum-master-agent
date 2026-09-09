"""Drive a project from problem statement to (attempted) working software.

    create_project -> bootstrap (team + backlog) -> [ plan sprint -> execute
    sprint -> review ] * until the backlog is done or max_sprints is hit.

Task execution reuses the Phase-1 task graph unchanged — this layer only
sequences tasks by dependency and keeps project state + events in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..agents.manager import AgentManager
from ..agents.scrum_master import ScrumMaster, SprintPlanResult
from ..ceremonies.retrospective import run_retrospective
from ..ceremonies.standup import run_standup
from ..config import Settings, get_settings
from ..events.bus import EventBus
from ..integration.merge import integrate_branch
from ..integration.reviewer import ReviewerAgent
from ..models.enums import BacklogItemKind, ProjectStatus, TaskStatus
from ..models.event import EventType
from ..models.project import Project, ProjectConstraints
from ..models.sprint import Sprint
from ..runtime.task_graph import TaskRunResult, run_task
from ..state.backlog import blocking_dependencies, topological_order
from ..state.store import ProjectStore
from ..tools.workspace import Workspace


class Paused(RuntimeError):
    """Raised inside the run loop when the human control file says PAUSE/STOP."""


@dataclass
class SprintExecution:
    sprint: Sprint
    results: list[TaskRunResult] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    review_rejected: list[str] = field(default_factory=list)

    @property
    def done(self) -> int:
        return sum(1 for r in self.results if r.ok)


class Orchestrator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.store = ProjectStore(self.settings.state_db_path)
        self.bus = EventBus(self.settings.data_dir / "events.db")
        self.sm = ScrumMaster(self.store, self.bus, settings=self.settings)
        self.manager = AgentManager(self.store)
        self.reviewer = ReviewerAgent(self.settings)

    # --- human controls (phased plan §10.6) --------------------------
    @property
    def _control_path(self):
        return self.settings.data_dir / self.settings.control_file

    def signal(self, state: str) -> None:
        """Write RUN | PAUSE | STOP to the control file."""
        self._control_path.write_text(state.strip().upper(), encoding="utf-8")

    def _control(self) -> str:
        try:
            return self._control_path.read_text(encoding="utf-8").strip().upper() or "RUN"
        except OSError:
            return "RUN"

    def _checkpoint(self) -> None:
        c = self._control()
        if c in ("PAUSE", "STOP"):
            self.bus.emit(EventType.ESCALATED_TO_HUMAN, reason=f"run {c.lower()}d by human control")
            raise Paused(c)

    # --- setup ---------------------------------------------------
    def create_project(
        self,
        *,
        name: str,
        problem_statement: str,
        repo_path: str,
        acceptance_criteria: list[str] | None = None,
        constraints: ProjectConstraints | None = None,
        human_mode: str | None = None,
    ) -> Project:
        from pathlib import Path

        repo = Path(repo_path).resolve()
        repo.mkdir(parents=True, exist_ok=True)
        ws = Workspace(repo)
        ws.ensure_git_repo()
        self._seed_repo(ws)

        project = Project(
            name=name,
            problem_statement=problem_statement,
            acceptance_criteria=acceptance_criteria or [],
            constraints=constraints or ProjectConstraints(),
            repo_path=str(repo),
            status=ProjectStatus.CREATED,
        )
        if human_mode:
            from ..models.enums import HumanMode

            project.human_mode = HumanMode(human_mode)
        self.store.save_project(project)
        self.bus.emit(
            EventType.PROJECT_CREATED,
            project_id=project.id,
            name=name,
            repo=str(repo),
        )
        return project

    def bootstrap(self, project: Project) -> Project:
        project.status = ProjectStatus.PLANNING
        self.store.save_project(project)
        self.sm.initialize_team(project)
        self.sm.generate_backlog(project)
        return self.store.get_project() or project

    # --- one sprint --------------------------------------------
    def plan_next_sprint(self, project: Project) -> SprintPlanResult:
        return self.sm.plan_sprint(project)

    def execute_sprint(self, project: Project, sprint: Sprint) -> SprintExecution:
        self.sm.start_sprint(project, sprint)
        project.status = ProjectStatus.IN_PROGRESS
        self.store.save_project(project)

        execution = SprintExecution(sprint=sprint)
        all_tasks = self.store.list_tasks()
        in_sprint = set(sprint.task_ids)
        try:
            ordered = [t for t in topological_order(all_tasks) if t.id in in_sprint]
        except Exception:  # cycle — fall back to given order
            ordered = [t for t in all_tasks if t.id in in_sprint]

        for i, stub in enumerate(ordered):
            if i and self.settings.inter_task_seconds:
                import time

                time.sleep(self.settings.inter_task_seconds)
            task = self.store.get_task(stub.id)
            if task is None or task.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
                continue

            blocking = blocking_dependencies(task, self.store.list_tasks())
            if blocking:
                execution.skipped.append(task.id)
                self.bus.emit(
                    EventType.BLOCKER_CREATED,
                    project_id=project.id,
                    sprint_id=sprint.id,
                    task_id=task.id,
                    reason=f"unmet dependencies: {blocking}",
                )
                continue

            agent_id = sprint.assignments.get(task.id)
            agent = self.manager.get(agent_id) if agent_id else None
            role = agent.role if agent else (task.role or "backend")
            if agent:
                self.manager.assign(agent.id, task.id)

            result = run_task(
                task,
                workspace_root=project.repo_path or ".",
                agent_role=role,
                settings=self.settings,
                project_summary=self._project_summary(project),
                project_id=project.id,
                sprint_id=sprint.id,
            )

            self.store.save_task(result.task)
            for ev in result.events:
                self.bus.emit_dict(ev, project_id=project.id, sprint_id=sprint.id)
            execution.results.append(result)

            # --- Phase 6: review + integrate a task that passed the gate -----
            if result.ok:
                self._review_and_integrate(project, sprint, result, execution)
            if agent:
                self.manager.record_result(
                    agent.id, task.id,
                    ok=(self.store.get_task(task.id).status is TaskStatus.DONE),
                )

            # --- Phase 8: a standup after every sprint tick -----------------
            if self.settings.enable_standups:
                since = sprint.started_at or 0.0
                run_standup(self.store, self.bus, self.store.get_sprint(sprint.id),
                            tick=i + 1, since_ts=since, settings=self.settings)

        self.sm.review_sprint(project, self.store.get_sprint(sprint.id))
        if self.settings.enable_retro:
            run_retrospective(self.store, self.bus, self.store.get_sprint(sprint.id),
                              project_id=project.id, settings=self.settings)
        self.sm.complete_sprint(project, self.store.get_sprint(sprint.id))
        return execution

    def _review_and_integrate(
        self, project: Project, sprint: Sprint, result: TaskRunResult, execution: SprintExecution
    ) -> None:
        ws = Workspace(project.repo_path or ".",
                       allow_network=self.settings.allow_network_in_shell)
        task = self.store.get_task(result.task.id)
        if task is None:
            return

        if self.settings.enable_review:
            review = self.reviewer.review(task, ws)
            self.bus.emit(
                EventType.CODE_REVIEW_COMPLETED, project_id=project.id, sprint_id=sprint.id,
                task_id=task.id, approved=review.approved, severity=review.severity,
                comments=review.comments,
            )
            if not review.approved:
                execution.review_rejected.append(task.id)
                task.advance_to(TaskStatus.REOPENED, actor="reviewer", note=review.feedback()[:300])
                self.store.save_task(task)
                return

        if self.settings.enable_integration and result.branch:
            integ = integrate_branch(
                ws, result.branch, target=self.settings.integration_target_branch,
                settings=self.settings,
            )
            if integ.ok:
                execution.merged.append(task.id)
                self.bus.emit(
                    EventType.MERGE_COMPLETED, project_id=project.id, sprint_id=sprint.id,
                    task_id=task.id, target=integ.target, merge_commit=integ.merge_commit,
                )
            else:
                self.bus.emit(
                    EventType.MERGE_CONFLICT, project_id=project.id, sprint_id=sprint.id,
                    task_id=task.id, conflicts=integ.conflicts, note=integ.note,
                )
                task.advance_to(TaskStatus.REOPENED, actor="scrum-master",
                                note=f"integration failed: {integ.note[:200]}")
                self.store.save_task(task)
            # leave the repo on the integration branch for the next task's base
            ws.run_argv(["git", "checkout", self.settings.integration_target_branch])

    # --- full loop --------------------------------------------
    def run(
        self,
        *,
        name: str,
        problem_statement: str,
        repo_path: str,
        acceptance_criteria: list[str] | None = None,
        constraints: ProjectConstraints | None = None,
        max_sprints: int | None = None,
    ) -> Project:
        project = self.create_project(
            name=name,
            problem_statement=problem_statement,
            repo_path=repo_path,
            acceptance_criteria=acceptance_criteria,
            constraints=constraints,
        )
        project = self.bootstrap(project)
        # note: a pre-existing control file (e.g. an intentional `aamt pause`
        # before start) is honoured — only resume() clears a prior pause.
        return self._sprint_loop(project, max_sprints)

    def resume(self, *, max_sprints: int | None = None) -> Project:
        """Continue an existing project from persisted state (phased plan §10.3)."""
        project = self.store.get_project()
        if project is None:
            raise RuntimeError("no project in the state store to resume")
        self.signal("RUN")
        self.bus.emit(EventType.DECISION_RECORDED, project_id=project.id,
                      decision="resumed from persisted state", context="resume")
        return self._sprint_loop(project, max_sprints)

    def _sprint_loop(self, project: Project, max_sprints: int | None) -> Project:
        limit = max_sprints or self.settings.max_sprints
        try:
            for _ in range(limit):
                self._checkpoint()
                project = self.store.get_project() or project
                if self._backlog_complete():
                    break
                self._revive_blocked(project)
                self._carry_forward(project)
                planned = self.plan_next_sprint(project)
                if not planned.plan.task_ids:
                    self.bus.emit(
                        EventType.ESCALATED_TO_HUMAN, project_id=project.id,
                        reason="no ready tasks to schedule (backlog blocked or exhausted)",
                    )
                    break
                self.execute_sprint(project, planned.sprint)
                self._write_sprint_report(project, planned.sprint)
        except Paused as p:
            project = self.store.get_project() or project
            project.status = ProjectStatus.IN_PROGRESS
            self.store.save_project(project)
            if str(p) == "STOP":
                project.status = ProjectStatus.ABANDONED
                self.store.save_project(project)
            return project

        project = self.store.get_project() or project
        project.status = (
            ProjectStatus.COMPLETED if self._backlog_complete() else ProjectStatus.IN_PROGRESS
        )
        self.store.save_project(project)
        if project.status is ProjectStatus.COMPLETED:
            self.bus.emit(EventType.PROJECT_COMPLETED, project_id=project.id)
        self._write_final_report(project)
        return project

    def _carry_forward(self, project: Project) -> None:
        """Feed the last retrospective's action items into planning context."""
        sprints = self.store.list_sprints()
        if not sprints or not sprints[-1].retrospective:
            return
        actions = sprints[-1].retrospective.action_items
        if actions:
            self.sm.record_decision(
                project, context=f"carry-forward from sprint {sprints[-1].number}",
                decision="apply retrospective action items",
                reason="; ".join(actions[:6]),
            )

    def _write_sprint_report(self, project: Project, sprint: Sprint) -> None:
        """Write this sprint's standups + retro to disk as soon as it ends —
        scrum ceremonies should be visible on disk without waiting for the
        whole project to finish or for someone to run `aamt report`."""
        try:
            from ..reporting.reports import sprint_report

            reports_dir = self.settings.data_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            path = reports_dir / f"sprint-{sprint.number:02d}.md"
            path.write_text(sprint_report(self.store, sprint_id=sprint.id), encoding="utf-8")
            self.bus.emit(EventType.DECISION_RECORDED, project_id=project.id,
                          decision=f"sprint {sprint.number} report written to {path}",
                          context="reporting")
        except Exception:  # noqa: BLE001
            pass

    def _write_final_report(self, project: Project) -> None:
        try:
            from ..reporting.reports import (
                agent_report, daily_report, final_report, project_timeline, sprint_report,
            )

            # legacy path (kept — an existing test pins this exact filename)
            path = self.settings.data_dir / f"final_report_{project.id}.md"
            path.write_text(final_report(self.store, self.bus), encoding="utf-8")

            # full ceremony/report set, always regenerated and visible together
            reports_dir = self.settings.data_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "final-report.md").write_text(
                final_report(self.store, self.bus), encoding="utf-8")
            (reports_dir / "sprints.md").write_text(
                sprint_report(self.store), encoding="utf-8")
            (reports_dir / "timeline.md").write_text(
                project_timeline(self.bus, project.id), encoding="utf-8")
            (reports_dir / "agents.md").write_text(
                agent_report(self.store, self.bus), encoding="utf-8")
            (reports_dir / "daily.md").write_text(
                daily_report(self.store, self.bus), encoding="utf-8")

            self.bus.emit(EventType.DECISION_RECORDED, project_id=project.id,
                          decision=f"final report written to {path}", context="reporting")
        except Exception:  # noqa: BLE001
            pass

    # --- helpers ---------------------------------------------
    def _seed_repo(self, ws: Workspace) -> None:
        """Give an empty repo a place for code and tests to live (idempotent)."""
        if list(p for p in ws.root.iterdir() if p.name not in {".git", ".gitignore"}):
            return
        ws.write_file("src/__init__.py", "")
        ws.write_file("tests/__init__.py", "")
        ws.write_file(
            "conftest.py",
            "import sys\nfrom pathlib import Path\n\n"
            "_src = str(Path(__file__).parent / 'src')\n"
            "if _src not in sys.path:\n    sys.path.insert(0, _src)\n",
        )
        ws.write_file("pytest.ini", "[pytest]\ntestpaths = tests\n")
        ws.write_file("README.md", "# Project\n\nScaffolded by aamt.\n")
        ws.commit_all("chore: scaffold repo", trailer=self.settings.commit_trailer)

    def _revive_blocked(self, project: Project) -> int:
        """BLOCKED tasks whose dependencies are all DONE get another chance."""
        from ..models.enums import TaskStatus
        from ..state.backlog import blocking_dependencies

        tasks = self.store.list_tasks()
        revived = 0
        for t in tasks:
            if t.status is not TaskStatus.BLOCKED:
                continue
            if not blocking_dependencies(t, tasks):
                if t.advance_to(TaskStatus.READY, actor="scrum-master", note="revive: deps satisfied"):
                    self.store.save_task(t)
                    revived += 1
        if revived:
            self.bus.emit(
                EventType.DECISION_RECORDED,
                project_id=project.id,
                decision=f"revived {revived} blocked task(s) for another attempt",
                context="replanning",
            )
        return revived

    def _project_summary(self, project: Project) -> str:
        c = project.constraints
        bits = [f"{project.name}: {project.problem_statement}"]
        if c.language:
            bits.append(f"language: {c.language}")
        if c.framework:
            bits.append(f"framework: {c.framework}")
        if project.acceptance_criteria:
            bits.append("project acceptance: " + "; ".join(project.acceptance_criteria))
        return "\n".join(bits)

    def _backlog_complete(self) -> bool:
        tasks = [
            t for t in self.store.list_tasks() if t.kind is BacklogItemKind.TASK
        ]
        if not tasks:
            return False
        return all(
            t.status in (TaskStatus.DONE, TaskStatus.CANCELLED) for t in tasks
        )

    def close(self) -> None:
        self.store.close()
        self.bus.close()
