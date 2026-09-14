from app.skills.loader import SkillLoader


def test_discovers_all_nine_skills():
    loader = SkillLoader()
    names = set(loader.list_names())
    expected = {
        "frontend", "backend", "ai_ml", "devops", "mlops", "database",
        "testing", "security", "architecture",
    }
    assert expected.issubset(names)


def test_skill_has_required_sections():
    loader = SkillLoader()
    skill = loader.get("backend")
    assert skill is not None
    for section in ("## Purpose", "## Responsibilities", "## Best Practices", "## Security Considerations"):
        assert section in skill.body


def test_cross_specialty_loading_tracks_usage_without_changing_identity():
    """Roadmap Phase 3 success gate: a Frontend Agent can load the Backend
    skill and the loader records that usage, without this module knowing
    or caring about the agent's own specialty -- that's BaseAgent's job,
    this just proves the loader-level mechanics work."""
    loader = SkillLoader()
    skill = loader.load_for_agent("frontend", "backend")
    assert skill is not None
    assert skill.name == "backend"
    assert loader.skills_used_by("frontend") == ["backend"]

    # Loading it again shouldn't duplicate the usage record.
    loader.load_for_agent("frontend", "backend")
    assert loader.skills_used_by("frontend") == ["backend"]


def test_unknown_skill_returns_none():
    loader = SkillLoader()
    assert loader.load_for_agent("frontend", "nonexistent-skill") is None
