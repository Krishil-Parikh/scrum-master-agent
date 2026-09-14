---
name: security
specialty: security
description: Cross-specialty adversarial checklist -- injection, auth, secrets, and resource exhaustion.
---

## Purpose
A shared adversarial checklist every agent applies to its own work,
regardless of specialty — assume the implementation is wrong and look for
the evidence, rather than assuming it's fine.

## Responsibilities
- Check for injection, broken access control, and secret leakage in
  anything that touches user input or external systems.
- Check reliability failure modes: missing timeouts, partial-failure
  handling, resource exhaustion.
- Flag, don't fix silently — a security concern found while doing
  unrelated work still goes through review, not a quiet inline patch.

## Best Practices
- Validate all input at trust boundaries — anywhere external data enters
  the system (request body, file upload, webhook, env var).
- Use the identity actually relevant to the authorization decision (this
  user owns this resource), not just "is someone logged in."
- Never hardcode, log, or return a secret in an error message.
- Parameterize queries; never build SQL, shell commands, or templates by
  string-concatenating untrusted input.

## Architecture Patterns
Defense at the boundary (validate once, on the way in) plus defense in
depth (don't assume a value is safe just because an earlier layer should
have checked it).

## Tools
Static analysis / dependency vulnerability scanners where available;
otherwise, a deliberate manual pass using the checklist below.

## Coding Standards
Explicit, typed input validation. No bare `except: pass` that swallows a
security-relevant failure silently.

## Testing Practices
Every authorization or validation check needs a test proving the
rejection path actually rejects — see the [Testing](../testing/SKILL.md)
skill.

## Common Failure Modes
- Auth bypass via trusting a client-supplied role/ID instead of the
  server-verified identity.
- Missing timeout on an external call, turning a slow dependency into a
  full outage.
- Resource exhaustion: an unbounded queue/cache fed by user-controlled
  input with no cap.

## Security Considerations
This entire skill *is* the security considerations section — apply the
checklist above to whatever's being built, and additionally check for
AI/ML-specific risk (prompt injection, retrieval poisoning) when the work
touches a model.

## Examples
Reviewing a new `PATCH /orders/:id` endpoint: confirm the handler checks
the caller owns `:id`'s order (not just that they're logged in), confirm
the update payload is validated server-side even though the frontend
already validates it, and confirm a malformed `:id` returns a clean 404
rather than a stack trace.
