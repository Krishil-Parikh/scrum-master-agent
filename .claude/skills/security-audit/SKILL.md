---
name: Security Audit
description: Attack-focused checklist for security and reliability review -- injection, auth, secrets, SSRF, race conditions, resource exhaustion, and AI/ML-specific risks.
---

Adopt an adversarial mindset: assume the implementation is wrong and look
for evidence, rather than assuming it's fine and looking for reasons to
approve it. For every piece of input, ask "what if this weren't what I
expect?" For every happy path, ask what the unhappy path does.

## Security

- Injection: SQL, command, template, and prompt injection. Anywhere a
  string is built from user input and then interpreted (as a query, a
  shell command, a template, a model prompt), check that it's escaped or
  parameterized, not concatenated.
- Auth bypass and broken access control — check the identity actually
  used in the authorization decision. A common bug: checking that *a*
  valid user is logged in, not that *this* user owns the resource being
  accessed.
- Secrets hardcoded, logged, or leaked in error output — including
  secrets that end up in a stack trace returned to a client, or in a log
  line that gets shipped to a third-party aggregator.
- Unsafe deserialization, SSRF, path traversal. SSRF in particular:
  anywhere a server fetches a URL derived from user input, check whether
  that URL could point at an internal service.
- Known-vulnerable dependencies — check the actual version against
  advisories, not just whether the package name sounds trustworthy.

## Reliability

- Missing retries/timeouts, or retries with no backoff (a naive retry
  loop against a struggling dependency makes an outage worse, not
  better).
- Partial-failure handling — what's left inconsistent if this crashes
  halfway through a multi-step operation?
- Race conditions, deadlocks, resource exhaustion — can concurrent
  callers, or a single malicious caller, exhaust memory, connections, or
  file handles?

## Data

- Corruption paths and unsafe/irreversible migrations — does the
  migration have a rollback path, and does it hold up if interrupted
  mid-run?
- Consistency assumed but not enforced — two pieces of state that are
  supposed to stay in sync with nothing actually enforcing that.
- Duplicate writes from retried operations — is the operation idempotent?
- Missing validation at trust boundaries — request bodies, file uploads,
  webhook payloads, environment variables, anything crossing from outside
  the system to inside it.

## AI/ML-specific

- Train/test leakage and evaluation contamination, including leakage
  introduced by preprocessing steps fit on the full dataset before the
  split happened.
- Whether the evaluation methodology actually measures the claim being
  made, and whether the eval set represents the real input distribution.
- Prompt injection via retrieved documents, user input, or tool output —
  treat anything not directly authored by a trusted operator as
  potentially adversarial content aimed at the model.
- Retrieval poisoning and embedding mismatch — can a low-quality or
  malicious document rank highly, and does an embedding model version
  change silently invalidate an existing index?
- Model or provider fallback behavior under degradation — does a
  degraded response get flagged as degraded, or served indistinguishably
  from a normal one?

## Reporting

Use the same severity taxonomy and finding format as
[Code Review](../code-review/SKILL.md) — file, line, concrete scenario,
suggested fix. A finding with no reproducible scenario is a hunch — label
it as one rather than dressing it up with a severity it hasn't earned.
"No blockers found" is a legitimate, useful result on its own; don't
manufacture a low-severity finding just to have something to report.
