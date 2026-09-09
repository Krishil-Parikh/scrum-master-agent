# Autonomous Agile Multi-Agent Software Engineering Team (`aamt`)

An autonomous AI software-engineering organization: a Scrum Master agent plus a
team of specialized developer agents that decompose a problem statement into a
backlog, plan and run sprints, write and integrate real code in a shared Git
repository, verify their work objectively, and iterate until acceptance criteria
are met — producing working software *and* a complete development history.

Built on [LangGraph](https://langchain-ai.github.io/langgraph/). See:

- [`PRD.md`](PRD.md) — product requirements
- [`autonomous_agile_multi_agent_team_phased_plan.md`](autonomous_agile_multi_agent_team_phased_plan.md) — implementation roadmap
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the code is structured

## Status — all MVP phases (0–10) landed

| Phase | Name | State |
|---|---|---|
| 0 | Architecture & environment | ✅ entities, state machine, config, event bus, project store |
| 1 | Single-agent engineering core | ✅ sandboxed tools, ReAct dev agent, LangGraph task loop, verification gate |
| 2 | Agent runtime & team roles | ✅ AgentManager, 7-role team, capability scoring, structured mailbox |
| 3 | Project state & backlog engine | ✅ persistent backlog, dependency graph, LLM backlog generation |
| 4 | Scrum Master & sprint engine | ✅ deterministic sprint planning + assignment, replanning, blocked-task revival |
| 5 | Multi-agent development | ✅ orchestrator sequences a sprint by dependency, per-agent context |
| 6 | Git & integration pipeline | ✅ branch-per-task, reviewer agent, merge with conflict + regression detection |
| 7 | Testing & verification | ✅ task-aware completion gate, test runner, optional LLM judge |
| 8 | Standups / review / retrospective | ✅ per-tick standups, sprint review, retro with carried-forward action items |
| 9 | Reporting & observability | ✅ timeline / daily / agent / sprint / final markdown reports |
| 10 | MVP integration & hardening | ✅ full `run()` loop, `resume()` from persisted state, pause/stop controls, TUI |

## Quick start

```bash
uv sync --extra dev
cp .env.example .env        # set AAMT_LLM_PROVIDER + a key (OpenRouter pool by default)

uv run pytest               # 63 tests, no API key needed
uv run aamt doctor          # check provider / keys / git
uv run aamt tui             # the AGENT.OS dashboard

# hand the team a problem statement:
uv run aamt build -p "Build a REST API for a task list with auth and SQLite" \
                  -r https://github.com/you/your-repo.git --max-sprints 4
uv run aamt report --kind final -o REPORT.md
```

## Package layout

```
src/aamt/
  config.py        env-driven settings (OpenRouter key rotation, phase toggles)
  models/          Project, Agent, Task, Sprint, Event, Decision, Standup + state machine
  events/          append-only SQLite event bus (audit trail + resumability)
  state/           project state store + backlog/dependency engine (cycle detection)
  llm/             provider-agnostic chat model + rotating OpenRouter key pool
  tools/           path-jailed workspace, shell, git, test runner
  agents/          BaseAgent, DeveloperAgent, AgentManager, Mailbox, ScrumMaster
  planning/        LLM backlog generation + deterministic sprint planner
  runtime/         LangGraph task-execution graph + objective verification gate
  integration/     reviewer agent + branch merge (conflict / regression aware)
  ceremonies/      standup + retrospective engines
  reporting/       markdown report generators
  orchestrator/    full project lifecycle: create → backlog → sprints → reports
  tui/             AGENT.OS Textual dashboard
  cli.py           typer entrypoint (doctor, run-task, plan, build, resume-run, report, tui, pause/stop)
```
