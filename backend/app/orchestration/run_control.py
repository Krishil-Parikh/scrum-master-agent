"""
Coarse-grained run control for the pipeline: Running / Paused / Stopped,
matching the dashboard's Pause/Stop header controls.

Control is checked at phase boundaries (between, say, "independent
analysis" and "SME session"), not inside a single agent's LLM call --
pausing mid-model-call would mean either abandoning an in-flight request or
building real cancellation plumbing through httpx, and the coarse version
gives the same practical behavior (the run stops making new progress
promptly) for a fraction of the complexity. That tradeoff is deliberate for
the MVP, not an oversight.
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum


class RunStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class RunStopped(Exception):
    pass


class RunController:
    def __init__(self) -> None:
        self.status: RunStatus = RunStatus.IDLE
        self.current_phase: str = ""
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused by default
        self._started_at: float | None = None

    def start(self) -> None:
        self.status = RunStatus.RUNNING
        self._started_at = time.time()
        self._pause_event.set()

    def pause(self) -> None:
        if self.status == RunStatus.RUNNING:
            self.status = RunStatus.PAUSED
            self._pause_event.clear()

    def resume(self) -> None:
        if self.status == RunStatus.PAUSED:
            self.status = RunStatus.RUNNING
            self._pause_event.set()

    def stop(self) -> None:
        self.status = RunStatus.STOPPED
        self._pause_event.set()  # unblock anything waiting so it can observe the stop

    def complete(self) -> None:
        self.status = RunStatus.COMPLETED

    def fail(self) -> None:
        self.status = RunStatus.FAILED

    async def checkpoint(self, phase: str) -> None:
        """Call between phases. Blocks while paused; raises RunStopped if
        the run was stopped."""
        self.current_phase = phase
        if self.status == RunStatus.STOPPED:
            raise RunStopped(phase)
        await self._pause_event.wait()
        if self.status == RunStatus.STOPPED:
            raise RunStopped(phase)

    @property
    def elapsed_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.time() - self._started_at


_controller: RunController | None = None


def get_run_controller() -> RunController:
    global _controller
    if _controller is None:
        _controller = RunController()
    return _controller
