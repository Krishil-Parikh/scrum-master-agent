---
name: Architecture
description: Checklist for architecture and design decisions -- component boundaries, interfaces, data flow, state management, scalability, failure handling, and observability.
---

Work through these before committing to a design, in roughly this order —
earlier categories constrain later ones, so getting boundaries wrong
tends to cascade into interface, data-flow, and state problems that are
expensive to unwind later.

## Component boundaries

- What's the single responsibility of this component? If the answer has
  "and," it's probably two components. "Handles user auth and sends
  welcome emails" is a sign the email-sending should live elsewhere.
- Where does this boundary match an existing seam in the codebase, and
  where does it cut across one? A new component that straddles an
  existing module boundary usually means either the new component or the
  old boundary is wrong.

## Interfaces

- What's the smallest interface that lets callers do what they need? A
  wide interface (returning an internal object, exposing five methods
  when two would do) invites callers to depend on details that should be
  free to change.
- Does this interface leak implementation details a caller shouldn't need
  to know — a database row shape, an internal retry count, a cache TTL?
  If the implementation changes, would every caller need to change too?

## Data flow

- Where does data enter, and is it validated at that boundary or trusted
  downstream? Every hop past the entry point that skips validation is a
  hop where an invalid assumption can silently propagate.
- Can you draw the flow in one pass without backtracking to explain a
  loop? If explaining the flow requires "oh, and then it goes back to
  step 2 sometimes," that cycle is worth naming and designing for
  explicitly, not leaving implicit.

## State management

- What's the source of truth, and is there ever more than one? Two
  places that are supposed to agree (a cache and a database, a frontend
  store and a backend model) will eventually disagree unless something
  actively keeps them in sync — say what that something is.
- What happens to in-flight state if this process restarts? Lost silently,
  replayed, or does the design make restart-safety someone else's
  problem by accident?

## Scalability

- What's the actual expected load, and does this design's bottleneck show
  up before or after that number? A design that falls over at 10x current
  load is fine if 10x is a decade away and irrelevant if it's next
  quarter — get the real number before judging the design against it.
- Does this scale by adding resources, or does it need a redesign past a
  certain point? Is that point close enough to matter? A single-writer
  bottleneck that's fine today can become the whole system's ceiling —
  know where that ceiling is before you're at it.

## Failure handling

- What's the failure mode for each external dependency (timeout, error,
  garbage response, hang)? "The API call fails" isn't specific enough —
  a timeout, a 500, and a malformed-but-200 response often need different
  handling.
- Does a partial failure leave anything in an inconsistent state? If step
  2 of a 3-step operation fails, what state are steps 1 and 3 left in,
  and does anything reconcile it?

## Observability

- If this breaks in production, what signal tells you it broke, and how
  fast? A design with no metric, log, or alert tied to its failure mode
  is a design that fails silently until a user complains.
- Can you tell *why* it failed from the logs/metrics, or only *that* it
  did? "Request failed" with no context (which request, what input, what
  the dependency returned) turns every incident into a fresh
  investigation instead of a quick lookup.

## Rule

A design that's easy to explain in these seven categories is usually a
design that's easy to build correctly. If you can't answer one of these
questions, that's not a gap in the checklist — it's a gap in the design,
and worth resolving (possibly with [Problem Solving](../problem-solving/SKILL.md)
or [Deep Thinker](../../agents/deep-thinker.md)) before committing to it.
