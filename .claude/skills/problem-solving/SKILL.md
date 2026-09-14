---
name: Problem Solving
description: Structured method for approaching an ambiguous or complex problem before jumping to implementation -- define the problem, surface constraints and unknowns, generate real alternatives, and state a confidence level before committing.
---

## When to use this

Before implementing anything non-obvious: a feature with more than one
reasonable design, a bug whose cause isn't clear yet, or any request
where the first idea that comes to mind might not be the right one. Skip
it for genuinely mechanical work — there's no ambiguity to resolve in
fixing a typo.

## Steps

1. **Define the problem** in one or two sentences. If you can't, that's
   the real problem — go find out what's actually being asked before
   doing anything else. "Make search better" isn't a problem statement;
   "search results for multi-word queries ignore word order, so 'red
   shoes' and 'shoes red' rank differently than users expect" is.
2. **Identify constraints** — what's genuinely fixed (compatibility,
   latency, data shape, team conventions) versus what only feels fixed.
   A surprising number of "we can't change that" constraints turn out to
   be untested assumptions — check the actual contract (read the code,
   check who else calls it) before treating a constraint as load-bearing.
3. **Identify unknowns** — what would you need to know to be confident?
   Can you find it out cheaply (read the code, check the docs, run a
   quick experiment) before guessing? An unknown that costs five minutes
   to resolve shouldn't be guessed at.
4. **Generate alternatives** — at least two real options, not a straw man
   next to your favorite. A real alternative would produce genuinely
   different code, not the same design with a different variable name.
5. **Determine the evidence required** to pick between them — a
   benchmark, a quick prototype, a look at existing usage patterns. Name
   the specific evidence, not just "more information."
6. **Select an approach** and say why, specifically — not "this seems
   better" but "this handles X, which the alternative doesn't, and X
   matters because Y." A reason that would also justify the alternative
   isn't actually a reason.
7. **State your confidence** and the one thing that would change your
   mind — a benchmark result, a constraint discovered to be softer than
   assumed, a scale number 10x off from the estimate.

## Anti-pattern

Jumping to "here's the code" on step 1. If the first thing you produce is
a diff, the problem wasn't explored — it was assumed. A close cousin:
generating alternatives that are all trivially bad except your preferred
one — that's not a comparison, it's a justification written backward from
a conclusion you'd already reached.

## Relationship to other skills

This is the general method; [Debugging](../debugging/SKILL.md) is the
same discipline applied specifically to root-causing a bug (hypothesis →
evidence → confirmed cause), and
[Task Decomposition](../task-decomposition/SKILL.md) picks up after step 6
here to turn the chosen approach into an ordered, dependency-aware plan.
