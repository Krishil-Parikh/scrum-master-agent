"""BaseAgent — a role + a model + a toolset wrapped in a ReAct loop.

Phase 1 only needs the developer variant, but the shape here (identity, tools,
bounded step budget, structured result) is what the Scrum Master and reviewer
agents will reuse in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from ..config import Settings, get_settings
from ..llm.provider import build_chat_model
from ..models.agent import AgentSpec


@dataclass
class AgentRunResult:
    ok: bool
    summary: str                          # the agent's final natural-language message
    steps: int = 0                        # number of model turns
    tool_calls: list[str] = field(default_factory=list)  # tool names invoked, in order
    error: str | None = None
    messages: list[BaseMessage] = field(default_factory=list)

    @property
    def claims_blocked(self) -> bool:
        low = self.summary.lower()
        return "blocked" in low or "cannot proceed" in low or "blocker:" in low


class BaseAgent:
    def __init__(self, spec: AgentSpec, *, settings: Settings | None = None):
        self.spec = spec
        self.settings = settings or get_settings()

    # --- lazily built model ------------------------------------------
    def _model(self):
        return build_chat_model(
            model=self.spec.model
            or (
                self.settings.coordinator_model
                if self.spec.is_coordinator
                else self.settings.developer_model
            ),
            settings=self.settings,
        )

    # --- run ------------------------------------------------------
    def run(
        self,
        objective: str,
        *,
        tools: list[BaseTool],
        system_prompt: str | None = None,
        max_steps: int | None = None,
    ) -> AgentRunResult:
        max_steps = max_steps or self.settings.max_agent_steps
        agent = create_react_agent(self._model(), tools)
        sys = system_prompt or self.spec.system_prompt

        try:
            state = agent.invoke(
                {"messages": [SystemMessage(content=sys), HumanMessage(content=objective)]},
                config={"recursion_limit": max_steps * 2 + 4},
            )
        except Exception as exc:  # noqa: BLE001 - surfaced in the result
            return AgentRunResult(
                ok=False, summary="", error=f"{type(exc).__name__}: {exc}"
            )

        msgs: list[BaseMessage] = state["messages"]
        tool_calls: list[str] = []
        steps = 0
        for m in msgs:
            if isinstance(m, AIMessage):
                steps += 1
                for tc in m.tool_calls or []:
                    tool_calls.append(tc["name"])

        final = next(
            (m for m in reversed(msgs) if isinstance(m, AIMessage) and not m.tool_calls),
            None,
        )
        summary = (final.content if final else "") or ""
        if isinstance(summary, list):  # some providers return content parts
            summary = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in summary
            )
        summary = summary.strip()

        # Some providers (seen with Mistral on certain OpenRouter backends) emit a
        # tool call as *plain text* instead of a structured tool_calls entry, so the
        # ReAct loop never executes it and "finishes" with junk. Detect and fail the
        # attempt so the outer graph retries (possibly on a fallback model).
        malformed = any(
            marker in summary
            for marker in ("[TOOL_CALLS]", "<tool_call>", "<|python_tag|>", "functools[")
        )
        if malformed or (not tool_calls and (not summary or len(summary) < 15)):
            return AgentRunResult(
                ok=False,
                summary=summary,
                steps=steps,
                tool_calls=tool_calls,
                messages=msgs,
                error=(
                    "model emitted a malformed / non-executed tool call "
                    f"({summary[:120]!r})" if malformed
                    else "agent produced no tool calls and no usable output"
                ),
            )

        return AgentRunResult(
            ok=True,
            summary=summary,
            steps=steps,
            tool_calls=tool_calls,
            messages=msgs,
        )
