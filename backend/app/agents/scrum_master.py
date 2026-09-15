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
from app.llm.prompts import truncate
from app.schemas.agent import AgentSpecialty
from app.schemas.project import ProjectContext
from app.schemas.task import Backlog, Epic, Sprint, Task, TaskRisk, TaskStatus, UserStory
from app.utils.ids import new_id

logger = logging.getLogger("ai_dev_pod.agents.scrum_master")

_VALID_SPECIALTIES = {s.value for s in DEVELOPER_SPECIALTIES}


class ScrumMasterAgent(BaseAgent):
    def __init__(self):
        super().__init__(PROFILES[AgentSpecialty.SCRUM_MASTER])

    # ---- Phase 7: Agile planning ----------------------------------------

    async def generate_backlog(self, context: ProjectContext, sme_context: str = "") -> Backlog:
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

Break this project into Epics -> User Stories -> Tasks. Every task MUST be assigned a "specialty" from exactly this set: frontend, backend, ai_ml, devops, mlops, database.

Decide for yourself which of those six specialties this specific project actually needs -- do not invent filler work for a specialty just to keep it represented. A small CRUD app might genuinely only need frontend, backend, and database; it does not need an ai_ml or mlops task just because those roles exist on the pod. Only include devops, ai_ml, or mlops tasks when the requirements actually call for them (e.g. no AI/ML task unless the project has an AI-powered feature; no dedicated devops task unless deployment/CI is in scope beyond what backend already covers). Specialties with no real work this project needs should simply have zero tasks -- the pod will have those developers help wherever the work actually is instead.

Return a JSON object:
{{
  "epics": [
    {{
      "title": "...",
      "description": "...",
      "stories": [
        {{
          "title": "...",
          "as_a": "user",
          "i_want": "...",
          "so_that": "...",
          "acceptance_criteria": ["..."],
          "tasks": [
            {{
              "title": "...",
              "description": "...",
              "specialty": "frontend|backend|ai_ml|devops|mlops|database",
              "risk": "low|medium|high",
              "acceptance_criteria": ["..."],
              "depends_on_task_titles": ["exact title of another task in this same response, if any"]
            }}
          ]
        }}
      ]
    }}
  ]
}}

Produce 3-5 epics covering the full project, sized to what the project actually needs -- keep task titles short and unique across the whole backlog so dependencies can reference them unambiguously. Aim for roughly 10-25 tasks total depending on real scope, not a fixed count.
""".strip()
        # This is the single largest structured-output call in the whole
        # pipeline (up to ~25 tasks nested in stories/epics) -- give it a
        # generous token budget so the JSON doesn't get cut off mid-object,
        # which would otherwise fail to parse at all rather than degrading.
        raw = await self._llm_json(context.name, prompt, max_tokens=5000)
        return _parse_backlog(raw)

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


def _parse_backlog(raw: dict) -> Backlog:
    backlog = Backlog()
    title_to_id: dict[str, str] = {}
    pending_deps: list[tuple[Task, list[str]]] = []

    epics = raw.get("epics", []) if isinstance(raw, dict) else []
    for epic_raw in epics:
        epic_id = new_id("epic")
        epic = Epic(epic_id=epic_id, title=epic_raw.get("title", "Untitled Epic"), description=epic_raw.get("description", ""))
        for story_raw in epic_raw.get("stories", []):
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
            for task_raw in story_raw.get("tasks", []):
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
