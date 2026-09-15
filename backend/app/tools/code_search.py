"""
Repo retrieval tools (scaling roadmap priorities #1 and #6): give an agent
real, on-demand visibility into the codebase it's about to work in, instead
of the orchestrator guessing which 1-2 dependency files to truncate and hand
over blind (the old `_implement_one_task` behavior).

Deliberately NOT a vector-embedding RAG pipeline. 2026 research on scaling
coding agents (see the "how to scale this" research turn in this project's
history) found that for code specifically, grep + symbols + structure
frequently outperforms naive semantic-similarity search, and a vector index
is heavy new infrastructure (an embedding model, a vector store) this
project doesn't need yet at its current scale. This module is the
lighter-weight version of that finding: full-text grep plus a regex-based
symbol index (function/class/route definitions) built fresh on every call --
no index to keep in sync, no new dependency.

Every function here is read-only and scoped to one worktree root via
`safe_join` (same path-traversal guard the write path uses) -- an agent can
look around, never escape or modify anything through these tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.tools.filesystem import safe_join

# Directories never worth showing an agent or indexing.
_IGNORED_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache"}
_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".yml", ".yaml",
    ".sql", ".css", ".html", ".txt", ".toml", ".ini", ".cfg",
}

_MAX_FILE_BYTES = 200_000  # skip indexing/grepping anything this large
_MAX_TREE_ENTRIES = 300
_MAX_GREP_MATCHES = 40
_MAX_SYMBOL_MATCHES = 60


def _iter_source_files(root: Path):
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _IGNORED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in _TEXT_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def list_tree(root: Path, *, max_entries: int = _MAX_TREE_ENTRIES) -> list[str]:
    """Relative paths of every source file in the worktree -- the cheapest
    "what exists here" view, for an agent deciding what to read or grep."""
    out: list[str] = []
    for path in _iter_source_files(root):
        out.append(str(path.relative_to(root)).replace("\\", "/"))
        if len(out) >= max_entries:
            out.append(f"... ({max_entries}+ files, truncated)")
            break
    return sorted(out)


def read_file_safe(root: Path, relative_path: str, *, max_chars: int = 4000) -> str:
    """Read a file an agent asked to see. Path-traversal guarded, length
    capped so one huge file can't blow the prompt budget."""
    try:
        path = safe_join(root, relative_path)
    except Exception:
        return f"(refused: {relative_path!r} is outside this worktree)"
    if not path.exists() or not path.is_file():
        return f"(not found: {relative_path})"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(could not read {relative_path}: {exc})"
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... (truncated, {len(text) - max_chars} more characters)"
    return text


def grep(root: Path, pattern: str, *, max_matches: int = _MAX_GREP_MATCHES) -> list[str]:
    """Plain substring/regex search across the worktree's source files.
    Returns "path:line: text" strings -- the same shape real grep gives a
    human, and (per the research above) often more useful for "where is X
    actually defined/used" than a similarity search would be."""
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error:
        rx = re.compile(re.escape(pattern), re.IGNORECASE)
    results: list[str] = []
    for path in _iter_source_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        for i, line in enumerate(lines, start=1):
            if rx.search(line):
                results.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(results) >= max_matches:
                    return results
    return results


# ---- symbol index: structure-aware search without an embeddings pipeline ----

_PY_DEF = re.compile(r"^\s*(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")
_PY_ROUTE = re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)")
_JS_DEF = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)")
_JS_CONST_FN = re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(")
_JS_CLASS = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)")


@dataclass
class Symbol:
    kind: str  # "function" | "class" | "route"
    name: str
    file: str
    line: int


def _symbols_in_file(path: Path, rel: str) -> list[Symbol]:
    out: list[Symbol] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    suffix = path.suffix.lower()
    for i, line in enumerate(lines, start=1):
        if suffix == ".py":
            m = _PY_DEF.match(line)
            if m:
                kind = "class" if line.strip().startswith("class") else "function"
                out.append(Symbol(kind, m.group(1), rel, i))
                continue
            m = _PY_ROUTE.search(line)
            if m:
                out.append(Symbol("route", f"{m.group(1).upper()} {m.group(2)}", rel, i))
        elif suffix in (".js", ".jsx", ".ts", ".tsx"):
            for pattern, kind in ((_JS_DEF, "function"), (_JS_CONST_FN, "function"), (_JS_CLASS, "class")):
                m = pattern.match(line)
                if m:
                    out.append(Symbol(kind, m.group(1), rel, i))
                    break
    return out


def search_symbols(root: Path, query: str, *, max_matches: int = _MAX_SYMBOL_MATCHES) -> list[str]:
    """Find function/class/route definitions whose name contains `query`
    (case-insensitive) anywhere in the worktree. Built fresh on every call
    (a regex sweep) rather than maintained as a persistent index -- simple,
    always correct, and fast enough at this project's scale."""
    query_lower = query.lower()
    results: list[str] = []
    for path in _iter_source_files(root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        for sym in _symbols_in_file(path, rel):
            if query_lower in sym.name.lower():
                results.append(f"{sym.kind} {sym.name}  ({sym.file}:{sym.line})")
                if len(results) >= max_matches:
                    return results
    return results
