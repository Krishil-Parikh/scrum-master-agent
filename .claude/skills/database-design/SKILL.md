---
name: Database Design
description: Checklist for schema and data-model decisions -- normalization tradeoffs, indexing, migrations, and consistency guarantees.
---

- **Normalization**: normalize to avoid update anomalies (the same fact
  stored in two places that can drift apart); denormalize deliberately,
  for a measured read-performance reason, not by default. "It might be
  faster" is not a measurement.
- **Indexing**: index for the queries you actually run, not the ones you
  imagine you might. Check the query plan (`EXPLAIN` or equivalent),
  don't guess — an index that looks right on paper can still be skipped
  by the query planner for reasons that only show up in the actual plan.
  Also consider the write cost: every index speeds up some reads and
  slows down every write to that table.
- **Migrations**: write them to be backward compatible with the
  currently-deployed code during rollout, and reversible where practical.
  A migration that requires simultaneous code deploy and schema change is
  an outage waiting to happen — the standard pattern is expand/contract:
  add the new column/table first (deploy compatible with both old and
  new code), migrate the code to use it, then remove the old one in a
  later, separate migration once nothing references it.
- **Consistency**: pick transaction boundaries that match the actual
  consistency requirement — not every write needs the same guarantee. A
  financial balance update needs strict consistency; an analytics
  counter usually doesn't, and forcing it into the same transaction as
  everything else adds contention for no real benefit.
- **Concurrent writes**: work out what happens when two writers touch the
  same row at once, explicitly, rather than discovering it in production —
  last-write-wins, optimistic locking (version column, reject stale
  writes), or pessimistic locking, chosen on purpose rather than by
  whatever the ORM defaults to.
- **Null handling**: decide whether a field can be null on purpose (it
  means "unknown" or "not applicable") versus null by accident (a
  migration left old rows without a value for a new required-looking
  column) — the two need very different handling in every query that
  reads it.

## Rule

A schema change is a contract change with every piece of code that reads
or writes that table — check for those callers before assuming a change
is safe (see [Dependency Analysis](../dependency-analysis/SKILL.md)). This
includes code outside the immediate PR: analytics queries, admin
scripts, and other services that read the same table directly.
