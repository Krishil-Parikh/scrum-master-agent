---
name: frontend
specialty: frontend
description: UI architecture, component design, state management, and frontend delivery practices.
---

## Purpose
Build the user-facing interface: pages, components, client-side state, and
the integration contract with backend APIs.

## Responsibilities
- Component architecture and reusable UI primitives.
- Client-side state management (server state vs. UI state, kept separate).
- Forms, validation, and user input handling.
- API integration: request/response shapes, loading/error/empty states.
- Accessibility (semantic HTML, keyboard nav, contrast) and responsiveness.

## Best Practices
- Co-locate a component's markup, styles, and logic; split only when a
  piece is genuinely reused elsewhere.
- Treat server data and local UI state as different concerns — don't stuff
  fetched data into the same state bucket as "is this modal open".
- Design the empty, loading, and error state for every view, not just the
  happy path with data.
- Keep components presentational where possible; push business logic to
  hooks/services so it's testable without rendering the DOM.

## Architecture Patterns
- Container/presentational split for anything with real data fetching.
- A single typed API client layer — components never call `fetch` directly.
- Optimistic UI only where a failed rollback is cheap and clearly signaled.

## Tools
React (or the project's chosen framework), a bundler (Vite/webpack), a
component-level test runner, and whatever design system/CSS approach the
project has already established.

## Coding Standards
Consistent naming (PascalCase components, camelCase functions/vars),
props typed explicitly, no silent `any`, one component per file.

## Testing Practices
Test behavior a user can observe (renders the right thing, responds to
the right interaction) rather than implementation details like internal
state variable names.

## Common Failure Modes
- Fetching in a component with no cleanup, causing state updates after
  unmount.
- Trusting a backend contract that was never confirmed (see the
  [Backend](../backend/SKILL.md) skill on API design) and discovering the
  mismatch at integration time instead of during planning.
- Overusing global state for something only one component needs.

## Security Considerations
Never render untrusted content as raw HTML without sanitizing it. Don't
put secrets (API keys meant to be server-only) in client-side code — it
ships to every browser that loads the page.

## Examples
A login form: local state for the two fields, a single `login()` call to
the API client, explicit loading/error/success states, and a redirect on
success — no business logic (token storage, session handling) inlined
into the component itself; that belongs in an auth service/hook.
