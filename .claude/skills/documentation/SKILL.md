---
name: Documentation
description: What to document and where -- code comments vs. README vs. AGENTS.md vs. ADRs -- and how to keep docs from rotting.
---

## Where things go

- **Code comments**: explain *why*, not *what* — the code already shows
  what it does. Comment the non-obvious reason a decision was made:
  "using a linear scan here instead of the index because the index goes
  stale faster than this runs" is a comment worth having; "// increment i
  by 1" is not.
- **README**: setup, usage, and how to run/test the project. What a new
  contributor needs on day one — not a running log of every feature ever
  added, which belongs in git history, not the README.
- **AGENTS.md**: durable engineering conventions and standing rules that
  should apply to every session, not just this one change — things like
  "always run the linter before committing" or "this service's tests
  require a local Redis instance." A one-off instruction for a single
  task doesn't belong here; it clutters the file for every future
  session that reads it.
- **Architecture Decision Records (ADRs)**: decisions with real tradeoffs
  worth remembering later — what was chosen, what was rejected, and why.
  Write these when the "why not X" question is likely to come up again
  (a new team member proposing the rejected alternative, or a future
  refactor questioning whether the original constraint still holds).

## Keeping docs from rotting

- Update documentation in the same diff as the change it describes, not
  as a follow-up that quietly never happens. A doc update queued as
  "follow-up" has a well-known failure rate: close to total.
- If a doc and the code disagree, that's a bug — fix whichever one is
  wrong, don't leave the contradiction for the next reader to puzzle out.
  A stale doc is worse than no doc, because it actively misleads instead
  of leaving an honest gap.
- Prefer docs that are hard to go stale (generated references, doc
  comments next to the code, types that double as documentation) over
  ones that duplicate information that will drift — a hand-maintained
  list of API endpoints next to an OpenAPI spec that's actually enforced
  will drift from it eventually.

## A quick test for whether something needs documenting

Would a competent engineer joining the project get it wrong without being
told? If yes, it needs to be written down somewhere findable. If the code
itself makes the right behavior obvious, another paragraph explaining it
is noise, not documentation.
