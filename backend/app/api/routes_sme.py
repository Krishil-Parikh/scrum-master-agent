"""Business SME question/answer endpoints -- backs the "Question for
Business SME" modal (PRD §6.2, §12)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.memory.project_memory import get_current_project_id, get_project_memory
from app.orchestration import sme as sme_module
from app.schemas.communication import SMEQuestion

router = APIRouter(prefix="/api/sme", tags=["sme"])


@router.get("/questions")
async def list_questions(open_only: bool = True) -> list[dict]:
    if not get_current_project_id():
        return []
    return get_project_memory().list_sme_questions(open_only=open_only)


class AnswerBody(BaseModel):
    question_id: str
    text: str
    decision: str = ""


@router.post("/answer")
async def answer_question(body: AnswerBody) -> dict:
    if not get_current_project_id():
        raise HTTPException(400, "No active project.")
    memory = get_project_memory()
    records = memory.list_sme_questions(open_only=False)
    match = next((r for r in records if r["question"]["question_id"] == body.question_id), None)
    if not match:
        raise HTTPException(404, "Unknown question_id.")
    question = SMEQuestion.model_validate(match["question"])
    context = memory.load_context()
    answer = await sme_module.answer_question(context, question, body.text, body.decision)
    return {"question_id": body.question_id, "answer": answer.model_dump()}
