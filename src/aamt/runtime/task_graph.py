"""The single-task execution loop as a LangGraph state machine (phased plan §1.4).

    prepare -> develop -> (blocked/error?) --------------------> escalate
                   |                                                ^
                   v                                                |
                 verify -- pass --> commit --> DONE                 |
                   |                                                |
                   `-- fail & attempts left --> develop            |
                   `-- fail & no attempts ------------------------> escalate

The developer agent runs its own inner ReAct loop (analyze/implement/test/fix);
this outer graph is the part that does **not** trust the agent — it re-runs the
verification gate itself and only commits on an objective PASS.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ..config import Settings, get_settings
from ..models.enums import TaskStatus
from ..models.event import EventType
from ..models.task import Task
from ..tools.workspace import Workspace
from ..agents.developer import DeveloperAgent
from .verification import verify_task


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------
class TaskRunState(TypedDict, total=False):
    task: dict[str, Any]
    agent_role: str
    workspace_root: str
    project_summary: str
    project_id: str | None
    sprint_id: str | None

    attempt: int
    max_attempts: int
    base_commit: str | None
    branch: str

    agent_summary: str
    agent_error: str | None
    last_feedback: str
    verification: dict[str, Any] | None
    commit_hash: str | None
    outcome: str
    _next: str

    log: Annotated[list[str], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]


@dataclass
class TaskRunResult:
    task: Task
    outcome: str                      # done | blocked | escalated | error
    attempts: int
    branch: str | None = None
    commit_hash: str | None = None
    agent_summary: str = ""
    agent_error: str | None = None
    verification_render: str = ""
    log: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.outcome == "done"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _conventional_type(task: Task) -> str:
    t = f"{task.title} {task.description}".lower()
    if any(w in t for w in ("test", "coverage", "pytest")):
        return "test"
    if any(w in t for w in ("fix", "bug", "regression")):
        return "fix"
    if any(w in t for w in ("refactor", "cleanup", "rename")):
        return "refactor"
    if any(w in t for w in ("doc", "readme", "comment")):
        return "docs"
    return "feat"


def _advance_to(task: Task, target: TaskStatus, *, actor: str, note: str = "") -> None:
    """Walk the task state machine toward ``target`` along allowed edges."""
    task.advance_to(target, actor=actor, note=note or None)


def _mk_workspace(state: TaskRunState, settings: Settings) -> Workspace:
    return Workspace(
        state["workspace_root"],
        allow_network=settings.allow_network_in_shell,
        default_timeout=settings.agent_timeout_seconds,
    )


# --------------------------------------------------------------------------
# nodes
# --------------------------------------------------------------------------
def _make_nodes(settings: Settings):
    def prepare(state: TaskRunState) -> dict[str, Any]:
        task = Task.model_validate(state["task"])
        ws = _mk_workspace(state, settings)
        ws.ensure_git_repo()
        base = ws.last_commit_hash()
        branch = f"{settings.branch_prefix}{task.id}"
        res = ws.create_branch(branch)
        on_branch = ws.current_branch() if res.ok else ws.current_branch()

        _advance_to(task, TaskStatus.IN_PROGRESS, actor=state["agent_role"], note="task started")
        task.branch = branch
        task.sprint_id = state.get("sprint_id")

        return {
            "task": task.model_dump(),
            "attempt": 1,
            "max_attempts": state.get("max_attempts", settings.max_task_retries),
            "base_commit": base,
            "branch": branch,
            "outcome": "",
            "last_feedback": "",
            "log": [f"prepare: branch={branch} (on {on_branch}) base={base or 'EMPTY'}"],
            "events": [
                {"type": EventType.TASK_STARTED.value,
                 "payload": {"task_id": task.id, "role": state["agent_role"], "branch": branch}}
            ],
        }

    def develop(state: TaskRunState) -> dict[str, Any]:
        task = Task.model_validate(state["task"])
        ws = _mk_workspace(state, settings)
        attempt = state.get("attempt", 1)

        agent = DeveloperAgent(state["agent_role"], settings=settings)
        res = agent.implement(
            task,
            ws,
            project_summary=state.get("project_summary", ""),
            extra_context=state.get("last_feedback", ""),
        )

        events: list[dict[str, Any]] = [
            {"type": EventType.AGENT_PROGRESS_REPORTED.value,
             "payload": {"task_id": task.id, "attempt": attempt,
                         "steps": res.steps, "tools": res.tool_calls}}
        ]

        if not res.ok:
            max_attempts = state.get("max_attempts", settings.max_task_retries)
            failed_ev = events + [
                {"type": EventType.AGENT_FAILED.value,
                 "payload": {"task_id": task.id, "attempt": attempt, "error": res.error}}
            ]
            if attempt < max_attempts:
                return {
                    "agent_error": res.error,
                    "attempt": attempt + 1,
                    "last_feedback": (
                        "Your previous attempt crashed before finishing:\n"
                        f"{res.error}\n"
                        "Retry from the current repo state. Use ONLY the provided tools, "
                        "each by its exact name, and make forward progress."
                    ),
                    "outcome": "",
                    "_next": "develop",
                    "log": [f"develop[{attempt}]: agent error -> retry {attempt + 1}: {res.error}"],
                    "events": failed_ev + [
                        {"type": EventType.RETRY_SCHEDULED.value,
                         "payload": {"task_id": task.id, "next_attempt": attempt + 1}}
                    ],
                }
            return {
                "agent_error": res.error,
                "outcome": "error",
                "_next": "escalate",
                "log": [f"develop[{attempt}]: agent error, retries exhausted: {res.error}"],
                "events": failed_ev,
            }

        if res.claims_blocked:
            return {
                "agent_summary": res.summary,
                "outcome": "blocked",
                "_next": "escalate",
                "log": [f"develop[{attempt}]: agent reports BLOCKED"],
                "events": events + [
                    {"type": EventType.BLOCKER_CREATED.value,
                     "payload": {"task_id": task.id, "reason": res.summary[:1000]}}
                ],
            }

        return {
            "agent_summary": res.summary,
            "outcome": "",
            "_next": "verify",
            "log": [f"develop[{attempt}]: {res.steps} steps, tools={res.tool_calls}"],
            "events": events + [
                {"type": EventType.TASK_COMPLETION_CLAIMED.value,
                 "payload": {"task_id": task.id, "attempt": attempt, "summary": res.summary[:1000]}}
            ],
        }

    def verify(state: TaskRunState) -> dict[str, Any]:
        task = Task.model_validate(state["task"])
        ws = _mk_workspace(state, settings)
        attempt = state.get("attempt", 1)

        report = verify_task(task, ws, base_commit=state.get("base_commit"), settings=settings)
        verdict = {
            "passed": report.passed,
            "render": report.render(),
            "feedback": report.feedback_for_agent(),
            "tests_passed": report.tests_passed,
            "implementation_present": report.implementation_present,
        }
        test_evt = (
            EventType.TEST_PASSED.value if report.tests_passed else EventType.TEST_FAILED.value
        )
        events = [
            {"type": EventType.TASK_VERIFIED.value,
             "payload": {"task_id": task.id, "attempt": attempt, "passed": report.passed}},
            {"type": test_evt, "payload": {"task_id": task.id, "attempt": attempt}},
        ]

        if report.passed:
            return {"verification": verdict, "_next": "commit",
                    "log": [f"verify[{attempt}]: PASS"], "events": events}

        if attempt < state.get("max_attempts", settings.max_task_retries):
            return {
                "verification": verdict,
                "attempt": attempt + 1,
                "last_feedback": report.feedback_for_agent(),
                "_next": "develop",
                "log": [f"verify[{attempt}]: FAIL -> retry {attempt + 1}"],
                "events": events + [
                    {"type": EventType.RETRY_SCHEDULED.value,
                     "payload": {"task_id": task.id, "next_attempt": attempt + 1}}
                ],
            }

        return {
            "verification": verdict,
            "outcome": "escalated",
            "_next": "escalate",
            "log": [f"verify[{attempt}]: FAIL -> retries exhausted"],
            "events": events,
        }

    def commit(state: TaskRunState) -> dict[str, Any]:
        task = Task.model_validate(state["task"])
        ws = _mk_workspace(state, settings)

        _advance_to(task, TaskStatus.TESTING, actor=state["agent_role"], note="verification passed")
        msg = (
            f"{_conventional_type(task)}: {task.title}\n\n"
            f"{state.get('agent_summary', '').strip()[:600]}\n\n"
            f"Task: {task.id}"
        )
        res = ws.commit_all(msg, trailer=settings.commit_trailer)
        commit_hash = ws.last_commit_hash() if res.ok else None

        events: list[dict[str, Any]] = []
        if res.ok and commit_hash:
            task.add_evidence(commit=commit_hash, actor=state["agent_role"])
            try:
                task.transition(TaskStatus.DONE, actor=state["agent_role"], note="verified + committed")
            except Exception:  # noqa: BLE001
                pass
            events += [
                {"type": EventType.COMMIT_CREATED.value,
                 "payload": {"task_id": task.id, "hash": commit_hash, "branch": state.get("branch")}},
                {"type": EventType.TASK_COMPLETED.value,
                 "payload": {"task_id": task.id, "hash": commit_hash}},
            ]
            outcome = "done"
            log = [f"commit: {commit_hash[:10]} -> task DONE"]
        else:
            outcome = "escalated"
            log = [f"commit FAILED: {res.stderr.strip()[:300]}"]
            events += [
                {"type": EventType.ESCALATED_TO_HUMAN.value,
                 "payload": {"task_id": task.id, "reason": "commit failed", "detail": res.stderr[:500]}}
            ]

        return {"task": task.model_dump(), "commit_hash": commit_hash,
                "outcome": outcome, "log": log, "events": events}

    def escalate(state: TaskRunState) -> dict[str, Any]:
        task = Task.model_validate(state["task"])
        outcome = state.get("outcome") or "escalated"
        note = {
            "blocked": "agent reported a blocker",
            "error": f"agent runtime error: {state.get('agent_error')}",
            "escalated": "verification failed after all retries",
        }.get(outcome, outcome)

        _advance_to(task, TaskStatus.BLOCKED, actor="scrum-master", note=note)
        return {
            "task": task.model_dump(),
            "outcome": outcome,
            "log": [f"escalate: {note}"],
            "events": [
                {"type": EventType.ESCALATED_TO_HUMAN.value,
                 "payload": {"task_id": task.id, "outcome": outcome, "note": note}}
            ],
        }

    return prepare, develop, verify, commit, escalate


# --------------------------------------------------------------------------
# graph
# --------------------------------------------------------------------------
def build_task_graph(settings: Settings | None = None, *, checkpointer: Any | None = None):
    settings = settings or get_settings()
    prepare, develop, verify, commit, escalate = _make_nodes(settings)

    g = StateGraph(TaskRunState)
    g.add_node("prepare", prepare)
    g.add_node("develop", develop)
    g.add_node("verify", verify)
    g.add_node("commit", commit)
    g.add_node("escalate", escalate)

    g.add_edge(START, "prepare")
    g.add_edge("prepare", "develop")
    g.add_conditional_edges(
        "develop", lambda s: s.get("_next", "verify"),
        {"verify": "verify", "develop": "develop", "escalate": "escalate"},
    )
    g.add_conditional_edges(
        "verify", lambda s: s.get("_next", "escalate"),
        {"develop": "develop", "commit": "commit", "escalate": "escalate"},
    )
    g.add_edge("commit", END)
    g.add_edge("escalate", END)
    return g.compile(checkpointer=checkpointer)


def run_task(
    task: Task,
    *,
    workspace_root: str,
    agent_role: str,
    settings: Settings | None = None,
    project_summary: str = "",
    project_id: str | None = None,
    sprint_id: str | None = None,
    max_attempts: int | None = None,
) -> TaskRunResult:
    """Run one task end to end. Returns the updated task, outcome and event list.

    The caller is responsible for persisting the task and emitting ``events`` to
    the project event bus (kept out of here so the graph stays I/O-light).
    """
    settings = settings or get_settings()
    graph = build_task_graph(settings)

    init: TaskRunState = {
        "task": task.model_dump(),
        "agent_role": agent_role,
        "workspace_root": workspace_root,
        "project_summary": project_summary,
        "project_id": project_id,
        "sprint_id": sprint_id,
        "max_attempts": max_attempts or settings.max_task_retries,
        "log": [],
        "events": [],
    }
    final: TaskRunState = graph.invoke(init, config={"recursion_limit": 60})

    return TaskRunResult(
        task=Task.model_validate(final["task"]),
        outcome=final.get("outcome") or "escalated",
        attempts=final.get("attempt", 1),
        branch=final.get("branch"),
        commit_hash=final.get("commit_hash"),
        agent_summary=final.get("agent_summary", ""),
        agent_error=final.get("agent_error"),
        verification_render=(final.get("verification") or {}).get("render", ""),
        log=final.get("log", []),
        events=final.get("events", []),
    )
