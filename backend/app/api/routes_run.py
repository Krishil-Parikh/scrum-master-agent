"""Pipeline run control -- Start/Pause/Resume/Stop, matching the dashboard
header controls (Roadmap Phase 17: End-to-End Orchestration)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.memory.project_memory import get_current_project_id, get_project_memory
from app.orchestration.orchestrator import get_orchestrator
from app.orchestration.run_control import RunStopped, get_run_controller

logger = logging.getLogger("ai_dev_pod.api.run")
router = APIRouter(prefix="/api/run", tags=["run"])

_background_task: asyncio.Task | None = None


async def _run_pipeline_task() -> None:
    orchestrator = get_orchestrator()
    memory = get_project_memory()
    context = memory.load_context()
    try:
        await orchestrator.run_full_pipeline(context)
    except RunStopped:
        logger.info("Pipeline stopped by user request.")
    except Exception:
        logger.exception("Pipeline run raised an unhandled exception.")


@router.post("/start")
async def start_run() -> dict:
    global _background_task
    if not get_current_project_id():
        raise HTTPException(400, "Create a project first (POST /api/project/intake).")
    controller = get_run_controller()
    if _background_task is not None and not _background_task.done():
        raise HTTPException(409, "A run is already in progress.")
    _background_task = asyncio.create_task(_run_pipeline_task())
    return {"status": controller.status.value}


@router.post("/pause")
async def pause_run() -> dict:
    controller = get_run_controller()
    controller.pause()
    return {"status": controller.status.value}


@router.post("/resume")
async def resume_run() -> dict:
    controller = get_run_controller()
    controller.resume()
    return {"status": controller.status.value}


@router.post("/stop")
async def stop_run() -> dict:
    controller = get_run_controller()
    controller.stop()
    return {"status": controller.status.value}


@router.get("/status")
async def run_status() -> dict:
    controller = get_run_controller()
    return {
        "status": controller.status.value,
        "current_phase": controller.current_phase,
        "elapsed_seconds": controller.elapsed_seconds,
    }
