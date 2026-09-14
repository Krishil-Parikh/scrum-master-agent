---
description: Refactor code while preserving existing behavior
agent: architect
---

Refactor the following with behavior held constant unless explicitly told
otherwise: $ARGUMENTS

See the [Refactoring](../skills/refactoring/SKILL.md) skill for the full
rules this command enforces. The defining constraint of this command is
in its name: this is a behavior-preservation exercise, not a feature
change wearing a refactor's clothes. If the request actually wants new
behavior alongside the restructuring, say so explicitly and treat it as
two separate changes — a refactor, then a feature — even if they end up
in the same session.

1. If the refactor is non-trivial, consult deep-thinker on the target
   design and tradeoffs before touching code — what's the concrete
   problem with the current structure (hard to test, hard to extend, hard
   to understand), and does the proposed target actually fix it, or just
   move the same problem somewhere else?
2. Hand the plan to builder. Hard rule: behavior must remain equivalent
   unless this request explicitly asked for a behavior change. If the
   existing code isn't already well-covered by tests, builder should
   flag that — a refactor with no characterization tests to catch a
   behavior change is a refactor without a safety net.
3. Run validator to confirm nothing broke. This matters more here than
   in a normal feature build: the entire point of a refactor is that
   external behavior is unchanged, so validator's confirmation is the
   direct evidence the refactor succeeded, not just a formality.
4. Run reviewer to confirm the refactor actually improved the code rather
   than just moving it around — reviewer should be able to name the
   concrete improvement (reduced coupling, clearer naming, removed
   duplication), not just confirm the diff is tidy.
5. Fix any issues and re-validate before reporting done. If a fix round
   introduces a behavior change of its own, treat that with the same
   suspicion as the original refactor would have gotten.
