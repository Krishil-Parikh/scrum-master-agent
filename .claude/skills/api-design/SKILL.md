---
name: API Design
description: Checklist for designing APIs -- naming, versioning, error shapes, pagination, idempotency, and backwards compatibility.
---

- **Naming**: consistent verbs and nouns across endpoints; a new consumer
  should be able to guess the shape of an endpoint they haven't seen yet.
  If `GET /users/:id` exists, `DELETE /users/:id` should too — not
  `POST /removeUser`. Inconsistency here compounds: every exception
  trains callers to stop guessing and start grepping the docs for every
  single call.
- **Versioning**: decide up front how a breaking change will be
  introduced (URL version, header, field deprecation window) rather than
  improvising when the first one is needed. Improvised versioning under
  time pressure tends to produce something inconsistent with whatever
  scheme gets chosen properly later.
- **Error shapes**: one consistent error format across the whole API,
  with enough detail for a caller to act on it and not so much that it
  leaks internals (stack traces, internal service names, raw database
  errors). A good error includes a stable machine-readable code alongside
  the human-readable message, so callers can branch on it without
  string-matching.
- **Pagination**: cursor-based over offset-based for anything that can
  grow or mutate while being paged through — offset pagination skips or
  duplicates rows when the underlying data changes between page
  requests, which is exactly the situation pagination is often used in
  (a live feed, a growing table).
- **Idempotency**: for anything that creates or mutates state, define
  what happens on a retried request — is it safe to call twice? A client
  that times out waiting for a response and retries shouldn't create two
  records; an idempotency key (client-generated, checked server-side) is
  the standard fix for operations that can't be made naturally idempotent.
- **Backwards compatibility**: adding an optional field is usually safe;
  renaming, removing, or changing the type of an existing one usually
  isn't — treat it as a breaking change and version accordingly. This
  includes changes that seem harmless, like tightening a previously
  unenforced validation — a client relying on the old permissive
  behavior breaks even though the field itself didn't change shape.
- **Rate limits and quotas**: if the API can be called at high volume,
  decide the limit and the response shape (429, Retry-After) as part of
  the design, not as an incident-driven patch after the first abuse case.

## Rule

Design the API from the caller's perspective first (what do they need to
express, and what would make the wrong usage hard to write by accident?),
then check it against what the server can efficiently support — not the
other way around. An API designed backward from the database schema
tends to leak implementation details the caller shouldn't have to care
about.
