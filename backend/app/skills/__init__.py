"""Skill System (PRD §16-17; Roadmap Phase 3): discovery + dynamic loading
of the shared capability library, so an agent can pick up a skill outside
its primary specialty without losing that primary identity."""

from app.skills.loader import Skill, SkillLoader, get_skill_loader

__all__ = ["Skill", "SkillLoader", "get_skill_loader"]
