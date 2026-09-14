"""
Skill discovery and dynamic loading (PRD §16-17; Roadmap Phase 3).

Skills are plain Markdown files with a tiny key: value frontmatter block,
living under app/skills/library/<name>/SKILL.md -- the same shape as this
repo's own .claude/skills/*/SKILL.md, deliberately: a skill is just a
reusable body of guidance an agent can pull into its context on demand.

Loading a skill never changes an agent's primary specialty/identity -- it
only adds the skill's body text to that agent's working context for the
current task, satisfying the PRD's "specialization without isolation"
principle (an agent can act with borrowed expertise but is still, e.g.,
fundamentally the Frontend Agent).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import SKILLS_DIR

logger = logging.getLogger("ai_dev_pod.skills")


@dataclass
class Skill:
    name: str
    specialty: str
    description: str
    body: str
    path: Path


def _parse_skill_file(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text

    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            frontmatter = text[3:end].strip()
            body = text[end + 4 :].lstrip("\n")
            for line in frontmatter.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()

    name = meta.get("name", path.parent.name)
    return Skill(
        name=name,
        specialty=meta.get("specialty", name),
        description=meta.get("description", ""),
        body=body.strip(),
        path=path,
    )


class SkillLoader:
    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = skills_dir
        self._cache: dict[str, Skill] | None = None
        # agent_id -> ordered list of skill names it has loaded, for
        # observability ("which skills has this agent used" -- PRD §17).
        self.usage: dict[str, list[str]] = {}

    def discover(self, *, force_reload: bool = False) -> dict[str, Skill]:
        if self._cache is not None and not force_reload:
            return self._cache

        skills: dict[str, Skill] = {}
        if self.skills_dir.exists():
            for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
                try:
                    skill = _parse_skill_file(skill_file)
                    skills[skill.name] = skill
                except Exception:
                    logger.exception("Failed to parse skill file %s", skill_file)
        self._cache = skills
        return skills

    def list_names(self) -> list[str]:
        return sorted(self.discover().keys())

    def get(self, name: str) -> Skill | None:
        return self.discover().get(name)

    def load_for_agent(self, agent_id: str, skill_name: str) -> Skill | None:
        skill = self.get(skill_name)
        if skill is None:
            logger.warning("Agent %s requested unknown skill %r", agent_id, skill_name)
            return None
        used = self.usage.setdefault(agent_id, [])
        if skill_name not in used:
            used.append(skill_name)
        return skill

    def skills_used_by(self, agent_id: str) -> list[str]:
        return list(self.usage.get(agent_id, []))


_loader: SkillLoader | None = None


def get_skill_loader() -> SkillLoader:
    global _loader
    if _loader is None:
        _loader = SkillLoader()
    return _loader
