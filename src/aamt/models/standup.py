"""Daily standup records (PRD §14, phased plan §8.1-8.3).

A "day" is a tick — one pass of the sprint's task list. Every standup is
persisted so the final report can replay the sprint day by day.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..ids import new_id, now_ts


class StandupEntry(BaseModel):
    agent_id: str
    role: str
    yesterday: str = ""          # what completed since the last tick
    today: str = ""              # what's in flight / planned
    blockers: str = ""           # empty string == none


class Standup(BaseModel):
    id: str = Field(default_factory=lambda: new_id("SU"))
    sprint_id: str
    tick: int                    # 1-based standup number within the sprint
    entries: list[StandupEntry] = Field(default_factory=list)
    team_summary: str = ""
    flagged_blockers: list[str] = Field(default_factory=list)   # task ids
    stalled_tasks: list[str] = Field(default_factory=list)
    ts: float = Field(default_factory=now_ts)
