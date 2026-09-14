---
description: Get an independent multi-perspective review of the current changes
agent: architect
---

Review the current changes ($ARGUMENTS if a specific scope was given,
otherwise the full diff):

Use this on a diff that already exists — your own recent work, someone
else's PR, or changes from outside this session — when you want a review
without re-running the whole build pipeline. Unlike `/build`, this
command doesn't touch builder at all; it's read-only feedback, structured
the way a thorough human review would be, from three independent angles
at once.

1. Run reviewer, test-engineer, and auditor independently and in
   parallel — each should form its judgment without seeing the others'
   output. Give all three the same diff and the same context about what
   the change is trying to do; don't let one agent's phrasing of the
   intent bias how another reads it.
2. reviewer reports on correctness, maintainability, and design quality
   with P0-NIT severity labels and file:line references.
3. test-engineer reports on test coverage gaps against the behavior
   actually implemented — not against what the ticket says, against what
   the diff actually does.
4. auditor reports on security, reliability, and data-integrity risk,
   including AI/ML-specific risks where relevant.
5. Synthesize all three into one report grouped by severity, noting any
   point where the perspectives disagree (e.g. reviewer calls something
   a minor style issue that auditor considers a real security gap) rather
   than silently resolving the disagreement in the summary. This command
   does not fix anything or send findings back to builder automatically —
   that's a deliberate next step, not an implicit one.
