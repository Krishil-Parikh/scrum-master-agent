---
name: Testing
description: Testing philosophy -- what to cover (unit, edge cases, failure paths, regression, integration) and how to tell whether a test actually proves anything.
---

## Process

```
What can go wrong?
        ↓
What behavior guarantees exist (explicit or implicit)?
        ↓
What tests prove those guarantees?
```

Read the implementation before designing tests. Testing from the ticket
alone tests the wrong thing — the ticket describes the intent, the code
determines the actual contract (what happens on empty input, what order
things happen in, what's idempotent and what isn't).

## Coverage to aim for

- Unit tests for core logic, including the boring happy path — an
  "obvious" path still regresses if nothing pins it down.
- Edge cases: empty input, boundary values (0, -1, max value, a count
  exactly at a limit), unexpected types, concurrency.
- Failure tests: dependency errors, timeouts, malformed responses. A
  function that only works when its dependencies behave has an untested
  failure contract.
- Regression tests that encode any bug this change fixes — write the test
  so it fails against the old (buggy) behavior and passes against the
  fix; a regression test that would have passed either way isn't proving
  anything.
- Integration tests at boundaries unit tests can't see (API, DB, external
  service) — mocking the boundary can hide exactly the class of bug
  (serialization mismatch, real latency, connection exhaustion) that only
  shows up with the real thing.

## How to tell a test is real

- It fails when the behavior it claims to check is broken — actually try
  breaking the implementation (invert a condition, remove the fix) and
  confirm the test catches it, for anything non-trivial.
- It tests behavior, not implementation details that are free to change.
  Asserting on the final output is more durable than asserting on an
  internal call count or a private field, unless that internal detail is
  itself the guarantee being tested.
- `assert result is not None` or `expect(x).toBeTruthy()` against a
  complex value is not a real assertion — assert the actual expected
  shape and values.
- A guarantee you can't find a way to test should be noted explicitly, not
  quietly skipped — "I couldn't find a deterministic way to test the
  retry jitter without flaking the suite" tells the reader something a
  silently absent test doesn't.

## Anti-pattern

A test suite that's large but shallow — high line coverage, weak
assertions. Coverage percentage measures what code ran, not what was
verified; a test that executes a function without checking its output
correctly counts toward coverage and proves nothing.
