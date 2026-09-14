---
description: Run the full verification suite and report pass/fail with no fixes
agent: validator
subagent: false
---

Run the complete verification suite for $ARGUMENTS (or the whole project
if empty): build, type checking, linting, unit tests, and any relevant
integration tests. Report a structured PASS/FAIL result per check, list
any reproducible failures with enough detail to act on (exact command,
exact output — not a paraphrase), and flag untested edge cases as
warnings rather than silently ignoring them. Do not modify any files.

This is the lightest-weight command in the set — it invokes validator
directly rather than going through architect, so there's no
decomposition, no review, and no fix loop. Use it when you just want to
know the current state of the project (after pulling someone else's
branch, before starting work, as a quick sanity check mid-session)
without triggering the rest of the pipeline. If the result comes back
FAIL and you want it fixed, that's a separate `/build` or direct request
to builder — this command's contract is report-only, and it stays that
way even when the failure looks trivial to fix.
