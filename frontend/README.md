# AI Dev Pod — Frontend

A live dashboard for the AI Agile Software Development Pod: watch the
Scrum Master and six developer agents talk, push real commits, resolve a
merge conflict, and run sprint ceremonies — in real time, over a
WebSocket — plus browse the backlog, Git history, and the project's
persistent Markdown memory.

Built with React + TypeScript + Vite. Styling is hand-written CSS (no
utility framework) organized as one shared `src/index.css` for tokens and
primitives, plus a small `.css` file alongside any component whose styling
isn't trivial.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local   # adjust VITE_API_BASE_URL if the backend isn't on :8000
npm run dev
```

Requires the backend running first (`../backend`, see its README) — the
app calls `GET /api/bootstrap` on load and then opens a WebSocket at
`VITE_WS_URL` for live updates.

## Structure

```
src/
├── api/            REST client + WebSocket message types (mirrors backend/app/schemas)
├── store/           zustand store: the single source of truth the whole UI reads from
├── hooks/            useWebSocket -- owns the live connection, feeds events into the store
├── components/
│   ├── layout/        Sidebar, TopBar (run controls), AppShell
│   ├── conversations/  the agent chat feed (also embedded on the Dashboard)
│   ├── terminal/       the live git/test output feed
│   ├── sme/             the "Question for Business SME" modal
│   ├── dashboard/       the Dashboard's bottom-row stat cards
│   └── common/           Avatar and other small shared primitives
├── pages/            one page per sidebar nav item
└── lib/               formatting helpers + a small dependency-free Markdown renderer
```

## How data flows

1. On load, `App.tsx` calls `GET /api/bootstrap` once for a full snapshot
   (project, backlog, agents, recent messages/events) and connects the
   WebSocket.
2. Every event the backend's Event Bus publishes (a task starting, a
   commit, a conflict, a chat message, a phase changing) arrives over the
   WebSocket and is applied in `store/podStore.ts` — either patched
   directly (chat messages, agent state) or used to trigger a targeted
   refetch (the backlog, SME questions) for anything too structural to
   patch safely from a single event.
3. Every page reads from that one store — there's no per-page fetching
   duplicated across the app, only a few pages (Git, Docs) that also poll
   a REST endpoint directly for data the event stream doesn't carry
   in-line (commit history, doc contents).

## Known accepted risk

`npm audit` flags one moderate advisory in `esbuild`/`vite` (dev server only
— [GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99)):
a malicious site open in the same browser could probe `npm run dev`'s
local server. Fixing it requires Vite 8, a breaking major bump this
project hasn't been tested against. It doesn't affect the production
build (`npm run build`'s output has no dev server), only `npm run dev` on
a machine that's also browsing untrusted sites at the same time — accepted
for now; revisit when Vite 8 has settled.

## Build

```bash
npm run build
```

Type-checks (`tsc -b`) then produces a static `dist/` you can serve with
any static file server, pointed at a deployed backend via
`VITE_API_BASE_URL`/`VITE_WS_URL`.
