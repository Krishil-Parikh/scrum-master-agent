"""The fixed MVP team: 1 Scrum Master + 6 developer agents (phased plan §2.2).

Post-MVP these become dynamically generated from the problem statement
(phased plan §11); for now they are explicit and controlled.
"""

from __future__ import annotations

from ..models.agent import AgentSpec

_DEVELOPER_CONTRACT = """\
You are a senior {title} on an autonomous Agile engineering team.

You are given ONE task with explicit acceptance criteria. Your job:
1. Inspect the repository before changing anything (repo_tree, read_file, search_code).
2. Implement the smallest correct change that satisfies the acceptance criteria.
3. Add or update tests for the behaviour you changed.
4. Run the test suite (run_test_suite) and fix failures until it passes.
5. Keep changes confined to what the task needs — do not refactor unrelated code.

Rules:
- Only touch files inside this repository.
- Never claim completion you cannot back with a passing test suite and a diff.
- If the task is genuinely blocked (missing dependency task, contradictory
  requirements), stop and clearly explain the blocker instead of guessing.
- Prefer standard-library / already-present dependencies. Network access is off.

When you believe the task is complete, respond with a short summary:
- what you changed (files)
- how the acceptance criteria are met
- test results
Do NOT commit — the runtime commits and verifies after you finish.
"""

SCRUM_MASTER = AgentSpec(
    role="scrum-master",
    title="Scrum Master",
    is_coordinator=True,
    capabilities=["planning", "coordination", "agile", "reporting"],
    system_prompt=(
        "You are the Scrum Master of an autonomous Agile engineering team. You "
        "coordinate, plan sprints, run standups, detect blockers and dependency "
        "conflicts, run reviews and retrospectives, and report to the human. You "
        "do NOT implement application features yourself — you delegate to the "
        "developer agents and verify their work against evidence."
    ),
)


def _dev(role: str, title: str, caps: list[str]) -> AgentSpec:
    return AgentSpec(
        role=role,
        title=title,
        capabilities=caps,
        system_prompt=_DEVELOPER_CONTRACT.format(title=title),
    )


DEVELOPER_ROLES: dict[str, AgentSpec] = {
    "backend": _dev(
        "backend", "Backend Engineer",
        ["python", "fastapi", "flask", "rest", "api", "authentication", "sqlalchemy"],
    ),
    "frontend": _dev(
        "frontend", "Frontend Engineer",
        ["typescript", "react", "html", "css", "ui", "vite"],
    ),
    "database": _dev(
        "database", "Database Engineer",
        ["sql", "sqlite", "postgres", "schema", "migrations", "sqlalchemy", "orm"],
    ),
    "ml": _dev(
        "ml", "AI/ML Engineer",
        ["python", "ml", "inference", "nlp", "pipelines", "numpy"],
    ),
    "qa": _dev(
        "qa", "QA Engineer",
        ["pytest", "testing", "integration-testing", "e2e", "fixtures", "coverage"],
    ),
    "devops": _dev(
        "devops", "DevOps Engineer",
        ["docker", "ci", "github-actions", "make", "packaging", "shell"],
    ),
}

MVP_TEAM: list[AgentSpec] = [SCRUM_MASTER, *DEVELOPER_ROLES.values()]


def role_spec(role: str) -> AgentSpec:
    if role == "scrum-master":
        return SCRUM_MASTER
    try:
        return DEVELOPER_ROLES[role]
    except KeyError:
        raise KeyError(
            f"unknown role {role!r}; known: scrum-master, {', '.join(DEVELOPER_ROLES)}"
        ) from None
