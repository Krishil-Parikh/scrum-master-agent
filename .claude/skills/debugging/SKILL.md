---
name: Debugging
description: Evidence-driven method for root-causing a bug -- reproduce, isolate a minimal failing case, form and test hypotheses, and turn the fix into a regression test.
---

## The chain

```
Symptom
  ↓
Reproduction
  ↓
Minimal failing case
  ↓
Hypotheses
  ↓
Evidence
  ↓
Root cause
  ↓
Fix
  ↓
Regression test
```

Skipping a link in this chain is how "fixes" that don't fix anything
happen — most commonly, jumping straight from symptom to fix with no
reproduction in between, which means there's no way to confirm the fix
actually did anything.

## Rules

- Reproduce it first. A bug you can't reproduce is a bug you can't
  confirm you fixed — "it seems to happen sometimes" is a starting point
  for investigation, not something to patch against blind.
- Shrink the reproduction to the smallest case that still fails — strip
  everything that isn't necessary to trigger it. A minimal case (a single
  function call with specific inputs, not a full user workflow) makes the
  next two steps dramatically faster and makes a good regression test
  almost write itself.
- Form an explicit hypothesis before changing code: "I believe X causes
  this because Y." Then find evidence for or against it — a log line, a
  debugger breakpoint, a print statement, a failing assertion at the
  suspected point — before touching the fix. A hypothesis you can't state
  in one sentence is a sign you don't understand the bug yet.
- Never ship "I think changing X should fix it" without having watched it
  actually fix the reproduction. A plausible-sounding fix for an
  unconfirmed cause is a coin flip, not a fix.
- Once fixed, write a regression test that encodes the original bug — run
  it against the pre-fix code (or reason through why it would have
  failed) to confirm it actually catches the bug, not just that it
  passes. If it can't be expressed as a test, you probably don't
  understand the root cause yet, or the bug lives somewhere untestable
  (timing, environment) that needs a different kind of safeguard
  (logging, an assertion, a monitor).

## Common failure patterns worth checking early

- Off-by-one and boundary errors (`<` vs `<=`, inclusive vs exclusive
  ranges).
- State from a previous call or request leaking into the current one
  (shared mutable state, a cache that wasn't invalidated, a global that
  should have been scoped).
- An assumption about ordering (of async operations, of iteration, of
  arrival) that isn't actually guaranteed.
- A difference between the environment where it reproduces and the one
  where it doesn't (data, config, version, load) — that difference is
  often the real clue.

## See also

For a live production incident, priorities invert — stabilize before you
understand. Use the [Incident Debugging](../incident-debugging/SKILL.md)
skill instead, then come back to this one once things are calm.
