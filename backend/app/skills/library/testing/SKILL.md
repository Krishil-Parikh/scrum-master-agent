---
name: testing
specialty: testing
description: Cross-specialty testing philosophy -- what to cover and how to tell a test actually proves something.
---

## Purpose
A shared testing discipline every agent (not just a dedicated QA role)
applies to its own work before calling a task done.

## Responsibilities
- Cover the happy path, edge cases, and failure paths for whatever was
  just built.
- Write regression tests for any bug a change fixes.
- Judge test quality, not coverage percentage.

## Best Practices
- Read the implementation before designing tests — testing only from the
  ticket description tests the wrong thing.
- Cover: the boring happy path, edge cases (empty input, boundary
  values, unexpected types), and failure paths (a dependency errors,
  times out, or returns something malformed).
- For anything non-trivial, actually break the implementation and
  confirm the test catches it — a test that passes whether or not the
  bug exists isn't testing that bug.

## Architecture Patterns
Unit tests for core logic in isolation; integration tests at boundaries
(API, DB, external service) that unit tests can't see because mocking
the boundary would hide exactly the bug that matters there.

## Tools
Whatever test runner the project's stack uses; a way to run tests fast
enough that running them is never the reason someone skips it.

## Coding Standards
Assert on actual expected values/shapes, not `result is not None` or
`result.toBeTruthy()` against a complex object — that proves nothing.

## Testing Practices
This skill *is* the testing practice used everywhere else in the
library — see the individual specialty skills for what to additionally
cover in their domain (e.g. auth flows for backend, migrations for
database, eval methodology for AI/ML).

## Common Failure Modes
- High coverage numbers with weak assertions (coverage theater).
- A test suite that only exercises the ticket's happy path and never the
  edge cases that actually break in production.
- Tests that assert on internal implementation details, breaking on every
  harmless refactor.

## Security Considerations
Include at least one test for the failure/rejection path of any
authorization or input-validation check — a security control with no
test proving it actually rejects the bad case is unverified, not secure.

## Examples
For a new rate-limit feature: a happy-path test (under the limit
succeeds), a boundary test (exactly at the limit), a rejection test
(over the limit returns 429), and a failure test (the backing store is
unavailable — does it fail open or closed, and is that on purpose?).
