"""Project Intake System (PRD §9; Roadmap Phase 4): accepts a raw project
document (Markdown/TXT/PDF/DOCX) and turns it into a structured
ProjectContext via the Requirement Analyzer."""

from app.intake.document_parser import extract_text
from app.intake.requirement_analyzer import analyze_document

__all__ = ["extract_text", "analyze_document"]
