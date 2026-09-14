---
description: Run a read-only security, reliability, and architecture audit
agent: architect
---

Audit the codebase ($ARGUMENTS if a scope was given) with no
modifications:

Use this when the goal is understanding risk, not fixing it — a health
check before a release, a due-diligence pass, or a periodic review of an
area nobody's touched in a while. Nothing in this command edits a file;
if the audit turns up something that needs fixing, that's a follow-up
`/build` or a direct request to builder, run separately and deliberately,
not an automatic next step here.

1. Run auditor for security and reliability findings (injection, auth,
   secrets, race conditions, resource exhaustion, and — where relevant —
   AI/ML-specific risks such as data leakage, evaluation contamination,
   and prompt injection). Give it the scope, not a summary of what you
   expect it to find.
2. Run reviewer for architecture and design-quality findings — maintain-
   ability, coupling, error handling, API design, test quality.
3. Run validator to report current build/type/lint/test health as a
   baseline, so the audit includes objective ground truth alongside the
   subjective findings.
4. Combine all three into one report ordered by severity (P0 first), with
   each finding attributed to which pass surfaced it. Note where auditor
   and reviewer flagged the same area from different angles — that's a
   signal worth calling out, not a duplicate to collapse away. Do not fix
   anything — this command only reports.
