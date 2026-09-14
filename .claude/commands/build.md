---
description: Design, implement, test, and verify a change end to end
agent: architect
---

Run the full build pipeline for: $ARGUMENTS

This is the default, complete workflow for a feature or bugfix — use it
when you want the change designed, implemented, tested, verified, and
independently reviewed in one pass, not just implemented. For a smaller
change where the full pipeline is overkill (a typo, a one-line config
tweak), architect should scale down per its own "how deep to go" judgment
rather than forcing every step below.

1. Decompose the request with decomposer into ordered, dependency-aware
   tasks, with high-risk components flagged. Skip this for genuinely
   trivial, single-file changes.
2. If the problem is ambiguous, involves a real tradeoff, or touches
   architecture, consult deep-thinker before committing to an approach.
   Do this *before* decomposer if the shape of the solution itself is in
   question — decomposing the wrong design just produces a well-ordered
   plan for the wrong thing.
3. Hand the resulting plan to builder for implementation. Builder must
   make minimal, behavior-preserving changes unless the request
   explicitly calls for a redesign. Give builder the concrete constraints
   from steps 1-2, not just the original request restated.
4. builder delegates to test-engineer for unit, integration, and
   edge-case tests covering the new behavior. Don't skip this even when
   the change feels simple — that's exactly when an untested edge case
   slips through.
5. Run validator to confirm the build, type checks, lint, and tests all
   pass. A FAIL here means back to builder, not a note in the final
   summary.
6. Run reviewer and auditor independently for a quality and
   security/reliability pass. Give both the diff and the original
   request — not builder's rationale for its own choices, and not each
   other's findings.
7. Send any P0/P1 findings back to builder for fixes, then re-run
   validator. Repeat until clean or until a finding is explicitly and
   knowingly accepted rather than fixed.
8. Only report completion once validator passes and reviewer/auditor have
   no unresolved P0/P1 findings. Summarize what changed, what was
   verified, and any accepted risks — including *why* each was accepted,
   not just that it was.
