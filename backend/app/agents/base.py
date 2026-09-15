"""
BaseAgent (PRD §6.4, §32; Roadmap Phase 2):

    Agent
    ├── identity
    ├── role
    ├── specialty
    ├── system_prompt
    ├── skills
    ├── memory
    ├── tools
    ├── state
    └── communication

Every developer agent and the Scrum Master subclass this. The generic LLM
behaviors that are identical in *shape* across specialties (independent
requirement analysis, implementing a task, reviewing a diff, a stand-up
report, retrospective input) live here, parameterized by the agent's
AgentProfile; specialty-specific nuance comes from the profile's prompt
text and each subclass's small overrides, not from duplicated logic.
"""

from __future__ import annotations

import logging

from app.agents.profiles import AgentProfile
from app.communication.event_bus import get_event_bus
from app.llm.openrouter_client import get_llm_client
from app.llm.prompts import JSON_ONLY_INSTRUCTION, build_system_prompt, truncate
from app.schemas.agent import AgentIdentity, AgentState, AgentStatus
from app.schemas.communication import Message, MessageChannel
from app.schemas.event import EventType
from app.schemas.project import ProjectContext
from app.schemas.task import Task
from app.skills.loader import Skill, get_skill_loader

logger = logging.getLogger("ai_dev_pod.agents")


class BaseAgent:
    def __init__(self, profile: AgentProfile):
        self.profile = profile
        self.identity = AgentIdentity(
            agent_id=profile.agent_id,
            display_name=profile.display_name,
            specialty=profile.specialty,
            branch=profile.branch,
            color=profile.color,
            avatar_initials=profile.avatar_initials,
        )
        self.status = AgentStatus(agent_id=profile.agent_id)
        self.llm = get_llm_client()
        self.skills = get_skill_loader()
        self.bus = get_event_bus()

    # ---- identity / state -------------------------------------------------

    @property
    def agent_id(self) -> str:
        return self.identity.agent_id

    async def set_state(self, state: AgentState, note: str = "") -> None:
        self.status.state = state
        self.status.note = note
        self.status.touch()
        await self.bus.emit(
            EventType.AGENT_STATE_CHANGED,
            actor_id=self.agent_id,
            state=state.value,
            note=note,
        )

    def system_prompt(self, project_name: str, *, extra_context: str = "") -> str:
        return build_system_prompt(
            role_title=self.profile.role_title,
            specialty_description=self.profile.specialty_description,
            project_name=project_name,
            responsibilities=self.profile.responsibilities,
            extra_context=extra_context,
        )

    # ---- communication ------------------------------------------------

    async def say(
        self,
        channel: MessageChannel,
        text: str,
        *,
        mentions: list[str] | None = None,
        sender_role: str | None = None,
    ) -> Message:
        message = Message(
            channel=channel,
            sender_id=self.agent_id,
            sender_name=self.identity.display_name,
            sender_role=sender_role or ("Scrum" if self.profile.specialty.value == "scrum_master" else "Developer"),
            text=text,
            mentions=mentions or [],
        )
        from app.memory.project_memory import get_current_project_id, get_project_memory

        if get_current_project_id():
            get_project_memory().append_message(message)
        await self.bus.emit(
            EventType.MESSAGE_POSTED,
            actor_id=self.agent_id,
            channel=channel.value,
            text=text,
            message_id=message.message_id,
            sender_name=message.sender_name,
            sender_role=message.sender_role,
            color=self.identity.color,
            avatar_initials=self.identity.avatar_initials,
            mentions=message.mentions,
        )
        return message

    # ---- skills -------------------------------------------------------

    async def load_skill(self, skill_name: str, *, reason: str = "") -> Skill | None:
        skill = self.skills.load_for_agent(self.agent_id, skill_name)
        if skill and skill_name != self.profile.specialty.value:
            await self.set_state(AgentState.HELPING, note=f"Loaded {skill_name} skill")
            text = f"Loading the **{skill_name}** skill" + (f" — {reason}" if reason else "") + "."
            await self.say(MessageChannel.SYSTEM, text)
        return skill

    def primary_skill_body(self) -> str:
        skill = self.skills.get(self.profile.specialty.value)
        return skill.body if skill else ""

    # ---- LLM helpers ----------------------------------------------------

    async def _llm_text(self, project_name: str, user_prompt: str, *, extra_context: str = "") -> str:
        messages = [
            {"role": "system", "content": self.system_prompt(project_name, extra_context=extra_context)},
            {"role": "user", "content": user_prompt},
        ]
        return await self.llm.chat(messages)

    async def _llm_json(
        self, project_name: str, user_prompt: str, *, extra_context: str = "", max_tokens: int | None = None
    ):
        messages = [
            {
                "role": "system",
                "content": self.system_prompt(project_name, extra_context=extra_context) + "\n\n" + JSON_ONLY_INSTRUCTION,
            },
            {"role": "user", "content": user_prompt},
        ]
        return await self.llm.chat_json(messages, max_tokens=max_tokens)

    # ---- Phase 5: independent requirement analysis ------------------------

    async def analyze_requirements(self, context: ProjectContext) -> dict:
        await self.set_state(AgentState.ANALYZING)
        focus = ", ".join(self.profile.analysis_focus)
        prompt = f"""
Project objective: {context.objective}
Business context: {context.business_context}

Requirements:
{chr(10).join(f"- [{r.kind}] {r.text}" for r in context.requirements) or "(none captured yet)"}

Constraints:
{chr(10).join(f"- {c}" for c in context.constraints) or "(none)"}

As {self.profile.role_title}, independently analyze this project through the lens of: {focus}.

Return a JSON object with exactly these keys:
{{
  "summary": "2-4 sentence summary of what this means for your specialty",
  "key_considerations": ["short bullet", "..."],
  "questions": [
    {{"text": "a specific question for the Business SME", "reason": "why this is ambiguous", "priority": "low|medium|high"}}
  ]
}}
Only include a question if the requirements are genuinely ambiguous or missing information a competent {self.profile.role_title} would need before starting. Do not invent questions for things already answered above.
""".strip()
        try:
            result = await self._llm_json(context.name, prompt)
        except Exception:
            logger.exception("%s: analyze_requirements failed", self.agent_id)
            result = {"summary": "(analysis failed)", "key_considerations": [], "questions": []}
        await self.set_state(AgentState.IDLE)
        return result

    # ---- Repo retrieval before implementing (scaling roadmap #1) ---------

    async def plan_context_requests(self, context: ProjectContext, task: Task, *, tree: list[str]) -> dict:
        """Ask the agent what it actually needs to look at in the existing
        codebase before implementing this task, instead of the orchestrator
        guessing 1-2 dependency files to truncate and hand over blind. This
        is deliberately a cheap, small, single JSON call rather than a full
        multi-turn tool-calling loop (OpenRouter's cheap models are shaky at
        sustained tool use) -- the agent gets one shot to say what it wants
        to see, the orchestrator resolves it, then implement_task runs with
        real answers instead of orchestrator-picked snippets."""
        if not tree:
            return {"read_files": [], "grep": [], "search_symbols": []}
        tree_listing = "\n".join(tree[:150])
        prompt = f"""
Task you're about to implement: {task.title}
{task.description}

Here is everything that currently exists in this codebase (file tree):
{tree_listing}

Before you write any code, say what you need to look at to avoid duplicating existing code, breaking an existing contract, or missing a naming convention already in use. Return a JSON object:
{{
  "read_files": ["exact paths from the tree above you want the full content of, at most 5"],
  "grep": ["short search terms for things that might exist elsewhere, e.g. a function or endpoint name, at most 3"],
  "search_symbols": ["short name fragments to look up as functions/classes/routes, at most 3"]
}}
If the tree is empty or this task is clearly self-contained and unrelated to anything listed, return empty lists -- don't invent lookups you don't need.
""".strip()
        try:
            result = await self._llm_json(context.name, prompt, max_tokens=400)
            if not isinstance(result, dict):
                return {"read_files": [], "grep": [], "search_symbols": []}
            return {
                "read_files": [str(p) for p in (result.get("read_files") or [])][:5],
                "grep": [str(p) for p in (result.get("grep") or [])][:3],
                "search_symbols": [str(p) for p in (result.get("search_symbols") or [])][:3],
            }
        except Exception:
            logger.exception("%s: plan_context_requests failed for %s", self.agent_id, task.task_id)
            return {"read_files": [], "grep": [], "search_symbols": []}

    # ---- Phase 13/14: implement a task ---------------------------------

    async def implement_task(
        self, context: ProjectContext, task: Task, *, extra_context: str = "", skill_body: str = ""
    ) -> dict:
        await self.set_state(AgentState.WORKING, note=f"Working on {task.title}")
        skill_section = f"\n\nRelevant skill guidance:\n{truncate(skill_body, 2500)}" if skill_body else ""
        prompt = f"""
Project: {context.name}
Objective: {context.objective}
Technology stack: {", ".join(context.technology_stack) or "not yet specified -- choose something simple and conventional"}

Task: {task.title}
Description: {task.description}
Acceptance criteria:
{chr(10).join(f"- {c}" for c in task.acceptance_criteria) or "(none specified -- use your judgment)"}

Guidance for this specialty's output: {self.profile.artifact_guidance}
{skill_section}
{extra_context}

Implement this task. Return a JSON object with exactly these keys:
{{
  "files": {{"relative/path/to/file.ext": "full file content as a string", "...": "..."}},
  "summary": "1-3 sentences describing what you implemented and why",
  "tests_note": "what you tested or what should be tested, if you didn't include a test file"
}}
Keep the change focused and minimal -- only the files this task actually needs. Use realistic, runnable code, not pseudocode. File paths should be relative (e.g. "src/routes/tasks.py"), no leading slash.
""".strip()
        try:
            result = await self._llm_json(context.name, prompt, max_tokens=3200)
            if not isinstance(result, dict) or "files" not in result:
                raise ValueError(f"Malformed implement_task response: {result!r}")
        except Exception:
            logger.exception("%s: implement_task failed for %s", self.agent_id, task.task_id)
            await self.set_state(AgentState.BLOCKED, note="Implementation failed")
            return {"files": {}, "summary": "Implementation failed.", "tests_note": "", "error": True}
        await self.set_state(AgentState.REVIEWING, note=f"Self-review: {task.title}")
        return result

    # ---- Phase 14: review another agent's diff -------------------------

    async def review_files(self, context: ProjectContext, task: Task, files: dict[str, str]) -> dict:
        files_text = "\n\n".join(f"--- {path} ---\n{truncate(content, 3000)}" for path, content in files.items())
        prompt = f"""
Review this implementation for the task "{task.title}" ({task.description}).

{files_text or "(no files were produced)"}

Return a JSON object:
{{
  "approved": true|false,
  "findings": [{{"severity": "P0|P1|P2|P3|NIT", "summary": "concrete issue", "file": "path or null"}}]
}}
Approve (true) unless there is a real P0/P1 problem (broken logic, an obvious security hole, or the acceptance criteria are clearly unmet). Don't invent findings to look thorough -- an empty findings list with approved:true is a valid, common outcome for a good diff.
""".strip()
        try:
            result = await self._llm_json(context.name, prompt)
            if not isinstance(result, dict):
                raise ValueError("Malformed review response")
        except Exception:
            logger.exception("%s: review_files failed for %s", self.agent_id, task.task_id)
            result = {"approved": True, "findings": [], "review_error": True}
        return result

    # ---- Phase 15: ceremonies -------------------------------------------

    async def standup_report(self, context: ProjectContext, recent_summary: str) -> dict:
        prompt = f"""
Recent activity for you ({self.profile.display_name}):
{recent_summary or "(no recorded activity yet)"}

Write your daily stand-up update. Return JSON:
{{"yesterday": "...", "today": "...", "blockers": "None, or a specific blocker", "dependencies": "None, or what you need from whom"}}
Keep each field to one short sentence, written the way a real engineer would say it out loud, not a status-report tone.
""".strip()
        try:
            return await self._llm_json(context.name, prompt)
        except Exception:
            logger.exception("%s: standup_report failed", self.agent_id)
            return {"yesterday": "—", "today": "—", "blockers": "None", "dependencies": "None"}

    # ---- Phase 12: merge conflict resolution -----------------------------

    async def resolve_conflict(
        self,
        context: ProjectContext,
        *,
        file_path: str,
        my_version: str,
        other_agent_name: str,
        other_version: str,
        my_task: Task,
    ) -> dict:
        """Resolve a Git merge conflict on one file by understanding both
        sides' intent (PRD §22) rather than blindly picking "ours" or
        "theirs". Called on the agent whose branch is receiving the merge."""
        await self.set_state(AgentState.RESOLVING_CONFLICT, note=f"Conflict in {file_path}")
        await self.say(
            MessageChannel.GIT,
            f"Merge conflict in `{file_path}` while syncing with **{other_agent_name}**. "
            f"Reconciling both changes based on intent rather than picking one side.",
        )
        prompt = f"""
You are merging {other_agent_name}'s branch into yours and hit a conflict in `{file_path}`.

Your current task: {my_task.title} — {my_task.description}

--- YOUR version of {file_path} ---
{truncate(my_version, 4000)}

--- {other_agent_name}'s version of {file_path} ---
{truncate(other_version, 4000)}

Both changes may be needed. Produce ONE final merged version of this file that preserves the intent of both sides wherever possible. If the two versions are genuinely incompatible, prefer correctness and note the tradeoff.

Return JSON:
{{"resolved_content": "the full final file content as a string", "explanation": "1-2 sentences on how you reconciled the two versions"}}
""".strip()
        try:
            result = await self._llm_json(context.name, prompt, max_tokens=2600)
            if not isinstance(result, dict) or "resolved_content" not in result:
                raise ValueError("Malformed conflict resolution response")
        except Exception:
            logger.exception("%s: resolve_conflict failed for %s", self.agent_id, file_path)
            # Fail safe to "ours" rather than losing the merge entirely -- an
            # imperfect but explicit outcome, logged as such.
            result = {
                "resolved_content": my_version,
                "explanation": "Automatic resolution failed; kept my version and flagged for human review.",
                "error": True,
            }
        await self.say(MessageChannel.GIT, f"Conflict resolved in `{file_path}`: {result.get('explanation', '')}")
        await self.set_state(AgentState.WORKING)
        return result

    async def retro_input(self, context: ProjectContext, sprint_summary: str) -> dict:
        prompt = f"""
Sprint summary:
{sprint_summary}

As {self.profile.display_name}, give your honest retrospective input. Return JSON:
{{"went_well": ["..."], "went_wrong": ["..."], "action_items": ["a concrete, assignable next step"]}}
Be specific and grounded in what actually happened this sprint -- generic answers like "communication could be better" without a concrete cause are not useful.
""".strip()
        try:
            return await self._llm_json(context.name, prompt)
        except Exception:
            logger.exception("%s: retro_input failed", self.agent_id)
            return {"went_well": [], "went_wrong": [], "action_items": []}
