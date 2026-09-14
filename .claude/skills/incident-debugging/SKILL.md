---
name: Incident Debugging
description: Response method for a live production incident -- stabilize first, understand second, and capture a postmortem once things are calm.
---

This is different from ordinary debugging: the priority order inverts.
Stopping the bleeding matters more than understanding it, at first. A
correct, well-understood fix that takes 40 minutes to write is worse than
a rollback that takes 2, if the incident is actively causing damage every
minute it continues.

## Steps

1. **Assess blast radius.** Who and what is actually affected, right now?
   All users or a subset? Read path, write path, or both? Is it getting
   worse, steady, or already self-resolving? This determines urgency and
   who needs to know.
2. **Stabilize before you root-cause.** Rollback, feature-flag, rate-
   limit, or fail over — whatever gets impact down fastest, even if you
   don't yet know why it broke. A rollback to the last known-good state
   is almost always the fastest lever available and doesn't require
   understanding the bug first.
3. **Capture evidence while it's fresh**: logs, metrics, recent deploys or
   config changes, anything that might not be there in an hour (rotated
   logs, an auto-scaled-away instance, a metrics window that ages out).
   Grab it even if you don't have time to read it yet.
4. **Identify the proximate trigger** — the thing that changed right
   before this started — even if it's not the full root cause. "The
   error rate spiked within 2 minutes of the 14:03 deploy" is enough to
   decide on a mitigation (roll back that deploy) without yet knowing
   which line in it was wrong.
5. **Communicate status at a fixed cadence** rather than going quiet while
   you dig. "Still investigating, next update in 15 minutes" is worth
   more to everyone waiting than silence followed by a surprise
   resolution — it lets people stop pinging you and lets stakeholders
   plan around the outage.
6. Once stable, switch to the [Debugging](../debugging/SKILL.md) skill for
   the actual root cause — reproduce it outside production, form a real
   hypothesis, confirm it with evidence, and turn the fix into a
   regression test.
7. **Write a blameless postmortem**: timeline (with timestamps), impact
   (who/what, for how long, roughly how many affected), root cause,
   contributing factors (what made this possible or worse — a missing
   alert, a manual step, a test gap), and concrete follow-ups with owners
   and dates — not "we'll be more careful." "We'll be more careful" fixes
   nothing; "add an alert on error rate > 1% for this endpoint, owner: X,
   by Friday" does.

## Rule

Don't let curiosity about the root cause delay mitigation. You can
understand a fire after it's out. The one exception: if you genuinely
don't know whether an available mitigation (like a rollback) is safe —
e.g. it might make things worse — that uncertainty itself needs a fast
answer, not an indefinite pause.
