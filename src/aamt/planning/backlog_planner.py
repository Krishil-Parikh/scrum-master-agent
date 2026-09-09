"""Turn a problem statement into a persisted backlog (phased plan §3.4).

Small/cheap models rarely honour a deep nested schema exactly, so this planner
is deliberately tolerant: it takes whatever JSON-ish structure comes back and
*normalises* it (key aliases, criteria shapes, title-based dependencies, missing
fields) before validating against :class:`BacklogPlan`. Three attempts:
structured-output → raw JSON with an example → one repair pass with the error.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import Settings, get_settings
from ..llm.provider import build_chat_model
from ..models.enums import BacklogItemKind, Priority
from ..models.project import Project
from ..models.task import AcceptanceCriterion, Task
from .schemas import BacklogPlan

_ROLES = {"backend", "frontend", "database", "ml", "qa", "devops"}
_ROLE_ALIASES = {
    "back-end": "backend", "back end": "backend", "api": "backend", "server": "backend",
    "front-end": "frontend", "front end": "frontend", "ui": "frontend", "client": "frontend",
    "db": "database", "data": "database", "sql": "database", "schema": "database",
    "ml/ai": "ml", "ai": "ml", "machine learning": "ml", "nlp": "ml",
    "test": "qa", "testing": "qa", "quality": "qa", "qa engineer": "qa",
    "ops": "devops", "ci": "devops", "infra": "devops", "infrastructure": "devops",
}
_PRIORITIES = {p.value for p in Priority}

_SYSTEM = """\
You are the Scrum Master decomposing a software problem into an Agile backlog.

Produce Epic -> Features -> Stories -> Tasks. Rules:
- Every Task is a concrete, single-engineer unit of work (a few hours).
- role is exactly one of: backend, frontend, database, ml, qa, devops.
- Give each Task 1-3 acceptance criteria as a JSON array of objects
  {"text": "...", "check": "<shell cmd that exits 0 iff satisfied, or null>"}.
- Wire dependencies with "depends_on": an array of the `ref` strings of tasks
  that must finish first — ONLY when a task literally cannot start without the
  other's output (schema before the API that queries it; an endpoint before the
  test that calls it). Do NOT chain everything off one task.
- Do NOT create a "set up project structure / scaffolding" task that everything
  else depends on. Each engineer creates the files their own task needs.
- Prefer a wide backlog (many independently-startable tasks) over a deep chain.
- Keep it lean. Estimates are 1-8 story points.

Return ONLY JSON of exactly this shape:
{
  "epic": "one line",
  "features": [
    {"title": "Feature name", "stories": [
      {"title": "Story name", "tasks": [
        {"ref": "t1", "title": "Task title", "description": "what to build",
         "role": "backend", "priority": "HIGH", "estimate": 3,
         "depends_on": [],
         "acceptance_criteria": [{"text": "GET /tasks returns 200", "check": null}]}
      ]}
    ]}
  ]
}
"""

_USER_TMPL = """\
# Problem statement
{problem}

# Constraints
language: {language}
framework: {framework}
testing: {testing}

# Whole-project acceptance criteria
{acceptance}

Return the backlog JSON now.
"""


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------
def _first(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _as_list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _norm_role(v: Any) -> str:
    s = str(v or "backend").strip().lower()
    if s in _ROLES:
        return s
    return _ROLE_ALIASES.get(s, "backend")


def _norm_priority(v: Any) -> str:
    s = str(v or "MEDIUM").strip().upper()
    return s if s in _PRIORITIES else "MEDIUM"


def _norm_estimate(v: Any) -> float:
    try:
        f = float(v)
        return f if f > 0 else 3.0
    except (TypeError, ValueError):
        return 3.0


def _norm_criteria(v: Any) -> list[dict]:
    out: list[dict] = []
    if isinstance(v, dict):
        if "criteria" in v or "acceptance_criteria" in v:
            return _norm_criteria(v.get("criteria") or v.get("acceptance_criteria"))
        text = _first(v, "text", "criterion", "description", "name")
        check = _first(v, "check", "command", "cmd")
        out.append({"text": str(text or check or "criterion"), "check": check})
        return out
    for item in _as_list(v):
        if isinstance(item, str):
            out.append({"text": item, "check": None})
        elif isinstance(item, dict):
            text = _first(item, "text", "criterion", "description", "name")
            check = _first(item, "check", "command", "cmd")
            out.append({"text": str(text or check or "criterion"), "check": check})
    return out or [{"text": "task is implemented and tested", "check": None}]


def _normalize(raw: Any) -> dict:
    """Coerce a loose model response into the strict BacklogPlan shape."""
    if isinstance(raw, str):
        raw = json.loads(_json_block(raw))
    if isinstance(raw, list):
        raw = {"features": raw}
    if not isinstance(raw, dict):
        raise ValueError(f"backlog is not an object: {type(raw)}")
    raw = raw.get("backlog", raw) if isinstance(raw.get("backlog"), dict) else raw

    epic = _first(raw, "epic", "epic_title", "title", "name", default="Project")
    if isinstance(epic, dict):
        epic = _first(epic, "title", "name", "text", default="Project")

    features_in = _as_list(_first(raw, "features", "feature", default=[]))

    counter = [0]
    norm_features: list[dict] = []
    title_to_ref: dict[str, str] = {}
    pending: list[tuple[dict, list[str]]] = []

    for f in features_in:
        f = f if isinstance(f, dict) else {"title": str(f)}
        stories_in = _as_list(_first(f, "stories", "story", default=[]))
        # some models put tasks directly under a feature
        if not stories_in and _first(f, "tasks", "task"):
            stories_in = [{"title": _first(f, "title", "feature", "name", default="Story"),
                           "tasks": _first(f, "tasks", "task")}]
        norm_stories: list[dict] = []
        for s in stories_in:
            s = s if isinstance(s, dict) else {"title": str(s)}
            tasks_in = _as_list(_first(s, "tasks", "task", default=[]))
            norm_tasks: list[dict] = []
            for t in tasks_in:
                t = t if isinstance(t, dict) else {"title": str(t)}
                counter[0] += 1
                ref = str(_first(t, "ref", "id", default=f"t{counter[0]}"))
                title = str(_first(t, "title", "task", "name", "summary", default=f"Task {ref}"))
                desc = str(_first(t, "description", "desc", "details", "body", default=title))
                nt = {
                    "ref": ref,
                    "title": title[:200],
                    "description": desc,
                    "role": _norm_role(_first(t, "role", "owner", "assignee")),
                    "priority": _norm_priority(_first(t, "priority", "prio")),
                    "estimate": _norm_estimate(_first(t, "estimate", "points", "effort", "size")),
                    "acceptance_criteria": _norm_criteria(
                        _first(t, "acceptance_criteria", "acceptance", "criteria", "ac")
                    ),
                    "depends_on": [],
                }
                deps_raw = [str(x) for x in _as_list(_first(t, "depends_on", "dependencies", "deps"))]
                norm_tasks.append(nt)
                pending.append((nt, deps_raw))
                title_to_ref[title.strip().lower()] = ref
                title_to_ref.setdefault(ref.lower(), ref)
            norm_stories.append({"title": str(_first(s, "title", "story", "name", default="Story")),
                                 "tasks": norm_tasks})
        norm_features.append({"title": str(_first(f, "title", "feature", "name", default="Feature")),
                              "stories": norm_stories})

    # resolve dependencies: accept refs or task titles
    for nt, deps_raw in pending:
        resolved: list[str] = []
        for d in deps_raw:
            key = d.strip().lower()
            ref = title_to_ref.get(key)
            if ref is None and re.fullmatch(r"t\d+", key):
                ref = key
            if ref and ref != nt["ref"] and ref not in resolved:
                resolved.append(ref)
        nt["depends_on"] = resolved

    return {"epic": str(epic), "features": norm_features}


def _json_block(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    return brace.group(1) if brace else text


# --------------------------------------------------------------------------
# planner
# --------------------------------------------------------------------------
class BacklogPlanner:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _model(self, **kw):
        return build_chat_model(
            model=self.settings.coordinator_model,
            settings=self.settings,
            max_tokens=max(self.settings.llm_max_tokens, 6000),
            **kw,
        )

    def generate(self, project: Project) -> BacklogPlan:
        user = _USER_TMPL.format(
            problem=project.problem_statement,
            language=project.constraints.language or "unspecified",
            framework=project.constraints.framework or "unspecified",
            testing=project.constraints.testing_requirements or "pytest",
            acceptance="\n".join(f"- {c}" for c in project.acceptance_criteria) or "- (none given)",
        )
        model = self._model()
        base_msgs = [("system", _SYSTEM), ("user", user)]
        errors: list[str] = []
        content = ""

        # 1) structured output (function calling)
        try:
            plan = model.with_structured_output(BacklogPlan).invoke(base_msgs)
            if isinstance(plan, BacklogPlan) and plan.all_tasks():
                return plan
            if isinstance(plan, dict):
                cand = BacklogPlan.model_validate(_normalize(plan))
                if cand.all_tasks():
                    return cand
        except Exception as exc:  # noqa: BLE001
            errors.append(f"structured: {exc}")

        # 2) raw JSON
        try:
            raw = model.invoke(base_msgs + [("user", "Output ONLY the JSON. No prose, no fences.")])
            content = raw.content if isinstance(raw.content, str) else str(raw.content)
            cand = BacklogPlan.model_validate(_normalize(content))
            if cand.all_tasks():
                return cand
            errors.append("raw: plan had no tasks")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"raw: {exc}")

        # 3) one repair pass — feed the bad output + the error back
        try:
            fix = model.invoke(
                base_msgs
                + [
                    ("user",
                     "Your previous attempt was invalid.\n"
                     f"--- your output ---\n{content[:4000]}\n--- end ---\n"
                     f"Error: {errors[-1]}\n"
                     "Return ONLY corrected JSON matching the exact shape in the "
                     "system message (keys: epic, features[].title, "
                     "features[].stories[].title, ...tasks[].{ref,title,description,"
                     "role,priority,estimate,depends_on,acceptance_criteria[]}). "
                     "No prose, no code fences."),
                ]
            )
            fixed = fix.content if isinstance(fix.content, str) else str(fix.content)
            cand = BacklogPlan.model_validate(_normalize(fixed))
            if cand.all_tasks():
                return cand
            errors.append("repair: plan had no tasks")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"repair: {exc}")

        raise RuntimeError("backlog planner failed:\n- " + "\n- ".join(errors))


def materialize_backlog(plan: BacklogPlan, *, project_id: str | None = None) -> list[Task]:
    """Flatten a :class:`BacklogPlan` into persisted-ready Task rows."""
    tasks: list[Task] = []

    epic = Task(kind=BacklogItemKind.EPIC, title=plan.epic or "Epic", description=plan.epic)
    tasks.append(epic)

    ref_to_id: dict[str, str] = {}
    planned_pairs: list[tuple[Task, list[str]]] = []

    for feature in plan.features:
        feat = Task(kind=BacklogItemKind.FEATURE, title=feature.title, parent_id=epic.id)
        tasks.append(feat)
        for story in feature.stories:
            st = Task(kind=BacklogItemKind.STORY, title=story.title, parent_id=feat.id)
            tasks.append(st)
            for pt in story.tasks:
                t = Task(
                    kind=BacklogItemKind.TASK,
                    title=pt.title,
                    description=pt.description,
                    parent_id=st.id,
                    role=pt.role,
                    priority=Priority(pt.priority),
                    estimate=float(pt.estimate or 0) or None,
                    labels=[f"role:{pt.role}"],
                    acceptance_criteria=[
                        AcceptanceCriterion(text=c.text, check=c.check)
                        for c in pt.acceptance_criteria
                    ],
                )
                tasks.append(t)
                ref_to_id[pt.ref] = t.id
                planned_pairs.append((t, pt.depends_on))

    for t, deps in planned_pairs:
        for ref in deps:
            dep_id = ref_to_id.get(ref)
            if dep_id and dep_id != t.id:
                t.dependencies.append(dep_id)

    return tasks
