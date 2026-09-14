"""
Requirement Analyzer (PRD §8 architecture diagram: "Problem Statement/PRD
-> Requirement Analyzer -> Project Context"; Roadmap Phase 4).

This runs once per intake, before the Scrum Master or any developer agent
sees the project -- it's the step that turns an arbitrary prose document
into the structured ProjectContext everything downstream retrieves instead
of re-reading the raw document.
"""

from __future__ import annotations

import logging

from app.llm.openrouter_client import get_llm_client
from app.llm.prompts import JSON_ONLY_INSTRUCTION, truncate
from app.schemas.project import ProjectContext, Requirement

logger = logging.getLogger("ai_dev_pod.intake")

_SYSTEM_PROMPT = f"""You are the Requirement Analyzer for an AI Agile software development pod. You read a raw project document (which may be informal, incomplete, or unstructured) and extract a clean, structured understanding of it. You do not write code or make product decisions -- you extract and organize what is actually stated, and separately note what is unclear.

{JSON_ONLY_INSTRUCTION}"""


async def analyze_document(project_name: str, raw_text: str) -> ProjectContext:
    prompt = f"""
Project document:
---
{truncate(raw_text, 14000)}
---

Extract a structured project context. Return a JSON object with exactly these keys:
{{
  "objective": "1-3 sentence statement of what is being built and why",
  "business_context": "relevant business/domain context",
  "requirements": [{{"text": "...", "kind": "functional|non_functional"}}],
  "constraints": ["..."],
  "stakeholders": ["..."],
  "acceptance_criteria": ["..."],
  "technology_stack": ["only technologies explicitly mentioned or strongly implied -- otherwise leave this empty"],
  "domain_terms": {{"term": "definition"}},
  "open_questions": [{{"question": "...", "reason": "why this is unclear from the document", "priority": "low|medium|high"}}]
}}
Extract only what the document actually supports; if the document doesn't cover a field, return an empty list/object for it rather than inventing content. Put genuinely ambiguous or missing information in "open_questions" instead of guessing.
""".strip()

    client = get_llm_client()
    raw = await client.chat_json(
        [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    )

    context = ProjectContext(name=project_name, raw_source_text=raw_text, status="analyzing")
    if isinstance(raw, dict):
        context.objective = str(raw.get("objective", "") or "")
        context.business_context = str(raw.get("business_context", "") or "")
        context.constraints = [str(c) for c in raw.get("constraints", []) or []]
        context.stakeholders = [str(s) for s in raw.get("stakeholders", []) or []]
        context.acceptance_criteria = [str(a) for a in raw.get("acceptance_criteria", []) or []]
        context.technology_stack = [str(t) for t in raw.get("technology_stack", []) or []]
        domain_terms = raw.get("domain_terms", {}) or {}
        context.domain_terms = {str(k): str(v) for k, v in domain_terms.items()} if isinstance(domain_terms, dict) else {}

        for req in raw.get("requirements", []) or []:
            if not isinstance(req, dict):
                continue
            kind = str(req.get("kind", "functional")).strip().lower()
            if kind not in ("functional", "non_functional"):
                kind = "functional"
            text = str(req.get("text", "")).strip()
            if text:
                context.requirements.append(Requirement(text=text, kind=kind, source="intake"))

        from app.schemas.project import OpenQuestion

        for q in raw.get("open_questions", []) or []:
            if not isinstance(q, dict):
                continue
            question_text = str(q.get("question", "")).strip()
            if question_text:
                context.open_questions.append(
                    OpenQuestion(
                        question=question_text,
                        reason=str(q.get("reason", "")),
                        priority=str(q.get("priority", "medium")),
                        owner="Requirement Analyzer",
                    )
                )
    else:
        logger.warning("Requirement analyzer returned non-dict JSON: %r", raw)

    return context
