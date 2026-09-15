"""Exercises the read-only repo retrieval tools agents use to look around a
worktree before implementing a task (scaling roadmap priorities #1 and #6)."""

from __future__ import annotations

from app.tools.code_search import grep, list_tree, read_file_safe, search_symbols


def _make_repo(tmp_path):
    (tmp_path / "src" / "routes").mkdir(parents=True)
    (tmp_path / "src" / "routes" / "auth.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.post('/login')\n"
        "def login(payload):\n"
        "    return {'token': 'x'}\n\n"
        "class AuthError(Exception):\n"
        "    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "components" / "LoginForm.jsx").write_text(
        "export function LoginForm() {\n  return null;\n}\n"
        "const useAuth = () => {\n  return {};\n};\n",
        encoding="utf-8",
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("should not be indexed", encoding="utf-8")
    return tmp_path


def test_list_tree_skips_ignored_dirs(tmp_path):
    root = _make_repo(tmp_path)
    tree = list_tree(root)
    assert "src/routes/auth.py" in tree
    assert "src/components/LoginForm.jsx" in tree
    assert not any("node_modules" in p for p in tree)


def test_read_file_safe_reads_and_caps(tmp_path):
    root = _make_repo(tmp_path)
    content = read_file_safe(root, "src/routes/auth.py")
    assert "def login" in content

    huge = read_file_safe(root, "src/routes/auth.py", max_chars=10)
    assert huge.endswith("more characters)")
    assert len(huge) < 200


def test_read_file_safe_refuses_path_traversal(tmp_path):
    root = _make_repo(tmp_path)
    result = read_file_safe(root, "../../etc/passwd")
    assert "refused" in result


def test_grep_finds_matches_with_line_numbers(tmp_path):
    root = _make_repo(tmp_path)
    results = grep(root, "login")
    assert any("src/routes/auth.py:4" in r for r in results)


def test_search_symbols_finds_python_and_js_definitions(tmp_path):
    root = _make_repo(tmp_path)
    results = search_symbols(root, "login")
    joined = "\n".join(results)
    assert "route POST /login" in joined
    assert "function login" in joined
    assert "function LoginForm" in joined


def test_search_symbols_finds_python_class(tmp_path):
    root = _make_repo(tmp_path)
    results = search_symbols(root, "AuthError")
    assert any("class AuthError" in r for r in results)
