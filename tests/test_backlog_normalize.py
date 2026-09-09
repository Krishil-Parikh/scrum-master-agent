"""The backlog planner must survive the loose JSON small models actually emit."""

from aamt.planning.backlog_planner import _normalize, materialize_backlog
from aamt.planning.schemas import BacklogPlan

# The exact shape that broke the first live run: "task"/"feature"/"story" keys,
# acceptance_criteria as a single object, depends_on by title.
LOOSE = {
    "epic": "Build a REST API for a personal task list",
    "features": [
        {
            "feature": "User Authentication",
            "stories": [
                {
                    "story": "Implement user registration",
                    "tasks": [
                        {
                            "task": "Create user model and database schema",
                            "role": "database",
                            "acceptance_criteria": {"check": "python -c \"assert True\""},
                        },
                        {
                            "task": "Implement registration endpoint",
                            "role": "back-end",
                            "depends_on": ["Create user model and database schema"],
                            "acceptance_criteria": {
                                "text": "POST /register returns 201",
                                "check": "true",
                            },
                        },
                    ],
                }
            ],
        },
        {
            "feature": "Tasks",
            "tasks": [  # tasks directly under a feature (no story)
                {
                    "task": "Write tests for protected endpoints",
                    "role": "qa engineer",
                    "priority": "high",
                    "estimate": "2",
                    "depends_on": ["Implement registration endpoint"],
                    "acceptance_criteria": ["unauthenticated request gets 401"],
                }
            ],
        },
    ],
}


def test_normalize_repairs_loose_shape():
    plan = BacklogPlan.model_validate(_normalize(LOOSE))
    tasks = plan.all_tasks()
    assert len(tasks) == 3

    by_title = {t.title: t for t in tasks}
    reg = by_title["Implement registration endpoint"]
    schema = by_title["Create user model and database schema"]
    qa = by_title["Write tests for protected endpoints"]

    assert reg.role == "backend"                     # "back-end" alias
    assert qa.role == "qa"                           # "qa engineer" alias
    assert qa.priority == "HIGH"                     # "high" -> HIGH
    assert qa.estimate == 2.0                        # "2" -> 2.0
    assert reg.depends_on == [schema.ref]            # title resolved to ref
    assert qa.depends_on == [reg.ref]
    assert schema.acceptance_criteria[0].check       # object criterion kept


def test_normalize_result_materializes_with_wired_deps():
    plan = BacklogPlan.model_validate(_normalize(LOOSE))
    rows = materialize_backlog(plan)
    work = {t.title: t for t in rows if t.kind.value == "TASK"}
    assert work["Implement registration endpoint"].dependencies == [
        work["Create user model and database schema"].id
    ]


def test_normalize_handles_bare_list_and_string_criteria():
    raw = [
        {"title": "Feature A", "stories": [
            {"title": "S", "tasks": [
                {"title": "do a thing", "acceptance_criteria": "it works"},
            ]},
        ]},
    ]
    plan = BacklogPlan.model_validate(_normalize(raw))
    assert plan.all_tasks()[0].acceptance_criteria[0].text == "it works"
