---
name: Git
description: Conventions for commits, branches, and history -- atomic commits, clear messages, and when to open a PR vs. commit directly.
---

## Commits

- One logical change per commit. If the message needs "and" to describe
  it, it's probably two commits. "Fix stale cache and update the README"
  is two commits even if they happened in the same sitting.
- Message: imperative mood, what changed and why, not a restatement of the
  diff. "Fix stale cache after invalidate()" beats "update cache.ts" —
  the filename is already in the diff; the message should carry
  information the diff itself doesn't.
- Don't mix a refactor and a behavior change in the same commit — see the
  [Refactoring](../refactoring/SKILL.md) skill. If a refactor was needed
  to make a fix reasonable to write, commit the refactor first (behavior
  unchanged, validated on its own), then the fix on top of it.
- A commit should leave the codebase in a working state — build passing,
  not "fix in next commit." Someone bisecting history with `git bisect`
  depends on every intermediate commit being runnable.

## Branches

- Name branches for what they do, not who's doing it or when —
  `fix/stale-cache-invalidation` over `krish-tuesday-fixes`. The former
  tells a reader what to expect from the diff before opening it.
- Never force-push a shared branch other people are actively working
  from. A force-push to your own not-yet-shared branch is fine — it's
  only destructive to history other people depend on.

## Pull requests

- The description states what changed, why, and how it was verified —
  link to (or restate) the validator result, don't just say "tested."
  "Tested" with no detail asks the reviewer to trust a claim they can't
  check; a pasted validation report lets them see exactly what ran.
- Keep PRs reviewable in size. If decomposer's task breakdown produced
  independent pieces, consider shipping them as separate PRs — a
  1,500-line PR gets a rubber-stamp review, not a real one, because no
  human (or agent) reviews 1,500 lines with the same attention as 150.

## Rebase vs. merge

- Rebase your own feature branch onto the latest target branch before
  opening or updating a PR, to keep history readable — a linear history
  is easier for `git bisect` and `git blame` to reason about than one
  tangled with merge commits from every sync.
- Don't rewrite history that's already been pushed and reviewed by
  someone else without asking first — a force-push after review
  invalidates line comments and can silently drop reviewed changes.

## Before committing on someone else's behalf

If you (an agent) are about to run `git commit` or open a PR, confirm the
change has actually been validated — see
[Validation](../validation/SKILL.md) — rather than committing first and
finding out it's broken after. A broken commit in shared history is more
expensive to clean up than the few extra minutes it takes to check first.
