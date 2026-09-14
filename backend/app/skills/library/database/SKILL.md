---
name: database
specialty: database
description: Schema design, migrations, indexing, and data pipeline practices.
---

## Purpose
Own the data model: schema design, migrations, indexing, and any data
pipeline the product depends on.

## Responsibilities
- Schema design and normalization tradeoffs.
- Migrations (forward and, where practical, reverse).
- Indexing for the queries the application actually runs.
- Data integrity constraints and consistency guarantees.

## Best Practices
- Normalize to avoid update anomalies; denormalize only for a measured
  read-performance reason, not by default.
- Write migrations to be backward compatible with the currently-deployed
  code during rollout (expand/contract: add the new column/table first,
  migrate code to use it, remove the old one in a later migration).
- Index for real query patterns, verified against the actual query plan,
  not guessed at.
- Decide explicitly what happens on concurrent writes to the same row
  (optimistic locking, last-write-wins, or pessimistic locking) rather
  than leaving it to whatever the ORM defaults to.

## Architecture Patterns
- One schema, one source of truth — application code reads/writes
  through a single data-access layer, not ad hoc queries scattered
  everywhere.
- Foreign keys and constraints enforced at the database level, not only
  in application code that can be bypassed.

## Tools
Whatever migration tool the project's stack provides (Alembic, Prisma
Migrate, etc.) — migrations always go through it, never a manual schema
edit against production.

## Coding Standards
Every migration is a file under version control, reviewed like code.
Column names and types consistent across related tables.

## Testing Practices
Test migrations against a copy of realistic data shape, not just an
empty database — a migration that's fine on zero rows can fail or
silently corrupt data at scale.

## Common Failure Modes
- A migration that requires simultaneous code deploy and schema change —
  an outage waiting to happen if the two aren't perfectly synchronized.
- Missing an index on a foreign key used in every join, discovered only
  when the table grows.
- Nulls used ambiguously — sometimes meaning "unknown," sometimes
  "not applicable," with no way to tell which from the schema alone.

## Security Considerations
Least-privilege database credentials per service. Never construct SQL by
string-concatenating user input — always parameterized queries.

## Examples
Adding a required `status` column to an existing `tasks` table: add it
as nullable with a default first (deploy-compatible with old code that
doesn't know about it), backfill existing rows, then — in a later,
separate migration — tighten it to NOT NULL once all writers are updated.
