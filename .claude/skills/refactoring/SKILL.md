---
name: Refactoring
description: Rules for refactoring safely -- behavior must stay equivalent unless explicitly asked to change, and how to prove it didn't.
---

## The hard rule

Behavior must remain equivalent unless the request explicitly asked for a
behavior change. A refactor that also quietly changes behavior is two
changes wearing one diff, and it makes both harder to review and to
revert — if something breaks later, no one can tell from the commit
whether it was the restructuring or the behavior tweak.

## Steps

1. If the code isn't already well-tested, characterize its current
   behavior with tests first — you need a way to know if you broke
   something. Characterization tests capture what the code *actually*
   does today, including quirks, not what it's supposed to do — that's
   the whole point: they're your safety net during the refactor, not a
   spec to design against.
2. Refactor in small, independently verifiable steps rather than one
   large rewrite. Each step should be small enough that if something
   breaks, you know which step did it without needing to bisect.
3. Re-run validation after each step, not just at the end — see
   [Validation](../validation/SKILL.md). Catching a break immediately
   after the step that caused it is far cheaper than catching it after
   five more steps piled on top.
4. Keep refactors and feature changes in separate diffs. If you notice a
   feature is needed mid-refactor, finish the refactor, then do the
   feature as its own change — see [Git](../git/SKILL.md) on keeping
   commits atomic.

## Signs a "refactor" isn't one

- The diff touches behavior a test doesn't cover, and no one checked
  whether that behavior changed. Silence here is not evidence of safety —
  it's an untested assumption.
- It's justified by "cleaner" or "more idiomatic" rather than a concrete
  problem (hard to test, hard to extend, hard to understand, duplicated
  in N places) the current structure causes. "Cleaner" is a description
  of the result you want, not a reason the current code needs to change —
  name the actual cost the current structure imposes.
- It changes a public interface's shape (parameters, return type, error
  behavior) "because it's better this way" — that's an API change with
  its own compatibility concerns (see
  [API Design](../api-design/SKILL.md)), not a pure refactor, even if the
  internal logic is otherwise untouched.

## A quick self-check before calling it done

Could you describe, in one sentence, the concrete problem this refactor
fixed (not "it's cleaner now" but "the old structure made X impossible to
test" or "duplicated Y in four places, so a fix had to be applied four
times")? If not, reconsider whether the refactor was worth the risk of
touching working code at all.
