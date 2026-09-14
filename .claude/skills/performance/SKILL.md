---
name: Performance
description: Checklist for thinking through performance -- time, space, I/O, network, database, concurrency, caching, memory, and scaling -- before or after implementation.
---

Work through the dimensions that are actually relevant to the change —
not all of these apply every time. Skip straight to the ones that matter
for the code at hand rather than mechanically running every item on
everything.

- **Time**: what's the complexity class, and does it matter at your
  actual N (not a hypothetical one)? An O(n²) algorithm is fine at n=50
  and a real problem at n=500,000 — know which one you're actually
  dealing with before "optimizing."
- **Space**: what's held in memory at once, and does it grow with input
  size? Loading a full dataset to process it when a streaming approach
  would hold a constant amount at a time is a common, easy-to-miss cost.
- **I/O**: how many round trips, and can any be batched or parallelized?
  A loop that makes one network/DB call per item (N+1) is often the
  single biggest, easiest-to-fix performance issue in a codebase.
- **Network**: payload size, chattiness, and what happens under latency
  or packet loss — does a slow network make this merely slow, or does it
  time out and fail?
- **Database**: are queries hitting an index, and do they scale with
  table size or row count returned? Check the actual query plan; a query
  that's fast on a development database with 100 rows can be a different
  query entirely against production's 10 million.
- **Concurrency**: does this hold up under simultaneous access, or does
  it assume it's the only caller? A cache, counter, or queue accessed
  from multiple requests needs an explicit answer for what happens when
  two requests hit it at the same instant.
- **Caching**: is there a cache, and what invalidates it — could that
  invalidation be wrong or late? A cache with no clear invalidation
  story is a correctness bug waiting to happen, not just a performance
  feature.
- **Memory**: any unbounded growth (queues, caches, buffers) with no cap?
  Anything that grows with user-controlled input (an unbounded queue fed
  by requests, a cache with no eviction policy) is also a resource-
  exhaustion risk — see [Security Audit](../security-audit/SKILL.md).
- **Scaling**: does this get better by adding resources, or does it hit a
  wall that needs a redesign — and how far off is that wall? A
  single-instance in-memory cache doesn't scale by adding more
  instances; it just makes each instance's view of the cache different.

## Rule

Measure before optimizing. A guess about what's slow is often wrong, and
"optimizing" the wrong thing adds complexity for no benefit — profile or
benchmark first, then fix the thing the data actually points at. Once a
fix is made, measure again to confirm it actually helped; "this should be
faster" is not the same claim as "this is faster, confirmed by
benchmark."
