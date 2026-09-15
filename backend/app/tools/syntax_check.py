"""
Syntax validation for generated code (scaling roadmap #5: a real Phase 14
quality gate). The old gate only ever checked `.py` files -- frontend
output (`.jsx`/`.tsx`) got zero validation of any kind before this.

Python: `py_compile` via the real interpreter -- exact.
Plain JavaScript (no JSX): Node's own `--check` flag -- exact, no
execution, via the real Node already on this machine. Skipped gracefully
if Node isn't on PATH.
JSX/TSX/TS: neither tool above can parse these without a transformer this
backend doesn't carry as a dependency, so these get a structural heuristic
(balanced brackets/parens/braces, unterminated strings) instead. This
catches the failure mode LLM generation actually produces -- truncated or
malformed output -- but it is explicitly a heuristic, not a real parser,
and won't catch genuine JS-level errors a transpiler would.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.tools.command_runner import run_command

_OPENERS = {"(": ")", "[": "]", "{": "}"}
_CLOSERS = {v: k for k, v in _OPENERS.items()}


def check_python_file(worktree: Path, rel_path: str, *, timeout: int = 20) -> str | None:
    """None if the file compiles; otherwise the compiler's error text."""
    result = run_command(worktree, [sys.executable, "-m", "py_compile", rel_path], timeout=timeout)
    return None if result.ok else result.combined_output.strip()


def check_plain_js_file(worktree: Path, rel_path: str, *, timeout: int = 15) -> str | None:
    """Node's own --check (a real parse, no execution) for plain .js
    files. Best-effort: returns None (not an error) if node isn't
    installed, rather than failing every task on machines without it."""
    result = run_command(worktree, ["node", "--check", rel_path], timeout=timeout)
    if result.returncode == 127:
        return None
    return None if result.ok else result.combined_output.strip()


def check_structural_balance(worktree: Path, rel_path: str) -> str | None:
    """Heuristic, not a real parser: unbalanced brackets/parens/braces or
    an unterminated string -- the concrete failure mode of LLM output
    getting cut off mid-generation. Used for JSX/TSX/TS."""
    path = worktree / rel_path
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"could not read file: {exc}"

    stack: list[str] = []
    in_string: str | None = None
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            continue
        if ch in _OPENERS:
            stack.append(ch)
        elif ch in _CLOSERS:
            if not stack or stack[-1] != _CLOSERS[ch]:
                line = text.count("\n", 0, i) + 1
                return f"unbalanced '{ch}' at line {line} (structural heuristic, not a full parser)"
            stack.pop()
    if in_string:
        return f"unterminated {in_string!r} string (structural heuristic, not a full parser)"
    if stack:
        return f"unclosed '{stack[-1]}' (structural heuristic, not a full parser)"
    return None


def check_file(worktree: Path, rel_path: str) -> str | None:
    """Dispatch to the right checker by extension. None if clean or no
    checker applies to this extension."""
    suffix = Path(rel_path).suffix.lower()
    if suffix == ".py":
        return check_python_file(worktree, rel_path)
    if suffix == ".js":
        return check_plain_js_file(worktree, rel_path)
    if suffix in (".jsx", ".ts", ".tsx"):
        return check_structural_balance(worktree, rel_path)
    return None
