---
description: Investigate a problem and produce an implementation plan with no code changes
agent: architect
---

Investigate the following without making any code changes: $ARGUMENTS

Use this when you want the thinking and the plan before committing to
code — a design review, a "how should we approach this" question, or a
bug whose fix isn't obvious yet. The deliverable is a document you can
read, question, and revise before anyone writes a line of implementation.
If you're confident in the approach already and just want it built, use
`/build` instead — this command deliberately stops short of that.

1. Send the problem to deep-thinker first. Do not let it propose an
   implementation — it should surface assumptions, constraints,
   alternatives, and failure modes. If the problem is actually a bug
   rather than a design question, deep-thinker should still form an
   explicit hypothesis about the cause rather than jumping to a fix.
2. Send the same problem to decomposer to sketch the shape of the work:
   tasks, dependencies, parallelizable pieces, and risk areas. This runs
   independently of deep-thinker's output — decomposer should size the
   work based on the problem as given, not on whichever alternative
   deep-thinker leans toward, since the two may disagree on approach.
3. Synthesize both outputs yourself into a single implementation plan:
   recommended approach, why it beats the alternatives deep-thinker
   raised, open risks, and the ordered task breakdown. If deep-thinker's
   recommendation and decomposer's task shape don't fit together cleanly
   (e.g. decomposer sized the wrong design), reconcile them explicitly
   rather than presenting both halves side by side unresolved.
4. Do not invoke builder, test-engineer, validator, reviewer, or auditor
   for this command — it is planning only. If the investigation surfaces
   something urgent enough to fix immediately, say so and hand it off as
   a separate, explicit next step rather than quietly sliding into
   implementation.
