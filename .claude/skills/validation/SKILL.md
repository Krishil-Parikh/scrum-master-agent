---
name: Validation
description: Defines what "done" means before something ships -- the exact set of checks to run and the report format to use.
---

## What "done" requires

1. The project builds.
2. The type checker passes.
3. The linter passes.
4. The full unit test suite passes.
5. Relevant integration tests pass.
6. The specific changed behavior has been exercised, not just inferred
   from 1-5 — running the existing suite green doesn't prove the new
   behavior works if nothing in that suite covers it yet.
7. Plausible edge cases for the change have been checked — the boundary
   the diff introduces, the empty/null case, what happens on a retry.

If any check genuinely doesn't apply to this project (no linter
configured, no integration tests exist), report it as N/A explicitly
rather than omitting it — the reader should be able to tell "not
applicable" apart from "forgot to check."

## Report format

```
VALIDATION RESULT

Build:        PASS / FAIL
Types:        PASS / FAIL
Lint:         PASS / FAIL
Unit tests:   <passed>/<total>
Integration:  PASS / FAIL / N/A

Changed behavior:
  ✓ <thing that was verified working>

Potential concern:
  ⚠ <anything undertested or fragile, short of an outright failure>

Verdict: PASS / PASS WITH WARNING / FAIL
```

Example:

```
VALIDATION RESULT

Build:        PASS
Types:        PASS
Lint:         PASS
Unit tests:   89/89
Integration:  N/A (none configured for this project)

Changed behavior:
  ✓ Empty-cart checkout now returns a 400 with a specific error message
    instead of a 500.

Potential concern:
  ⚠ No test covers what happens if the cart becomes empty mid-request due
    to a concurrent item removal.

Verdict: PASS WITH WARNING
```

## Rules

- Report reproducible failures with the exact command and output — not a
  paraphrase of what went wrong. "The build failed" is not a report;
  `npm run build` followed by the actual compiler error is.
- This is a mechanical check, not a design opinion. "It passes but I'd
  have built it differently" is a PASS here — that judgment belongs in
  [Code Review](../code-review/SKILL.md), not in a validation report.
- Use PASS WITH WARNING for real-but-non-blocking gaps rather than
  rounding up to a clean PASS or down to a FAIL — both directions hide
  information the reader needs.
- Don't let a PASS on 1-5 stand in for step 6. A green test suite with no
  test for the actual change is not evidence the change works.
