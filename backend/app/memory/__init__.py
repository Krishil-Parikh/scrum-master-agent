"""
Persistent Project Memory (PRD §10, §25, §26; Roadmap Phase 16).

Everything a project needs to "remember" lives under
`backend/project_data/<project_id>/`:

    context.json        -- the canonical ProjectContext (JSON)
    backlog.json         -- Epics/Stories/Tasks/Sprints (JSON)
    agents.json          -- live AgentStatus per agent (JSON)
    events.jsonl          -- append-only event log (one Event per line)
    docs/PROJECT.md
    docs/REQUIREMENTS.md
    docs/AGILE.md
    docs/STANDUPS.md
    docs/SME_DISCUSSIONS.md
    docs/DECISIONS.md
    docs/ARCHITECTURE.md
    docs/DEVELOPMENT_LOG.md
    docs/GIT_ACTIVITY.md
    docs/RETROSPECTIVES.md

JSON is the source of truth the backend reads/writes structurally; the
Markdown files under docs/ are the human- (and agent-) readable narrative
required by the PRD, regenerated/appended alongside every structural change.
A fresh agent (or a human) can `cat` any of those Markdown files and
understand exactly where the project stands without replaying conversation
history -- that's the whole point of this layer (PRD §10: "Agents should
never rely exclusively on their own conversation history").
"""

from app.memory.project_memory import ProjectMemory, get_project_memory

__all__ = ["ProjectMemory", "get_project_memory"]
