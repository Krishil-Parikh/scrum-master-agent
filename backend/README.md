# AI Dev Pod — Backend

The backend for the **AI Agile Software Development Pod**: a Scrum Master
agent coordinating six specialized developer agents (Frontend, Backend,
AI/ML, DevOps, MLOps, Database) through a full Agile workflow — requirement
analysis, Business SME clarification, Agile planning, parallel development
across isolated Git branches, merge-conflict resolution, code review,
testing, and sprint ceremonies — against a real project document.

See the repo root's PRD and Phased MVP Roadmap for the full spec this
implements. This backend is a genuine, working MVP of the "MVP Success
Criterion" loop described there, not a mockup.

## Architecture

```
app/
├── main.py              FastAPI app: wires every router + the WebSocket bridge
├── config.py             Settings (env-driven), shared paths
├── schemas/               Pydantic contracts: agent, project, task, event, communication
├── llm/                   OpenRouter client (API-key pool rotation) + prompt helpers
├── agents/                BaseAgent + Scrum Master + 6 developer agents + registry
├── skills/                Shared skill library (Markdown) + dynamic loader
├── intake/                Document parsing (md/txt/pdf/docx) + Requirement Analyzer
├── memory/                Persistent project memory: JSON state + Markdown narrative
├── communication/         Event bus (pub/sub) + WebSocket fan-out
├── git_layer/              Git branch isolation (worktrees), commits, merge/conflict handling
├── tools/                  Scoped filesystem + subprocess execution (the "Tool Layer")
├── orchestration/          SME session, run control (pause/resume/stop), the full pipeline
└── api/                    FastAPI routers consumed by the frontend
scripts/run_demo.py        Run one full end-to-end project from the CLI
tests/                      pytest suite (offline by default; see below)
project_data/               Runtime: per-project JSON state + Markdown docs (gitignored)
workspace/                  Runtime: the demo project's actual Git repo + agent worktrees (gitignored)
```

Every layer is intentionally decoupled: agents don't know about FastAPI,
the Git layer doesn't know about agents, the event bus doesn't know about
the frontend. `orchestration/orchestrator.py` is the one place that wires
them together into the end-to-end flow — that's the file to read first to
understand how a project actually moves from a PRD to working code.

## Setup

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in at least one OPENROUTER_API_KEY_1
```

`git` must be on `PATH` — the Git layer shells out to the real `git` CLI
(no GitHub account or remote required; the demo project's repo lives
entirely under `workspace/` unless you set `DEMO_PROJECT_GIT_REMOTE`).

## Run the API server

```bash
uvicorn app.main:app --reload --port 8000
```

Then either drive it from the frontend (`../frontend`, see its README), or
directly:

```bash
curl -X POST http://localhost:8000/api/project/intake \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "text": "Build a ..."}'

curl -X POST http://localhost:8000/api/run/start
```

Watch progress live over the WebSocket at `ws://localhost:8000/ws`, or poll
`GET /api/bootstrap`.

## Run the full demo end-to-end from the CLI

This is the fastest way to see (and live-test against the real OpenRouter
API) the entire loop: intake → independent analysis → SME session → Agile
planning → parallel development with real Git branches and a deliberate
merge-conflict drill → testing → sprint review → retrospective.

```bash
python scripts/run_demo.py
# or with your own project brief:
python scripts/run_demo.py path/to/brief.md
```

It prints progress as it goes and a JSON summary report at the end. Inspect
the result in `project_data/<project_id>/docs/*.md` and the real Git
history under `workspace/<project_id>/repo` (`git -C workspace/<project_id>/repo log --all --oneline --graph`).

## Tests

```bash
pytest
```

The suite runs entirely offline by default (the LLM client is stubbed in
`tests/test_agents_offline.py`; `tests/test_git_manager.py` exercises a
real local git repo in a temp directory, no network). Nothing in `pytest`
spends OpenRouter credits — live-model correctness is verified separately
via `scripts/run_demo.py`.

## Configuration

See `.env.example` for every setting. The two worth knowing about:

- `OPENROUTER_MODEL` — defaults to a cheap Mistral model
  (`mistralai/mistral-small-3.2-24b-instruct`). Nothing else in the
  codebase hardcodes "mistral"; change this to point at any other
  OpenRouter model id.
- `SME_MODE` — `auto` (default) answers agent questions with an LLM
  playing the Business SME, so a full run can complete unattended;
  `human` leaves questions open for a real person to answer via
  `POST /api/sme/answer` (or the frontend's SME modal).
