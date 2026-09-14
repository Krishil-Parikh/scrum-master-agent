"""Project intake and Project Docs endpoints (PRD §9; Roadmap Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.intake.document_parser import UnsupportedDocumentError, extract_text
from app.memory.project_memory import get_current_project_id, get_project_memory
from app.orchestration.orchestrator import get_orchestrator
from app.schemas.project import ProjectContext

router = APIRouter(prefix="/api/project", tags=["project"])

ALLOWED_DOCS = {
    "PROJECT.md",
    "REQUIREMENTS.md",
    "AGILE.md",
    "ARCHITECTURE.md",
    "STANDUPS.md",
    "SME_DISCUSSIONS.md",
    "DECISIONS.md",
    "DEVELOPMENT_LOG.md",
    "GIT_ACTIVITY.md",
    "RETROSPECTIVES.md",
}


class IntakeTextBody(BaseModel):
    name: str
    text: str


@router.post("/intake", response_model=ProjectContext)
async def intake_text(body: IntakeTextBody) -> ProjectContext:
    if not body.text.strip():
        raise HTTPException(400, "text must not be empty")
    orchestrator = get_orchestrator()
    return await orchestrator.start_new_project(body.name, body.text)


@router.post("/intake/file", response_model=ProjectContext)
async def intake_file(name: str = Form(...), file: UploadFile = File(...)) -> ProjectContext:
    raw = await file.read()
    try:
        text = extract_text(file.filename or "document.txt", raw)
    except UnsupportedDocumentError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not text.strip():
        raise HTTPException(400, "No extractable text found in the uploaded document.")
    orchestrator = get_orchestrator()
    return await orchestrator.start_new_project(name, text)


@router.get("/current", response_model=ProjectContext)
async def get_current_project() -> ProjectContext:
    if not get_current_project_id():
        raise HTTPException(404, "No project has been created yet.")
    return get_project_memory().load_context()


@router.get("/docs")
async def list_docs() -> list[str]:
    if not get_current_project_id():
        return []
    memory = get_project_memory()
    return sorted(p.name for p in memory.md.docs_dir.glob("*.md"))


@router.get("/docs/{doc_name}")
async def get_doc(doc_name: str) -> dict:
    if doc_name not in ALLOWED_DOCS:
        raise HTTPException(404, "Unknown document.")
    if not get_current_project_id():
        raise HTTPException(404, "No project has been created yet.")
    memory = get_project_memory()
    path = memory.md.docs_dir / doc_name
    if not path.exists():
        return {"name": doc_name, "content": ""}
    return {"name": doc_name, "content": path.read_text(encoding="utf-8")}
