"""Exercises the multi-language syntax gate (scaling roadmap priority #5:
a real Phase 14 quality gate, not just single-task Python checking)."""

from __future__ import annotations

import shutil

import pytest

from app.tools.syntax_check import check_file, check_python_file, check_structural_balance


def test_check_python_file_passes_valid_code(tmp_path):
    (tmp_path / "ok.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    assert check_python_file(tmp_path, "ok.py") is None


def test_check_python_file_reports_syntax_error(tmp_path):
    (tmp_path / "bad.py").write_text("def f(:\n    return 1\n", encoding="utf-8")
    error = check_python_file(tmp_path, "bad.py")
    assert error is not None
    assert "bad.py" in error or "SyntaxError" in error


def test_check_structural_balance_passes_balanced_jsx(tmp_path):
    (tmp_path / "ok.jsx").write_text(
        "export function Card({ title }) {\n  return <div className=\"card\">{title}</div>;\n}\n",
        encoding="utf-8",
    )
    assert check_structural_balance(tmp_path, "ok.jsx") is None


def test_check_structural_balance_catches_unclosed_brace(tmp_path):
    (tmp_path / "bad.jsx").write_text(
        "export function Card() {\n  return <div>{value}</div>;\n",  # missing closing }
        encoding="utf-8",
    )
    error = check_structural_balance(tmp_path, "bad.jsx")
    assert error is not None
    assert "unclosed" in error


def test_check_structural_balance_catches_unterminated_string(tmp_path):
    (tmp_path / "bad2.jsx").write_text(
        "const label = \"Save\n export default label;\n",
        encoding="utf-8",
    )
    error = check_structural_balance(tmp_path, "bad2.jsx")
    assert error is not None
    assert "unterminated" in error


def test_check_structural_balance_ignores_brackets_inside_strings(tmp_path):
    (tmp_path / "ok2.jsx").write_text(
        "const msg = \"array looks like [1, 2, {a: 1}\";\n"
        "function f() { return msg; }\n",
        encoding="utf-8",
    )
    assert check_structural_balance(tmp_path, "ok2.jsx") is None


def test_check_file_dispatches_by_extension(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "a.jsx").write_text("const x = 1;\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("# hello\n", encoding="utf-8")

    assert check_file(tmp_path, "a.py") is None
    assert check_file(tmp_path, "a.jsx") is None
    assert check_file(tmp_path, "a.md") is None  # no checker for markdown -- not an error


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed on PATH")
def test_check_plain_js_file_catches_real_syntax_error(tmp_path):
    from app.tools.syntax_check import check_plain_js_file

    (tmp_path / "bad.js").write_text("function f( {\n  return 1;\n}\n", encoding="utf-8")
    error = check_plain_js_file(tmp_path, "bad.js")
    assert error is not None
