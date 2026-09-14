"""
Business SME interaction (PRD §6.2, §12; Roadmap Phase 6).

Two modes, chosen by settings.sme_mode:
  - "human": questions are persisted as open SMEQuestions and surfaced to
    the frontend's SME modal (see api/routes_sme.py); the pipeline waits
    for a real answer via the API.
  - "auto": an LLM plays the Business SME persona and answers immediately,
    grounded in the project context -- used for unattended end-to-end runs
    (e.g. the live demo / CI-style run) where no human is available to
    click through the modal.

Either way, every question and answer goes through the same
record_sme_question / record_sme_answer persistence and the same
SME_QUESTION_CREATED / SME_RESPONSE_RECEIVED events, so the frontend and
Markdown history look identical regardless of which mode produced them.
"""

from __future__ import annotations

import asyncio
import logging

from app.communication.event_bus import get_event_bus
from app.config import get_settings
from app.llm.openrouter_client import get_llm_client
from app.llm.prompts import JSON_ONLY_INSTRUCTION, truncate
from app.schemas.communication import MessageChannel, SMEAnswer, SMEQuestion
from app.schemas.event import EventType
from app.schemas.project import ProjectContext

logger = logging.getLogger("ai_dev_pod.sme")

_SME_SYSTEM_PROMPT = f"""You are the Business SME (Subject Matter Expert) and Product Owner for this project. Engineers on the AI development pod ask you clarifying questions about ambiguous requirements. Answer decisively and practically, the way a real product owner would in a short Slack reply -- concrete, willing to make a reasonable call rather than saying "it depends," and consistent with the project's stated objective and existing decisions. Keep answers to 2-4 sentences.

{JSON_ONLY_INSTRUCTION}"""


async def ask_question(context: ProjectContext, question: SMEQuestion) -> None:
    from app.memory.project_memory import get_current_project_id, get_project_memory

    bus = get_event_bus()
    if get_current_project_id():
        get_project_memory().record_sme_question(question)
    await bus.emit(
        EventType.SME_QUESTION_CREATED,
        actor_id=question.asked_by,
        question_id=question.question_id,
        text=question.text,
        priority=question.priority,
    )


async def answer_question(context: ProjectContext, question: SMEQuestion, answer_text: str, decision: str = "") -> SMEAnswer:
    """Record a human-provided answer (used by the /sme/answer API route)."""
    from app.memory.project_memory import get_current_project_id, get_project_memory

    answer = SMEAnswer(question_id=question.question_id, text=answer_text, decision=decision or answer_text)
    if get_current_project_id():
        get_project_memory().record_sme_answer(question.question_id, answer)
    bus = get_event_bus()
    await bus.emit(EventType.SME_RESPONSE_RECEIVED, actor_id="sme", question_id=question.question_id)
    return answer


async def auto_answer_question(context: ProjectContext, question: SMEQuestion) -> SMEAnswer:
    """LLM-played Business SME answer, for unattended (SME_MODE=auto) runs."""
    client = get_llm_client()
    prompt = f"""
Project objective: {context.objective}
Business context: {context.business_context}

An engineer asks:
"{question.text}"

Reason it's ambiguous: {question.reason}

Return JSON: {{"answer": "your reply as the Business SME", "decision": "one-sentence definitive decision statement"}}
""".strip()
    try:
        raw = await client.chat_json(
            [{"role": "system", "content": _SME_SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        )
        answer_text = str(raw.get("answer", "")) if isinstance(raw, dict) else str(raw)
        decision = str(raw.get("decision", answer_text)) if isinstance(raw, dict) else answer_text
    except Exception:
        logger.exception("auto_answer_question failed for %s", question.question_id)
        answer_text = "No strong preference -- use your best judgment and document the assumption."
        decision = "Deferred to engineering judgment."

    return await answer_question(context, question, answer_text, decision)


async def run_sme_session(context: ProjectContext, questions: list[SMEQuestion]) -> list[tuple[SMEQuestion, SMEAnswer | None]]:
    """Ask every question and, in auto mode, answer them immediately and
    concurrently. In human mode, questions are left open for the API/UI."""
    settings = get_settings()
    bus = get_event_bus()

    await bus.emit(EventType.PHASE_STARTED, phase="sme_session", question_count=len(questions))
    for q in questions:
        await ask_question(context, q)

    results: list[tuple[SMEQuestion, SMEAnswer | None]] = []
    if settings.sme_mode == "auto":
        answers = await asyncio.gather(*(auto_answer_question(context, q) for q in questions), return_exceptions=True)
        for q, a in zip(questions, answers):
            if isinstance(a, Exception):
                logger.exception("SME auto-answer failed for %s", q.question_id, exc_info=a)
                results.append((q, None))
            else:
                results.append((q, a))
    else:
        results = [(q, None) for q in questions]

    await bus.emit(EventType.PHASE_COMPLETED, phase="sme_session", answered=sum(1 for _, a in results if a))
    return results
