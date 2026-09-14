"""
The Orchestrator connects every layer into the one end-to-end workflow the
PRD/Roadmap describe (PRD §45 Definition of Done; Roadmap Phase 17):

    Intake -> Context -> Independent Analysis -> Discussion -> SME
    -> Agile Planning -> Task Allocation -> Parallel Development
    -> Git Collaboration -> Conflict Resolution -> Cross-Specialty Assistance
    -> Testing -> Code Review -> Sprint Review -> Retrospective -> Release

`run_full_pipeline` drives the whole thing for one project. Individual
phase methods are also usable on their own by the API layer where that's
useful (e.g. re-running just a stand-up), but the source of truth for "what
does an end-to-end run look like" is this file.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from app.agents.base import BaseAgent
from app.agents.registry import get_agent_registry
from app.communication.event_bus import get_event_bus
from app.config import get_settings
from app.git_layer.git_manager import get_git_manager
from app.intake.requirement_analyzer import analyze_document
from app.llm.prompts import truncate
from app.memory.project_memory import get_project_memory, set_current_project_id
from app.orchestration.run_control import RunStopped, get_run_controller
from app.orchestration.sme import run_sme_session
from app.schemas.agent import AgentState
from app.schemas.communication import MessageChannel, SMEQuestion
from app.schemas.event import EventType
from app.schemas.project import Decision, ProjectContext
from app.schemas.task import Backlog, Task, TaskStatus
from app.tools.command_runner import run_command

logger = logging.getLogger("ai_dev_pod.orchestrator")

# Buddy pairing for cross-specialty code review (PRD §17, §24): each
# developer reviews their buddy's work, loading the buddy's primary skill
# first -- this is the concrete moment the "Cross-Specialty Test" (Roadmap
# Phase 3 success gate) happens during a real run, not just in isolation.
REVIEW_BUDDIES = {
    "frontend": "backend",
    "backend": "frontend",
    "ai_ml": "mlops",
    "mlops": "ai_ml",
    "devops": "database",
    "database": "devops",
}

MAX_DEVELOPMENT_WAVES = 5


class Orchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.registry = get_agent_registry()
        self.bus = get_event_bus()
        self.run = get_run_controller()

    # ---- Phase 4: intake ------------------------------------------------

    async def start_new_project(self, name: str, raw_text: str) -> ProjectContext:
        await self.bus.emit(EventType.PHASE_STARTED, phase="intake")
        context = await analyze_document(name, raw_text)
        context.name = name
        set_current_project_id(context.project_id)
        memory = get_project_memory(context.project_id)
        memory.save_context(context)
        memory.md.write_project_md(context, team=self._team_names())
        memory.md.write_requirements_md(context)
        await self.bus.emit(EventType.PHASE_COMPLETED, phase="intake", project_id=context.project_id)
        return context

    def _team_names(self) -> list[str]:
        return [f"{a.identity.display_name} ({a.profile.specialty.value})" for a in self.registry.all()]

    # ---- Full pipeline ---------------------------------------------------

    async def run_full_pipeline(self, context: ProjectContext) -> dict:
        memory = get_project_memory(context.project_id)
        git = get_git_manager(context.project_id, remote_url=self.settings.demo_project_git_remote)
        self.run.start()

        try:
            await self._phase_setup_repo(context, git)
            analyses = await self._phase_independent_analysis(context, memory)
            qa_results = await self._phase_sme_session(context, memory, analyses)
            backlog = await self._phase_agile_planning(context, memory, qa_results)
            sprint = await self._phase_task_allocation_and_sprint(context, memory, backlog)
            await self._phase_parallel_development(context, memory, backlog, git)
            await self._phase_conflict_drill(context, memory, backlog, git)
            await self._phase_testing_pass(context, memory, backlog, git)
            standup_summary = await self._phase_standup(context, memory, backlog, sprint)
            review_summary = await self._phase_sprint_review(context, memory, backlog, sprint)
            retro = await self._phase_retrospective(context, memory, backlog, sprint, review_summary)

            context.status = "completed"
            memory.save_context(context)
            memory.md.write_project_md(context, team=self._team_names())
            self.run.complete()

            report = {
                "project_id": context.project_id,
                "sprint_id": sprint.sprint_id,
                "standup_summary": standup_summary,
                "review_summary": review_summary,
                "retrospective": retro,
                "task_counts": _task_status_counts(backlog),
                "branches": git.list_branches(),
                "recent_commits": git.recent_commits(limit=15),
            }
            await self.bus.emit(EventType.PHASE_COMPLETED, phase="full_pipeline", **_json_safe(report))
            return report
        except RunStopped:
            logger.info("Pipeline run stopped by request at phase %s", self.run.current_phase)
            self.run.stop()
            raise
        except Exception:
            logger.exception("Pipeline run failed")
            self.run.fail()
            raise

    # ---- Phase: repo setup ------------------------------------------------

    async def _phase_setup_repo(self, context: ProjectContext, git) -> None:
        await self.run.checkpoint("repo_setup")
        await self.bus.emit(EventType.PHASE_STARTED, phase="repo_setup")
        readme = f"# {context.name}\n\n{context.objective}\n\nBuilt by the AI Dev Pod.\n"
        result = git.init_repo(readme)
        for line in result.log_lines:
            await self.bus.emit(EventType.RUN_LOG, actor_id="system", text=line, channel="git")
        for agent in self.registry.developers():
            _, wt_result = git.ensure_agent_worktree(agent.agent_id, agent.identity.branch)
            for line in wt_result.log_lines:
                await self.bus.emit(EventType.RUN_LOG, actor_id=agent.agent_id, text=line, channel="git")
        await self.bus.emit(EventType.PHASE_COMPLETED, phase="repo_setup")

    # ---- Phase 5: independent analysis + discussion ------------------------

    async def _phase_independent_analysis(self, context: ProjectContext, memory) -> dict[str, dict]:
        await self.run.checkpoint("independent_analysis")
        await self.bus.emit(EventType.PHASE_STARTED, phase="independent_analysis")
        developers = self.registry.developers()
        results = await asyncio.gather(*(a.analyze_requirements(context) for a in developers))
        analyses: dict[str, dict] = {}
        for agent, analysis in zip(developers, results):
            analyses[agent.agent_id] = analysis
            if analysis.get("summary"):
                await agent.say(MessageChannel.DEVELOPERS, analysis["summary"])
        await self.registry.scrum_master.say(
            MessageChannel.SCRUM,
            f"Thanks all — I've reviewed everyone's analysis. "
            f"Consolidating {sum(len(a.get('questions', [])) for a in results)} question(s) for the SME.",
        )
        await self.bus.emit(EventType.PHASE_COMPLETED, phase="independent_analysis")
        return analyses

    # ---- Phase 6: SME session --------------------------------------------

    async def _phase_sme_session(self, context: ProjectContext, memory, analyses: dict[str, dict]):
        await self.run.checkpoint("sme_session")
        questions: list[SMEQuestion] = []
        for agent_id, analysis in analyses.items():
            agent = self.registry.get(agent_id)
            for q in analysis.get("questions", []) or []:
                if not isinstance(q, dict) or not q.get("text"):
                    continue
                questions.append(
                    SMEQuestion(
                        asked_by=agent.agent_id,
                        asked_by_name=agent.identity.display_name,
                        text=str(q["text"]),
                        reason=str(q.get("reason", "")),
                        priority=str(q.get("priority", "medium")),
                    )
                )

        if not questions:
            return []

        for q in questions:
            agent = self.registry.get(q.asked_by)
            await agent.say(MessageChannel.SME, q.text, sender_role="Developer")

        results = await run_sme_session(context, questions)
        for question, answer in results:
            if answer is None:
                continue
            context.decisions.append(
                Decision(context=question.text, decision=answer.decision, reason=answer.text, impact="Folded into Agile planning.")
            )
            memory.md.append_decision(context.decisions[-1])
            await self.registry.scrum_master.say(
                MessageChannel.SME, f"**Business SME:** {answer.text}", sender_role="SME"
            )

        context.open_questions = [
            oq for oq in context.open_questions if oq.question not in {q.text for q, a in results if a}
        ]
        memory.save_context(context)
        memory.md.write_requirements_md(context)
        return results

    # ---- Phase 7: Agile planning ------------------------------------------

    async def _phase_agile_planning(self, context: ProjectContext, memory, qa_results) -> Backlog:
        await self.run.checkpoint("agile_planning")
        await self.bus.emit(EventType.PHASE_STARTED, phase="agile_planning")
        sme_context = ""
        if qa_results:
            lines = [f"- Q: {q.text}\n  Decision: {a.decision}" for q, a in qa_results if a]
            if lines:
                sme_context = "\n\nSME clarifications:\n" + "\n".join(lines)

        await self.registry.scrum_master.set_state(AgentState.PLANNING)
        backlog = await self.registry.scrum_master.generate_backlog(context, sme_context=sme_context)
        memory.save_backlog(backlog)
        memory.md.write_agile_md(backlog)
        await self.registry.scrum_master.say(
            MessageChannel.SCRUM,
            f"Backlog is ready: {len(backlog.epics)} epics, {len(backlog.stories)} stories, "
            f"{len(backlog.tasks)} tasks.",
        )
        await self.bus.emit(EventType.PHASE_COMPLETED, phase="agile_planning", tasks=len(backlog.tasks))
        return backlog

    # ---- Phase 8: task allocation + sprint --------------------------------

    async def _phase_task_allocation_and_sprint(self, context: ProjectContext, memory, backlog: Backlog):
        await self.run.checkpoint("task_allocation")
        sm = self.registry.scrum_master
        sm.allocate_tasks(backlog)
        sprint = sm.create_sprint(backlog, name="Sprint 1", days=14)
        context.current_sprint_id = sprint.sprint_id
        context.status = "in_progress"
        memory.save_backlog(backlog)
        memory.save_context(context)
        memory.md.write_agile_md(backlog)
        await self.bus.emit(EventType.SPRINT_STARTED, actor_id="scrum_master", sprint_id=sprint.sprint_id, task_count=len(sprint.task_ids))
        await sm.say(
            MessageChannel.SCRUM,
            f"Sprint 1 planned — goal: {sprint.goal} "
            f"({len(sprint.task_ids)} tasks across the team). Let's get started!",
        )
        return sprint

    # ---- Phase 9-14: parallel development -----------------------------

    async def _phase_parallel_development(self, context: ProjectContext, memory, backlog: Backlog, git) -> None:
        sm = self.registry.scrum_master
        for wave in range(1, MAX_DEVELOPMENT_WAVES + 1):
            await self.run.checkpoint(f"development_wave_{wave}")
            sm.allocate_tasks(backlog)
            ready = [t for t in backlog.tasks.values() if t.status == TaskStatus.READY]
            if not ready:
                break

            by_agent: dict[str, list[Task]] = {}
            for t in ready:
                by_agent.setdefault(t.assigned_agent_id, []).append(t)

            await self.bus.emit(EventType.PHASE_STARTED, phase=f"development_wave_{wave}", agents=list(by_agent.keys()))
            await asyncio.gather(
                *(self._run_agent_task_queue(context, memory, backlog, git, agent_id, tasks) for agent_id, tasks in by_agent.items())
            )
            memory.save_backlog(backlog)
            memory.md.write_agile_md(backlog)
            await self.bus.emit(EventType.PHASE_COMPLETED, phase=f"development_wave_{wave}")

        sm.allocate_tasks(backlog)
        memory.save_backlog(backlog)
        memory.md.write_agile_md(backlog)

    async def _run_agent_task_queue(self, context, memory, backlog: Backlog, git, agent_id: str, tasks: list[Task]) -> None:
        agent = self.registry.get(agent_id)
        for task in tasks:
            await self._implement_one_task(context, memory, backlog, git, agent, task)

    async def _implement_one_task(self, context, memory, backlog: Backlog, git, agent: BaseAgent, task: Task) -> None:
        task.status = TaskStatus.IN_PROGRESS
        task.touch()
        await self.bus.emit(EventType.TASK_ASSIGNED, actor_id=agent.agent_id, task_id=task.task_id, title=task.title)
        await agent.say(MessageChannel.TASKS, f"Starting **{task.title}**.")
        await self.bus.emit(EventType.TASK_STARTED, actor_id=agent.agent_id, task_id=task.task_id)

        # --- sync in any completed dependency's branch first ---
        dep_context = ""
        for dep_id in task.depends_on:
            dep_task = backlog.tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED or not dep_task.branch:
                continue
            if dep_task.branch == agent.identity.branch:
                continue
            sync_result = git.sync_branch(agent.agent_id, dep_task.branch)
            for line in sync_result.log_lines:
                await self.bus.emit(EventType.RUN_LOG, actor_id=agent.agent_id, text=line, channel="git")
            if not sync_result.ok and sync_result.data.get("status") == "conflict":
                await self._resolve_sync_conflict(context, git, agent, dep_task, sync_result.data.get("conflicted_files", []))
            if dep_task.files_changed:
                snippets = []
                for path in dep_task.files_changed[:2]:
                    content = git.show_file_at_ref(agent.agent_id, "HEAD", path)
                    if content:
                        snippets.append(f"{path}:\n{truncate(content, 1200)}")
                if snippets:
                    dep_context += f"\n\nRelevant files from dependency '{dep_task.title}':\n" + "\n\n".join(snippets)

        # --- implement ---
        skill_body = agent.primary_skill_body()
        result = await agent.implement_task(context, task, extra_context=dep_context, skill_body=skill_body)
        if result.get("error") or not result.get("files"):
            task.status = TaskStatus.BLOCKED
            task.blocked_reason = "Implementation failed or produced no files."
            task.touch()
            await self.bus.emit(EventType.TASK_BLOCKED, actor_id=agent.agent_id, task_id=task.task_id, reason=task.blocked_reason)
            return

        commit_msg = f"{task.title}\n\n{result.get('summary', '')}".strip()
        commit_result = git.write_and_commit(agent.agent_id, agent.identity.branch, result["files"], commit_msg)
        for line in commit_result.log_lines:
            await self.bus.emit(EventType.RUN_LOG, actor_id=agent.agent_id, text=line, channel="git")

        if commit_result.ok and commit_result.data.get("sha"):
            task.files_changed = list(result["files"].keys())
            memory.md.append_git_activity(
                agent=agent.identity.display_name,
                branch=agent.identity.branch or "",
                commit=commit_result.data["sha"],
                purpose=task.title,
                files_changed=task.files_changed,
            )
            await self.bus.emit(
                EventType.PUSH_CREATED,
                actor_id=agent.agent_id,
                task_id=task.task_id,
                sha=commit_result.data["sha"],
                branch=agent.identity.branch,
            )
            push_result = git.push(agent.agent_id, agent.identity.branch or "")
            for line in push_result.log_lines:
                await self.bus.emit(EventType.RUN_LOG, actor_id=agent.agent_id, text=line, channel="git")
            await agent.say(
                MessageChannel.GIT,
                f"Pushed `{commit_result.data['sha']}` to `{agent.identity.branch}`: {result.get('summary', task.title)}",
            )

        # --- self-review, then buddy cross-specialty review ---
        self_review = await agent.review_files(context, task, result["files"])
        buddy_id = REVIEW_BUDDIES.get(agent.agent_id)
        buddy = self.registry.get(buddy_id) if buddy_id else None
        buddy_review = {"approved": True, "findings": []}
        if buddy is not None:
            await buddy.load_skill(agent.profile.specialty.value, reason=f"reviewing {agent.identity.display_name}'s change")
            await self.bus.emit(EventType.REVIEW_REQUESTED, actor_id=agent.agent_id, reviewer=buddy.agent_id, task_id=task.task_id)
            buddy_review = await buddy.review_files(context, task, result["files"])
            findings = buddy_review.get("findings", []) or []
            verdict = "approved" if buddy_review.get("approved", True) else "requested changes"
            await buddy.say(
                MessageChannel.TASKS,
                f"Reviewed **{task.title}** from {agent.identity.display_name} — {verdict}."
                + (f" {len(findings)} finding(s)." if findings else " No findings."),
            )
            await self.bus.emit(EventType.REVIEW_COMPLETED, actor_id=buddy.agent_id, task_id=task.task_id, approved=buddy_review.get("approved", True))

        blocking = [f for f in (buddy_review.get("findings") or []) if str(f.get("severity", "")).upper() in ("P0", "P1")]
        if blocking:
            task.status = TaskStatus.BLOCKED
            task.blocked_reason = "; ".join(f.get("summary", "") for f in blocking)
            task.touch()
            await self.bus.emit(EventType.TASK_BLOCKED, actor_id=agent.agent_id, task_id=task.task_id, reason=task.blocked_reason)
            return

        task.status = TaskStatus.COMPLETED
        task.touch()
        await agent.set_state(AgentState.COMPLETED, note=task.title)
        await self.bus.emit(EventType.TASK_COMPLETED, actor_id=agent.agent_id, task_id=task.task_id, title=task.title)

    async def _resolve_sync_conflict(self, context, git, agent: BaseAgent, dep_task: Task, conflicted_files: list[str]) -> None:
        await self.bus.emit(
            EventType.MERGE_CONFLICT, actor_id=agent.agent_id, files=conflicted_files, with_branch=dep_task.branch
        )
        dep_agent = self.registry.get(dep_task.assigned_agent_id) if dep_task.assigned_agent_id else None
        other_name = dep_agent.identity.display_name if dep_agent else dep_task.branch or "another agent"
        resolved: dict[str, str] = {}
        for path in conflicted_files:
            ours = git.show_file_at_ref(agent.agent_id, "HEAD", path)
            theirs = git.show_file_at_ref(agent.agent_id, dep_task.branch or "", path)
            outcome = await agent.resolve_conflict(
                context, file_path=path, my_version=ours, other_agent_name=other_name, other_version=theirs, my_task=dep_task
            )
            resolved[path] = outcome.get("resolved_content", ours)
        commit = git.resolve_conflict(agent.agent_id, resolved, f"Merge {dep_task.branch}: resolve conflict in {', '.join(conflicted_files)}")
        for line in commit.log_lines:
            await self.bus.emit(EventType.RUN_LOG, actor_id=agent.agent_id, text=line, channel="git")
        await self.bus.emit(EventType.MERGE_RESOLVED, actor_id=agent.agent_id, files=conflicted_files)

    # ---- Deliberate conflict drill (Roadmap Phase 12 / Phase 19 Test 3) ----

    async def _phase_conflict_drill(self, context: ProjectContext, memory, backlog: Backlog, git) -> None:
        await self.run.checkpoint("conflict_drill")
        frontend = self.registry.get("frontend")
        backend = self.registry.get("backend")
        shared_task = Task(
            task_id="conflict-drill",
            story_id="conflict-drill",
            title="Document the shared API integration contract",
            description="Write INTEGRATION.md describing the request/response contract between frontend and backend.",
            specialty=frontend.profile.specialty,
            acceptance_criteria=["Describes the endpoints, payload shapes, and error format the other side depends on."],
        )
        await self.bus.emit(EventType.PHASE_STARTED, phase="conflict_drill")

        fe_result, be_result = await asyncio.gather(
            frontend.implement_task(
                context, shared_task,
                extra_context="Write exactly one file: INTEGRATION.md, describing the API contract from the FRONTEND's perspective (what it expects to call and receive).",
            ),
            backend.implement_task(
                context, shared_task,
                extra_context="Write exactly one file: INTEGRATION.md, describing the API contract from the BACKEND's perspective (what it will expose and return).",
            ),
        )
        for agent, result in ((frontend, fe_result), (backend, be_result)):
            if result.get("files"):
                commit = git.write_and_commit(agent.agent_id, agent.identity.branch, result["files"], "Document API integration contract")
                for line in commit.log_lines:
                    await self.bus.emit(EventType.RUN_LOG, actor_id=agent.agent_id, text=line, channel="git")

        sync_result = git.sync_branch(frontend.agent_id, backend.identity.branch or "developer-2")
        for line in sync_result.log_lines:
            await self.bus.emit(EventType.RUN_LOG, actor_id=frontend.agent_id, text=line, channel="git")

        if not sync_result.ok and sync_result.data.get("status") == "conflict":
            conflicted_files = sync_result.data.get("conflicted_files", [])
            await self.bus.emit(EventType.MERGE_CONFLICT, actor_id=frontend.agent_id, files=conflicted_files, with_branch=backend.identity.branch)
            await frontend.say(
                MessageChannel.GIT,
                f"Conflict merging **{backend.identity.display_name}**'s branch — both of us edited "
                f"`INTEGRATION.md`. Reconciling both perspectives into one contract.",
            )
            resolved: dict[str, str] = {}
            for path in conflicted_files:
                ours = git.show_file_at_ref(frontend.agent_id, "HEAD", path)
                theirs = git.show_file_at_ref(frontend.agent_id, backend.identity.branch or "", path)
                outcome = await frontend.resolve_conflict(
                    context, file_path=path, my_version=ours, other_agent_name=backend.identity.display_name,
                    other_version=theirs, my_task=shared_task,
                )
                resolved[path] = outcome.get("resolved_content", ours)
            commit = git.resolve_conflict(frontend.agent_id, resolved, "Merge developer-2: resolve INTEGRATION.md conflict")
            for line in commit.log_lines:
                await self.bus.emit(EventType.RUN_LOG, actor_id=frontend.agent_id, text=line, channel="git")
            memory.md.append_git_activity(
                agent=frontend.identity.display_name, branch=frontend.identity.branch or "",
                commit=commit.data.get("sha", "?"), purpose="Resolve merge conflict in INTEGRATION.md",
                files_changed=list(resolved.keys()), dependencies=f"merged {backend.identity.branch}",
            )
            await self.bus.emit(EventType.MERGE_RESOLVED, actor_id=frontend.agent_id, files=conflicted_files)
        else:
            await frontend.say(MessageChannel.GIT, "No conflict on merge — contracts happened to align.")

        await self.bus.emit(EventType.PHASE_COMPLETED, phase="conflict_drill")

    # ---- Phase 14: testing pass ------------------------------------------

    async def _phase_testing_pass(self, context: ProjectContext, memory, backlog: Backlog, git) -> None:
        await self.run.checkpoint("testing")
        await self.bus.emit(EventType.PHASE_STARTED, phase="testing")
        for agent in self.registry.developers():
            worktree = git.worktrees_dir / agent.agent_id
            if not worktree.exists():
                continue
            py_files = list(worktree.rglob("*.py"))
            if not py_files:
                continue
            for f in py_files[:10]:
                result = run_command(worktree, [sys.executable, "-m", "py_compile", str(f)], timeout=20)
                await self.bus.emit(
                    EventType.RUN_LOG, actor_id=agent.agent_id, channel="test",
                    text=f"$ python -m py_compile {f.relative_to(worktree)}\n{result.combined_output or '(no output -- syntax OK)'}",
                )
            test_files = list(worktree.rglob("test_*.py")) + list(worktree.rglob("*_test.py"))
            if test_files:
                result = run_command(worktree, [sys.executable, "-m", "pytest", "-q"], timeout=45)
                await self.bus.emit(
                    EventType.RUN_LOG, actor_id=agent.agent_id, channel="test",
                    text=f"$ python -m pytest -q\n{result.combined_output}",
                )
        await self.bus.emit(EventType.PHASE_COMPLETED, phase="testing")

    # ---- Phase 15: stand-up -----------------------------------------------

    async def _phase_standup(self, context: ProjectContext, memory, backlog: Backlog, sprint) -> str:
        await self.run.checkpoint("standup")
        sm = self.registry.scrum_master
        await sm.say(
            MessageChannel.SCRUM,
            "Good morning team! \n\nLet's start our daily standup. Please share:\n"
            "- What you completed\n- What you're working on next\n- Any blockers",
        )
        developers = self.registry.developers()

        def _recent_summary(agent_id: str) -> str:
            mine = [t for t in backlog.tasks.values() if t.assigned_agent_id == agent_id]
            done = [t.title for t in mine if t.status == TaskStatus.COMPLETED]
            blocked = [f"{t.title} ({t.blocked_reason})" for t in mine if t.status == TaskStatus.BLOCKED]
            lines = []
            if done:
                lines.append("Completed: " + "; ".join(done))
            if blocked:
                lines.append("Blocked: " + "; ".join(blocked))
            return "\n".join(lines)

        reports = await asyncio.gather(*(a.standup_report(context, _recent_summary(a.agent_id)) for a in developers))
        entries = []
        report_by_agent: dict[str, dict] = {}
        for agent, report in zip(developers, reports):
            report_by_agent[agent.agent_id] = report
            entries.append({"agent": agent.identity.display_name, **report})
            text = f"Yesterday: {report.get('yesterday', '—')}\nToday: {report.get('today', '—')}\nBlockers: {report.get('blockers', 'None')}"
            await agent.say(MessageChannel.DEVELOPERS, text)

        summary, blockers = sm.summarize_standup(report_by_agent)
        await sm.say(MessageChannel.SCRUM, summary)
        memory.md.append_standup(sprint.name, entries)
        await self.bus.emit(EventType.STANDUP_POSTED, actor_id="scrum_master", blockers=blockers)
        return summary

    # ---- Phase 15/27: sprint review -----------------------------------

    async def _phase_sprint_review(self, context: ProjectContext, memory, backlog: Backlog, sprint) -> str:
        await self.run.checkpoint("sprint_review")
        sm = self.registry.scrum_master
        summary = await sm.sprint_review_summary(context, backlog, sprint)
        sprint.status = "review"
        await sm.say(MessageChannel.SCRUM, f"**Sprint Review** — {summary}")
        memory.md.append_development_log("Sprint Review", summary)
        return summary

    # ---- Phase 15/29: retrospective ---------------------------------------

    async def _phase_retrospective(self, context: ProjectContext, memory, backlog: Backlog, sprint, review_summary: str) -> dict:
        await self.run.checkpoint("retrospective")
        sm = self.registry.scrum_master
        developers = self.registry.developers()
        inputs = await asyncio.gather(*(a.retro_input(context, review_summary) for a in developers))
        retro = sm.synthesize_retrospective(list(inputs))
        memory.md.append_retrospective(
            sprint_name=sprint.name,
            went_well=retro["went_well"],
            went_wrong=retro["went_wrong"],
            action_items=retro["action_items"],
        )
        sprint.status = "completed"
        top_action = retro["action_items"][0] if retro["action_items"] else "Keep current process."
        await sm.say(MessageChannel.SCRUM, f"**Retrospective complete.** Top action item: {top_action}")
        await self.bus.emit(EventType.RETROSPECTIVE_CREATED, actor_id="scrum_master", **retro)
        return retro


def _task_status_counts(backlog: Backlog) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in backlog.tasks.values():
        counts[t.status.value] = counts.get(t.status.value, 0) + 1
    return counts


def _json_safe(d: dict) -> dict:
    """Trim a report dict down to primitives before it rides along on an
    Event (which gets persisted as JSON) -- keeps event logs compact."""
    return {
        "project_id": d.get("project_id"),
        "sprint_id": d.get("sprint_id"),
        "task_counts": d.get("task_counts"),
    }


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
