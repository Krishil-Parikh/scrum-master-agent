---
name: architecture
specialty: architecture
description: Cross-specialty design checklist -- boundaries, interfaces, data flow, and failure handling.
---

## Purpose
A shared design checklist for any non-trivial structural decision,
regardless of which specialty is making it.

## Responsibilities
- Judge component boundaries and interface design before implementation
  starts, not after.
- Trace data flow end to end and identify where validation actually
  happens.
- Think through failure handling and observability up front.

## Best Practices
- A component's responsibility should be statable without "and" — if it
  needs "and," it's probably two components.
- Design the smallest interface that lets callers do what they need;
  don't leak implementation detail through it.
- Know the source of truth for any piece of state, and whether more than
  one place is allowed to believe it owns that truth (it shouldn't be).

## Architecture Patterns
Layered boundaries with a clear direction of dependency; explicit
contracts (typed interfaces, API schemas) between any two components
built by different agents.

## Tools
Whatever the project already uses for interface definition (typed
schemas, OpenAPI, protocol definitions) — reuse the existing pattern
rather than introducing a second one.

## Coding Standards
Interfaces documented at the point of definition — a caller shouldn't
need to read the implementation to know what a function promises.

## Testing Practices
Test at the boundary the design defines — if two components only talk
through a documented interface, testing that interface's contract is
higher-value than testing internals on both sides redundantly.

## Common Failure Modes
- Two components each assuming they own the same piece of state.
- A "temporary" tight coupling between components built by different
  agents that never gets revisited once it works.
- No observability designed in — a failure in production has no signal
  beyond "the feature stopped working."

## Security Considerations
Validate at the boundary where data enters a component, not just
somewhere upstream that a future caller might skip.

## Examples
Before two agents (e.g. Frontend and Backend) start building against
each other, agree on the API contract explicitly — request/response
shape, error format, auth requirements — and write it down, rather than
each side guessing and reconciling at integration time.
