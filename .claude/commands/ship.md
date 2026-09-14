---
description: Final pre-ship gate -- diff review, full verification, and security check
agent: architect
---

Run the full ship gate before this change goes out: $ARGUMENTS

This is the last checkpoint before a change is considered ready to merge
or deploy — heavier than `/review` because it's mechanical verification
plus review, and it loops back to fix anything blocking rather than just
reporting. Use it as the final step of a larger piece of work, not as a
substitute for `/build` earlier in the process.

1. Get the current diff and summarize the scope of the change — what
   files, what behavior, what it's intended to accomplish. This framing
   matters: a review of "what changed" without "what it's for" makes it
   hard for anyone to judge whether the change actually accomplishes its
   goal.
2. Run validator for build, types, lint, and tests. Treat this exactly as
   validator's own report format specifies — no shortcuts, no assuming a
   clean result from an earlier session still holds.
3. Run auditor for a security/reliability pass on the diff.
4. Run reviewer for a final correctness and quality pass.
5. If any P0 or P1 issue is found, stop and send it to builder for a fix,
   then repeat validation from step 2 — don't just re-check the one thing
   that failed; a fix can have side effects elsewhere.
6. Once everything is clean, produce a final summary: what changed, what
   was verified, what was found and fixed (including anything found and
   *not* fixed, with the reason), and the current repository status
   (branch, whether it's committed, whether it's pushed). This summary is
   the artifact someone would read before approving the ship — write it
   for that reader, not as an internal log.
