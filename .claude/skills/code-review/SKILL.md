---
name: Code Review
description: Methodology for reviewing a diff -- what to check, how to phrase findings, and the severity taxonomy to classify them with.
---

## What to check

- Correctness beyond what tests cover — logic errors, off-by-ones, wrong
  assumptions about input shape (null, empty, duplicate, out-of-order,
  unexpectedly large).
- Maintainability — naming, structure, whether the next person can follow
  it without you. If understanding a function requires you to hold five
  other functions in your head at once, that's a maintainability finding
  even if the logic is correct.
- Coupling and abstraction boundaries — does this component reach into
  another's internals instead of going through its interface? Does the
  interface itself leak implementation detail a caller shouldn't need?
- Race conditions and shared-state bugs — anything read and written from
  more than one place, especially across async boundaries or concurrent
  requests.
- Error handling: loud and specific, or silent and vague? `catch (e) {}`
  and `except: pass` are findings, not style choices, because they erase
  the exact information a future debugger needs.
- API design and backwards compatibility — see
  [API Design](../api-design/SKILL.md) for the fuller checklist.
- Unnecessary changes riding along with the real diff — reformatting,
  unrelated renames, a "while I'm here" cleanup that makes the actual
  change harder to review.
- Test quality, not test coverage percentage — see [Testing](../testing/SKILL.md).
  A high coverage number with weak assertions proves nothing.

## Severity taxonomy

```
P0   — catastrophic: data loss, security hole, breaks prod
P1   — serious bug: wrong behavior in a real path
P2   — should fix: real but non-urgent problem
P3   — improvement: worth doing, not blocking
NIT  — optional / style
```

A rough way to calibrate: would you block a merge on this? P0/P1 — yes,
always. P2 — usually, unless there's real time pressure and it's tracked
as follow-up. P3/NIT — no, but worth saying so the author can weigh it.

## Finding format

Every finding needs a file, a line, and a concrete scenario — not an
adjective:

```
P1
src/cache.ts:87
Race condition between invalidate() and refresh().
Scenario: T1 reads stale value in refresh(); T2 invalidates; T1 writes the
stale value back.
Suggested fix: version-stamp cache entries; reject writes older than the
current stamp.
```

"Could be cleaner" is not a finding. If you can't point at a line and
describe what actually goes wrong, hold off until you can — or label it
explicitly as a style preference (NIT) rather than dressing it up with a
severity it hasn't earned.

## When there's nothing to report

A clean diff is a real result. Say "no findings" plainly rather than
manufacturing a low-severity issue to look thorough — a review that
always finds something, regardless of how clean the code is, stops being
useful signal.

## Note

This is a review of design and correctness, not of whether the build,
tests, and linter pass — that's a separate, mechanical check (see the
[Validation](../validation/SKILL.md) skill). Don't restate validator's
result here, and don't let a passing build substitute for actually
reading the diff.
