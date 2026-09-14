---
name: Task Decomposition
description: Break a goal into an ordered, dependency-aware set of tasks with parallelizable work and risk called out by blast radius rather than difficulty.
---

## Shape of the output

```
epics
 └── tasks
      └── subtasks
           └── atomic implementation units
```

Every task carries: what depends on it, what it depends on, its risk
level, and what "done" looks like. Not every goal needs all four levels —
a small feature might only need "tasks," while a multi-team initiative
needs the full tree.

## Steps

1. State the goal in one line. If it takes a paragraph, the goal itself
   probably needs [Problem Solving](../problem-solving/SKILL.md) first to
   narrow it down.
2. List tasks in the order their dependencies require, not the order they
   occurred to you. Writing them in occurrence order and reordering after
   is fine — but the final list should reflect real dependency, not
   stream-of-consciousness.
3. Mark dependencies explicitly: `A → B → C`, `A → D`, `B + D → E`. A task
   with an implicit, unstated dependency is a task someone will start too
   early.
4. Identify what can run in parallel — anything with no shared
   dependency and no shared file/resource. Two tasks that both touch the
   same file aren't truly parallel even without a formal dependency
   between them; flag that too.
5. Classify risk by **blast radius and reversibility**, not difficulty:
   - High risk: auth, concurrency, external APIs, migrations, anything
     touching money or irreversible state (a delete with no soft-delete,
     a schema change with no rollback).
   - Low risk: UI, formatting, isolated utilities, anything easy to
     revert with a single commit revert and no follow-on cleanup.
   - A task can be both hard and low risk (a gnarly algorithm that's
     fully unit-testable and used nowhere else yet), or easy and high
     risk (a one-line change to a shared auth check). Risk and difficulty
     are independent axes — don't conflate them.
6. Write acceptance criteria per task (or per group) — concrete enough
   that someone else could verify it without asking you what you meant.
   "Works correctly" is not acceptance criteria; "returns a 404 for a
   nonexistent ID and a 200 with the updated record otherwise" is.

## Worked example

Goal: "let users export their data as CSV"

```
Tasks:
  1. Define the CSV column schema and which fields are included — depends
     on: none — risk: low
  2. Implement the export query (batched, to avoid loading the full
     dataset into memory) — depends on: 1 — risk: med (a naive
     unbatched query could OOM on a large account)
  3. Implement the CSV serialization and streaming response — depends on:
     2 — risk: low
  4. Add the export endpoint and rate-limit it (exports are expensive) —
     depends on: 3 — risk: med (missing the rate limit lets one user
     trigger repeated expensive exports)
  5. Add the "export" button and download flow in the UI — depends on: 4
     — risk: low

Parallelizable:
  - None — this is a mostly linear pipeline; task 5 could start against a
    mocked endpoint while 2-4 are in progress if the UI and backend are
    built by different people.

Acceptance criteria:
  - Exporting an account with 0 records produces a valid, empty CSV (just
    headers), not an error.
  - Exporting a large account (test with a synthetic dataset well above
    normal size) completes without memory growth proportional to record
    count.
  - A second export request while one is in-flight for the same user is
    rate-limited, not queued silently.
```

## Anti-pattern

A flat, unordered to-do list. If nothing in the list depends on anything
else, you haven't actually decomposed the problem — you've just listed
adjectives for the same blob of work. A second anti-pattern: padding the
list with busywork ("write tests for X" as its own task per file) instead
of trusting that test coverage is handled as part of implementing each
real task.
