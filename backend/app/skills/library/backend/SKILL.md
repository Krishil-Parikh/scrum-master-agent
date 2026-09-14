---
name: backend
specialty: backend
description: API design, service/business logic, authentication, and server-side reliability.
---

## Purpose
Build the services, APIs, and business logic that power the product —
the contract the frontend (and other services) depend on.

## Responsibilities
- REST/API endpoint design and request/response contracts.
- Business logic and validation, enforced server-side regardless of what
  the client already checked.
- Authentication and authorization.
- Integration with the database layer and external services.

## Best Practices
- Validate all input at the boundary — never trust a client-supplied
  value, including ones the client already validated.
- One consistent error response shape across the whole API.
- Design idempotency for anything that creates or mutates state (see the
  API Design considerations below) — a retried request shouldn't double
  an effect.
- Keep business logic out of route handlers; handlers parse/validate/call
  a service function/return — the logic itself is testable without HTTP.

## Architecture Patterns
- Layered: routes → services/business logic → data access. Each layer
  only talks to the one below it.
- Dependency injection for things like the DB session and current user,
  so handlers/services are testable without a running server.

## Tools
Whatever the project's chosen framework is (FastAPI/Express/Django/etc.),
a migration tool for the schema, and a test client that can hit routes
without a real network call.

## Coding Standards
Explicit typed request/response models. No bare dict passing across
layer boundaries. Errors raised with a specific type/code, not a generic
exception with a string message.

## Testing Practices
Unit test business logic directly; integration test the actual HTTP
routes for auth, validation, and the real request/response shape.

## Common Failure Modes
- Authorization checked against "is *a* user logged in" instead of "does
  *this* user own this resource" — see the [Security](../security/SKILL.md)
  skill.
- No idempotency on a create endpoint — a network retry creates duplicate
  records.
- Swallowing an exception into a generic 500 with no detail, making the
  bug invisible in logs.

## Security Considerations
Parameterize all queries (never string-concatenate user input into SQL).
Rate-limit anything expensive or public. Never log secrets or full
request bodies that might contain credentials.

## Examples
A `POST /tasks` endpoint: validate the payload against a typed model,
check the caller is authorized to create a task in that project, call
`task_service.create(...)`, return the created resource with a 201 — the
route handler itself is a handful of lines.
