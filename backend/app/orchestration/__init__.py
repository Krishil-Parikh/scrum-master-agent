"""Orchestration layer (PRD §39 "Orchestration"; Roadmap Phase 17): agent
lifecycle, task allocation, and the phase-by-phase pipeline that connects
every other layer into one end-to-end run."""

from app.orchestration.orchestrator import Orchestrator, get_orchestrator

__all__ = ["Orchestrator", "get_orchestrator"]
