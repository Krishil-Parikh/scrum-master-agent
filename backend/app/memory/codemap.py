"""
Persistent "what does this codebase actually look like right now" record
(scaling roadmap #3). Several 2026 sources on scaling coding agents converge
on the same fix for context blindness: a lightweight memory graph tracking
relationships between symbols, files, and past decisions, queried by
relevance rather than stuffed wholesale into every prompt.

This is that idea scoped to what this project actually needs: updated after
every completed task from data already on hand (no extra LLM call) --
which specialty owns the file, what task last touched it, a one-line
summary of why, and the real function/class/route symbols in it (reusing
the same regex extractor code_search.py uses for on-demand lookups, so the
two stay consistent). Queried by simple relevance (specialty match +
keyword overlap), not embedding similarity -- see code_search.py's module
docstring for why that tradeoff was made at this project's scale.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.tools.code_search import symbols_in_file

logger = logging.getLogger("ai_dev_pod.memory.codemap")


@dataclass
class CodemapEntry:
    path: str
    specialty: str
    task_title: str
    summary: str
    symbols: list[str] = field(default_factory=list)


class Codemap:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self._entries: dict[str, CodemapEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._entries = {path: CodemapEntry(**data) for path, data in raw.items()}
        except Exception:
            logger.exception("Failed to load codemap from %s -- starting fresh", self.store_path)
            self._entries = {}

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        raw = {path: asdict(entry) for path, entry in self._entries.items()}
        self.store_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def record_task(self, *, specialty: str, task_title: str, summary: str, files: dict[str, str] | list[str], worktree: Path) -> None:
        """Called once per completed task with the files it wrote. Cheap:
        no LLM call, just a regex symbol sweep over the files that already
        exist on disk in the worktree."""
        for rel_path in files:
            full_path = worktree / rel_path
            symbols: list[str] = []
            if full_path.exists():
                try:
                    symbols = [f"{s.kind} {s.name}" for s in symbols_in_file(full_path, rel_path)][:15]
                except Exception:
                    symbols = []
            self._entries[rel_path] = CodemapEntry(
                path=rel_path, specialty=specialty, task_title=task_title, summary=(summary or "")[:300], symbols=symbols,
            )
        self._save()

    def relevant_to(self, *, specialty: str, keywords: list[str], max_entries: int = 8) -> list[CodemapEntry]:
        """Simple relevance scoring: same specialty scores higher, and each
        keyword (from the new task's own title/description) found in a
        prior entry's title/summary/symbols adds to the score. This is
        deliberately not similarity search -- exact keyword/specialty
        matching is enough at this project's scale and is fully
        explainable (see code_search.py's docstring)."""
        keywords_lower = [k.lower() for k in keywords if k and len(k) > 2]
        scored: list[tuple[int, CodemapEntry]] = []
        for entry in self._entries.values():
            score = 2 if entry.specialty == specialty else 0
            haystack = f"{entry.task_title} {entry.summary} {' '.join(entry.symbols)}".lower()
            score += sum(1 for k in keywords_lower if k in haystack)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda pair: -pair[0])
        return [entry for _, entry in scored[:max_entries]]

    @staticmethod
    def render(entries: list[CodemapEntry]) -> str:
        if not entries:
            return ""
        lines = []
        for e in entries:
            symbol_text = ", ".join(e.symbols[:6]) if e.symbols else "(no symbols detected)"
            lines.append(f"- {e.path} [{e.specialty}] -- from '{e.task_title}': {e.summary}\n  symbols: {symbol_text}")
        return "\n".join(lines)
