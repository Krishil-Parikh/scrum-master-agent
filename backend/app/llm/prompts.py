"""Shared prompt-building helpers. Keeping these in one place means every
agent asks the model for structured output the same way, which is most of
what makes cheap models return usable JSON consistently."""

from __future__ import annotations

JSON_ONLY_INSTRUCTION = (
    "Respond with ONLY a single valid JSON value (object or array) and "
    "nothing else -- no prose, no markdown code fences, no explanation "
    "before or after it. If you are unsure, still return your best-effort "
    "JSON matching the requested shape."
)


def build_system_prompt(
    *,
    role_title: str,
    specialty_description: str,
    project_name: str,
    responsibilities: list[str],
    extra_context: str = "",
) -> str:
    resp = "\n".join(f"- {r}" for r in responsibilities)
    parts = [
        f"You are {role_title}, part of an autonomous AI Agile software "
        f"development pod building: {project_name}.",
        specialty_description,
        "Your responsibilities:",
        resp,
        (
            "Stay in character as this role. Be concise and concrete -- "
            "write like a competent, slightly terse senior engineer in a "
            "real standup or PR, not like a marketing description of one. "
            "Never invent facts about the project that contradict the "
            "provided context; if something is genuinely unknown, say so."
        ),
    ]
    if extra_context:
        parts.append(extra_context)
    return "\n\n".join(parts)


def truncate(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, {len(text) - max_chars} more characters]"
