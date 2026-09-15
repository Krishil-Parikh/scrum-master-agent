"""
Scrum Master / Pod Lead Agent (PRD §6.3; Roadmap Phase 2).

Unlike the six developer agents, the Scrum Master never produces source
code. Its job is coordination: turning requirements into a backlog,
allocating tasks, running ceremonies, and consolidating cross-agent
information (standups, retrospectives) into one narrative.
"""

from __future__ import annotations

import logging

from app.agents.base import BaseAgent
from app.agents.profiles import DEVELOPER_SPECIALTIES, PROFILES
from app.schemas.agent import AgentSpecialty
from app.schemas.project import ProjectContext
from app.schemas.task import Backlog, Epic, Sprint, Task, TaskRisk, TaskStatus, UserStory
from app.utils.ids import new_id

logger = logging.getLogger("ai_dev_pod.agents.scrum_master")

_VALID_SPECIALTIES = {s.value for s in DEVELOPER_SPECIALTIES}


class ScrumMasterAgent(BaseAgent):
    def __init__(self):
        super().__init__(PROFILES[AgentSpecialty.SCRUM_MASTER])

    # ---- Phase 7: Agile planning (hierarchical -- scaling roadmap #2) ----
    #
    # Backlog generation used to be one mega LLM call asking for the entire
    # Epic -> Story -> Task tree at once (up to ~25 tasks nested three deep
    # in one JSON response). That's a known failure mode for large
    # structured output: past a certain size the JSON silently truncates
    # mid-array, and the caller has no way to tell "the model stopped
    # early" from "the model decided this project only needs 6 tasks."
    # Splitting into "epics first, then stories+tasks per epic in parallel"
    # keeps every individual call small regardless of total project size --
    # 10 epics means 10 small calls (fanned out the same way independent
    # analysis already does), not one call trying to hold everything.

    async def generate_epics(self, context: ProjectContext, sme_context: str = "") -> list[dict]:
        """Step 1 of 2: just the top-level breakdown, no stories/tasks yet."""
        requirements_text = "\n".join(f"- [{r.kind}] {r.text}" for r in context.requirements)
        decisions_text = "\n".join(f"- {d.decision}" for d in context.decisions)
        prompt = f"""
Project: {context.name}
Objective: {context.objective}
Business context: {context.business_context}

Requirements:
{requirements_text or "(none captured)"}

Confirmed decisions from SME clarification:
{decisions_text or "(none yet)"}
{sme_context}

Break this project into 3-6 Epics -- the top-level chunks of work only, not individual stories or tasks yet.

Decide for yourself which specialties (frontend, backend, ai_ml, devops, mlops, database) this project actually needs -- do not shape an epic around a specialty just to keep it represented. A small CRUD app might genuinely only need frontend, backend, and database epics.

Return a JSON object:
{{"epics": [{{"title": "...", "description": "1-2 sentences on what this epic covers"}}]}}
""".strip()
        raw = await self._llm_json(context.name, prompt, max_tokens=800)
        epics = raw.get("epics", []) if isinstance(raw, dict) else []
        return [e for e in epics if isinstance(e, dict) and e.get("title")]

    async def generate_stories_and_tasks_for_epic(self, context: ProjectContext, epic: dict, sme_context: str = "") -> dict:
        """Step 2 of 2: fill in ONE epic's stories and tasks. Called once
        per epic, in parallel (see the orchestrator's agile-planning
        phase), so each call stays small no matter how many epics there
        are in total."""
        requirements_text = "\n".join(f"- [{r.kind}] {r.text}" for r in context.requirements)
        prompt = f"""
Project: {context.name}
Objective: {context.objective}

Requirements:
{requirements_text or "(none captured)"}
{sme_context}

Epic: {epic.get('title', 'Untitled Epic')}
{epic.get('description', '')}

Break this ONE epic into User Stories, each broken into technical Tasks. Every task MUST be assigned a "specialty" from exactly this set: frontend, backend, ai_ml, devops, mlops, database -- only a specialty this epic genuinely needs, don't invent filler tasks to represent one that isn't relevant here.

Return a JSON object:
{{
  "stories": [
    {{
      "title": "...", "as_a": "user", "i_want": "...", "so_that": "...",
      "acceptance_criteria": ["..."],
      "tasks": [
        {{
          "title": "...", "description": "...",
          "specialty": "frontend|backend|ai_ml|devops|mlops|database",
          "risk": "low|medium|high",
          "acceptance_criteria": ["..."],
          "depends_on_task_titles": ["exact title of another task -- from this epic or a different one -- if any"]
        }}
      ]
    }}
  ]
}}
Keep task titles short and globally unique across the whole project (another epic's task may need to reference yours as a dependency, and vice versa). Aim for 2-5 stories for this one epic, sized to what it actually needs.
""".strip()
        try:
            raw = await self._llm_json(context.name, prompt, max_tokens=2200)
            return raw if isinstance(raw, dict) else {"stories": []}
        except Exception:
            logger.exception("generate_stories_and_tasks_for_epic failed for epic %r", epic.get("title"))
            return {"stories": []}

    def assemble_backlog(self, epics_raw: list[dict], epic_results: list[dict]) -> Backlog:
        """Combine per-epic story/task JSON (generated independently, in
        parallel) into one Backlog, resolving dependency references
        globally at the end -- a task in epic 3 can legitimately depend on
        a task title from epic 1, so title->id resolution has to happen
        after every epic's results are in, not per-epic."""
        backlog = Backlog()
        title_to_id: dict[str, str] = {}
        pending_deps: list[tuple[Task, list[str]]] = []

        for epic_raw, epic_result in zip(epics_raw, epic_results):
            epic_id = new_id("epic")
            epic = Epic(epic_id=epic_id, title=epic_raw.get("title", "Untitled Epic"), description=epic_raw.get("description", ""))
            for story_raw in (epic_result.get("stories") or []):
                if not isinstance(story_raw, dict):
                    continue
                story_id = new_id("story")
                story = UserStory(
                    story_id=story_id,
                    epic_id=epic_id,
                    title=story_raw.get("title", "Untitled Story"),
                    as_a=story_raw.get("as_a", "user"),
                    i_want=story_raw.get("i_want", ""),
                    so_that=story_raw.get("so_that", ""),
                    acceptance_criteria=story_raw.get("acceptance_criteria", []) or [],
                )
                for task_raw in (story_raw.get("tasks") or []):
                    if not isinstance(task_raw, dict):
                        continue
                    specialty_raw = str(task_raw.get("specialty", "")).strip().lower()
                    if specialty_raw not in _VALID_SPECIALTIES:
                        specialty_raw = "backend"  # safe default rather than dropping the task
                    risk_raw = str(task_raw.get("risk", "low")).strip().lower()
                    if risk_raw not in ("low", "medium", "high"):
                        risk_raw = "low"
                    task = Task(
                        task_id=new_id("task"),
                        story_id=story_id,
                        title=task_raw.get("title", "Untitled Task"),
                        description=task_raw.get("description", ""),
                        specialty=AgentSpecialty(specialty_raw),
                        risk=TaskRisk(risk_raw),
                        acceptance_criteria=task_raw.get("acceptance_criteria", []) or [],
                    )
                    title_to_id[task.title] = task.task_id
                    pending_deps.append((task, task_raw.get("depends_on_task_titles", []) or []))
                    backlog.tasks[task.task_id] = task
                    story.task_ids.append(task.task_id)
                backlog.stories[story_id] = story
                epic.story_ids.append(story_id)
            backlog.epics[epic_id] = epic

        for task, dep_titles in pending_deps:
            task.depends_on = [title_to_id[t] for t in dep_titles if t in title_to_id and title_to_id[t] != task.task_id]

        return backlog

    # ---- Phase 8: task allocation -----------------------------------------

    def allocate_tasks(self, backlog: Backlog) -> Backlog:
        """Deterministic allocation: specialty match decides the agent (the
        pod has exactly one agent per specialty in the MVP, so this is a
        direct mapping); a task becomes READY once every dependency it
        lists is COMPLETED. No LLM call needed -- this is exactly the kind
        of mechanical decision that shouldn't cost a model call."""
        title_to_id = {t.title: t.task_id for t in backlog.tasks.values()}
        for task in backlog.tasks.values():
            task.assigned_agent_id = task.specialty.value
            task.branch = PROFILES[task.specialty].branch
            deps_satisfied = all(
                backlog.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
                if dep_id in backlog.tasks
            )
            if task.status == TaskStatus.BACKLOG and deps_satisfied:
                task.status = TaskStatus.READY
                task.touch()
        return backlog

    def needed_specialties(self, backlog: Backlog) -> set[str]:
        """Which specialties this project actually has work for -- computed
        from the backlog the LLM produced, not assumed. Roadmap Phase 8
        + the user's ask: decide up front which roles are critical instead
        of forcing every specialty to be represented."""
        return {t.specialty.value for t in backlog.tasks.values()}

    def request_work(self, backlog: Backlog, requester) -> Task | None:
        """Pull-based allocation (PRD §6.4 "developers ask their mentors
        for work" rather than being handed it; Roadmap Phase 8 dynamic
        reassignment / Phase 19 Test 5 cross-specialty assistance).

        A developer calls this instead of being pushed a task. Their own
        specialty's READY queue is served first. If their specialty simply
        has no work anywhere in this backlog (or has already finished all
        of it) they pivot to helping wherever the READY queue is currently
        biggest, after loading that specialty's skill -- this is what makes
        an unneeded role (e.g. MLOps on a small CRUD app) contribute instead
        of sitting idle, without forcing filler work onto their own branch.
        Callers are expected to serialize calls to this (e.g. one shared
        lock) since it mutates the backlog."""
        own = requester.profile.specialty.value
        own_ready = [t for t in backlog.tasks.values() if t.status == TaskStatus.READY and t.specialty.value == own]
        if own_ready:
            task = own_ready[0]
            task.assigned_agent_id = requester.agent_id
            return task

        own_pending = any(
            t.specialty.value == own and t.status in (TaskStatus.BACKLOG, TaskStatus.IN_PROGRESS)
            for t in backlog.tasks.values()
        )
        if own_pending:
            return None  # own work exists but is waiting on a dependency -- don't poach, just wait

        by_specialty: dict[str, list[Task]] = {}
        for t in backlog.tasks.values():
            if t.status == TaskStatus.READY:
                by_specialty.setdefault(t.specialty.value, []).append(t)
        if not by_specialty:
            return None

        busiest = max(by_specialty, key=lambda s: len(by_specialty[s]))
        task = by_specialty[busiest][0]
        task.assigned_agent_id = requester.agent_id
        return task

    def create_sprint(self, backlog: Backlog, *, name: str = "Sprint 1", goal: str = "", days: int = 14) -> Sprint:
        ready_task_ids = [t.task_id for t in backlog.tasks.values() if t.status in (TaskStatus.READY, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.REVIEW, TaskStatus.COMPLETED)]
        story_ids = sorted({backlog.tasks[tid].story_id for tid in ready_task_ids})
        sprint = Sprint(
            sprint_id=new_id("sprint"),
            name=name,
            goal=goal or "Deliver the first vertical slice of the project across every specialty.",
            story_ids=story_ids,
            task_ids=ready_task_ids,
            days=days,
            status="active",
        )
        backlog.sprints[sprint.sprint_id] = sprint
        backlog.current_sprint_id = sprint.sprint_id
        return sprint

    # ---- Phase 15: ceremonies --------------------------------------------

    def summarize_standup(self, reports: dict[str, dict]) -> tuple[str, list[str]]:
        blockers = [
            f"{PROFILES[AgentSpecialty(aid)].display_name}: {r['blockers']}"
            for aid, r in reports.items()
            if r.get("blockers") and r["blockers"].strip().lower() not in ("none", "none.", "-", "")
        ]
        if blockers:
            summary = "Blockers reported: " + "; ".join(blockers)
        else:
            summary = "No blockers reported. Team is on track."
        return summary, blockers

    async def sprint_review_summary(self, context: ProjectContext, backlog: Backlog, sprint: Sprint) -> str:
        completed = [backlog.tasks[t] for t in sprint.task_ids if backlog.tasks[t].status == TaskStatus.COMPLETED]
        pending = [backlog.tasks[t] for t in sprint.task_ids if backlog.tasks[t].status != TaskStatus.COMPLETED]
        prompt = f"""
Sprint: {sprint.name} — Goal: {sprint.goal}

Completed tasks:
{chr(10).join(f"- {t.title} ({t.specialty.value})" for t in completed) or "(none)"}

Not completed:
{chr(10).join(f"- {t.title} ({t.specialty.value}, status={t.status.value})" for t in pending) or "(none)"}

Write a concise sprint review summary (3-5 sentences) for the Business SME/Product Owner: what shipped, whether the sprint goal was met, and what's left.
""".strip()
        try:
            return await self._llm_text(context.name, prompt)
        except Exception:
            logger.exception("sprint_review_summary failed")
            return f"{len(completed)}/{len(sprint.task_ids)} tasks completed this sprint."

    def synthesize_retrospective(self, inputs: list[dict]) -> dict:
        """Mechanical aggregation (dedupe + cap) rather than another LLM
        call -- combining short lists the agents already produced doesn't
        need model reasoning, and keeping this cheap matters when running
        on a metered model."""

        def _dedupe(items: list[str], limit: int = 8) -> list[str]:
            seen: list[str] = []
            for item in items:
                norm = item.strip()
                if norm and norm not in seen:
                    seen.append(norm)
            return seen[:limit]

        went_well = _dedupe([w for i in inputs for w in i.get("went_well", [])])
        went_wrong = _dedupe([w for i in inputs for w in i.get("went_wrong", [])])
        action_items = _dedupe([a for i in inputs for a in i.get("action_items", [])])
        return {"went_well": went_well, "went_wrong": went_wrong, "action_items": action_items}
