"""
Run one full, end-to-end AI Dev Pod project without the API/frontend --
this is the "MVP Demonstration Project" (Roadmap Phase 18) and the script
used for live-testing the pod against the real OpenRouter API.

Usage (from backend/, with the venv active):

    python scripts/run_demo.py
    python scripts/run_demo.py path/to/custom_brief.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.orchestration.orchestrator import get_orchestrator  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai_dev_pod.demo")

DEFAULT_BRIEF = """\
# AI-Powered Task Management Platform

Build a small, AI-powered project/task management platform for a single team.

## Goals
- Users can sign up, log in, and manage their profile.
- Users can create projects and, within a project, create tasks.
- Each task has a title, description, status (todo/in_progress/done), and an assignee.
- An AI feature automatically suggests a category/label for a new task based on its title and description (e.g. "bug", "feature", "chore").
- A dashboard shows task counts by status and by category.

## Non-functional
- The API must validate all input server-side.
- The system should be deployable via Docker and have a basic CI pipeline (lint + test on every push).
- Task data must be stored in a relational database with a clear schema.

## Out of scope for this version
- Payments, billing, or multi-tenant organizations.
- Real-time collaborative editing.

## Open questions for the team
- Should task categorization run automatically on every task, or only on request?
- What roles exist beyond a single "member" role?
"""


async def main() -> None:
    brief_path = sys.argv[1] if len(sys.argv) > 1 else None
    if brief_path:
        text = Path(brief_path).read_text(encoding="utf-8")
        name = Path(brief_path).stem.replace("_", " ").title()
    else:
        text = DEFAULT_BRIEF
        name = "AI Task Management Platform"

    orchestrator = get_orchestrator()

    logger.info("=== Phase 4: Intake ===")
    context = await orchestrator.start_new_project(name, text)
    logger.info("Project created: %s (project_id=%s)", context.name, context.project_id)
    logger.info("Objective: %s", context.objective)
    logger.info("Requirements extracted: %d", len(context.requirements))

    logger.info("=== Running full pipeline (this calls the real OpenRouter API repeatedly) ===")
    report = await orchestrator.run_full_pipeline(context)

    logger.info("=== DONE ===")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
