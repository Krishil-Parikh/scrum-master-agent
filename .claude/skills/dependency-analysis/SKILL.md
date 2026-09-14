---
name: Dependency Analysis
description: Method for understanding what a change affects before making it -- callers, shared state, and version/dependency risk.
---

## Before changing shared code

- Find every caller/usage of what you're about to change, not just the
  ones you already know about — a broad search (grep for the symbol
  name, not just the files you expect) beats memory. Memory is
  systematically biased toward the callers you touched most recently.
- Check for shared mutable state that a change in behavior could affect
  indirectly — a global, a module-level cache, a singleton — even when
  no caller directly invokes the changed function.
- If the signature or behavior of something widely used is changing,
  enumerate the call sites that need updating before starting, so the
  size of the change is known up front rather than discovered mid-way.
  Discovering call site #14 after you've already "finished" is a sign
  the search wasn't thorough enough at the start.
- Distinguish between a caller that needs to change and a caller that
  happens to still work by accident — the latter is a latent bug the
  change is about to expose, not evidence the change is safe.

## Before adding a new dependency

- Check its transitive dependencies and known vulnerabilities, not just
  the package itself — a well-maintained top-level package can still
  pull in an abandoned or vulnerable one three levels down.
- Weigh its maintenance and security surface against the amount of code
  it actually saves you — a small amount of code you own outright is
  sometimes better than a dependency you don't control, especially for
  something narrow enough to implement correctly in an afternoon.
- Check it's actively maintained (recent commits, responsive issue
  tracker, no pile of unaddressed security reports); an abandoned
  dependency is a future migration you're signing up for, usually at a
  worse time than now.
- Check license compatibility if the project has license constraints —
  this is easy to skip and expensive to discover late.

## Rule

"What does this touch?" is a question to answer before the change, not a
surprise to discover from a failing test after. When the search feels
exhaustive, it usually isn't yet — a symbol renamed in one language
convention (`camelCase`) might be referenced via a different one in
generated code, a config file, or a string-based lookup that a
type-aware search won't catch.
