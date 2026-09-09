"""BaseAgent result parsing — especially the malformed-tool-call guard."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from aamt.agents.base import BaseAgent
from aamt.models.agent import AgentSpec


class _StubAgent(BaseAgent):
    """Bypass the LLM: feed a canned message list into run()'s parser."""

    def __init__(self, messages):
        super().__init__(AgentSpec(role="backend", title="Backend"))
        self._messages = messages

    def run(self, objective, *, tools, system_prompt=None, max_steps=None):  # type: ignore[override]
        # reuse the real parsing by monkey-constructing the tail of BaseAgent.run
        import aamt.agents.base as mod

        real = mod.create_react_agent

        class _FakeGraph:
            def invoke(self, _state, config=None):
                return {"messages": self._messages}
            _messages = self._messages

        mod.create_react_agent = lambda *a, **k: _FakeGraph()
        try:
            return super().run(objective, tools=[], system_prompt=system_prompt, max_steps=max_steps)
        finally:
            mod.create_react_agent = real


def test_real_completion_is_ok():
    msgs = [
        HumanMessage(content="do it"),
        AIMessage(content="", tool_calls=[{"name": "write_file", "args": {"path": "a", "content": "x"}, "id": "1"}]),
        ToolMessage(content="wrote a", tool_call_id="1"),
        AIMessage(content="Done. I created a and the tests pass."),
    ]
    res = _StubAgent(msgs).run("x", tools=[])
    assert res.ok
    assert res.tool_calls == ["write_file"]
    assert "Done" in res.summary


def test_leaked_tool_call_text_is_failure():
    msgs = [
        HumanMessage(content="do it"),
        AIMessage(content="[TOOL_CALLS]repo_tree{}"),
    ]
    res = _StubAgent(msgs).run("x", tools=[])
    assert not res.ok
    assert "malformed" in (res.error or "")


def test_empty_output_no_tools_is_failure():
    msgs = [HumanMessage(content="do it"), AIMessage(content="ok")]
    res = _StubAgent(msgs).run("x", tools=[])
    assert not res.ok


def test_blocked_claim_flag():
    msgs = [
        HumanMessage(content="do it"),
        AIMessage(content="", tool_calls=[{"name": "repo_tree", "args": {}, "id": "1"}]),
        ToolMessage(content="(empty repo)", tool_call_id="1"),
        AIMessage(content="BLOCKED: this needs the database schema task done first."),
    ]
    res = _StubAgent(msgs).run("x", tools=[])
    assert res.ok and res.claims_blocked
