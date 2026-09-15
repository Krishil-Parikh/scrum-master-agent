"""Exercises the project codemap -- the persistent "what has already been
built" record agents consult beyond their direct dependency chain
(scaling roadmap priority #3)."""

from __future__ import annotations

from app.memory.codemap import Codemap


def _worktree_with_file(tmp_path):
    worktree = tmp_path / "worktree"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src" / "auth.py").write_text(
        "def login(payload):\n    return {'token': 'x'}\n",
        encoding="utf-8",
    )
    return worktree


def test_record_task_extracts_symbols_and_persists(tmp_path):
    worktree = _worktree_with_file(tmp_path)
    store_path = tmp_path / "codemap.json"
    cm = Codemap(store_path)

    cm.record_task(
        specialty="backend", task_title="Login API",
        summary="Implemented the login endpoint.", files=["src/auth.py"], worktree=worktree,
    )

    assert store_path.exists()
    reloaded = Codemap(store_path)  # simulate a fresh process picking it back up
    hits = reloaded.relevant_to(specialty="backend", keywords=["login"])
    assert len(hits) == 1
    assert hits[0].path == "src/auth.py"
    assert "function login" in hits[0].symbols


def test_relevant_to_ranks_specialty_and_keyword_matches(tmp_path):
    worktree = _worktree_with_file(tmp_path)
    (worktree / "src" / "dashboard.jsx").write_text("export function Dashboard() { return null; }\n", encoding="utf-8")
    cm = Codemap(tmp_path / "codemap.json")
    cm.record_task(specialty="backend", task_title="Login API", summary="auth stuff", files=["src/auth.py"], worktree=worktree)
    cm.record_task(specialty="frontend", task_title="Dashboard UI", summary="dashboard widgets", files=["src/dashboard.jsx"], worktree=worktree)

    hits = cm.relevant_to(specialty="backend", keywords=["login"])

    assert hits, "expected at least one relevant entry"
    # Same-specialty + keyword match should outrank an unrelated specialty entry.
    assert hits[0].specialty == "backend"
    assert hits[0].path == "src/auth.py"


def test_relevant_to_returns_empty_for_no_match(tmp_path):
    cm = Codemap(tmp_path / "codemap.json")
    assert cm.relevant_to(specialty="backend", keywords=["nonexistent"]) == []


def test_render_produces_readable_text():
    from app.memory.codemap import CodemapEntry

    entry = CodemapEntry(path="src/auth.py", specialty="backend", task_title="Login API", summary="auth", symbols=["function login"])
    text = Codemap.render([entry])
    assert "src/auth.py" in text
    assert "function login" in text
    assert Codemap.render([]) == ""
