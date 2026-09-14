"""Scoped filesystem access. `safe_join` is the security boundary: every
write an agent makes is resolved against an explicit root and rejected if
it would land outside it (a `../../` path-traversal attempt in a
model-generated filename, for instance) -- see .claude/skills/security-audit
on path traversal at trust boundaries. Agent-generated file paths are
untrusted input; this is where that boundary is enforced."""

from __future__ import annotations

from pathlib import Path


class PathTraversalError(ValueError):
    pass


def safe_join(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    if root != candidate and root not in candidate.parents:
        raise PathTraversalError(
            f"Refusing to write outside the workspace root: {relative_path!r}"
        )
    return candidate


def write_text(root: Path, relative_path: str, content: str) -> Path:
    path = safe_join(root, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_text(root: Path, relative_path: str) -> str:
    path = safe_join(root, relative_path)
    return path.read_text(encoding="utf-8")
