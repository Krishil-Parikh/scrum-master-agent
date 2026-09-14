---
name: ai_ml
specialty: ai_ml
description: Model integration, evaluation methodology, and AI-feature design.
---

## Purpose
Design and integrate the AI/ML components of the product — model calls,
prompt or feature design, and evaluation of whether they actually work.

## Responsibilities
- Choosing between a hosted LLM call, a fine-tuned model, or a classical
  ML approach based on what the task actually needs.
- Prompt/feature engineering and structured output design.
- Evaluation: does the model's output actually satisfy the requirement?
- Defining fallback behavior when the model/provider is degraded.

## Best Practices
- Separate retrieval quality from generation quality when evaluating a
  RAG-style feature — a good generation over bad retrieval can look fine
  end-to-end while hiding the real failure point.
- Ask a cheap model for structured JSON output explicitly (schema in the
  prompt, `response_format: json_object` where supported) and parse
  defensively — cheap models drift from the schema more than expensive
  ones.
- Version prompts alongside code so a behavior change is traceable to a
  specific prompt edit, not a mystery regression.

## Architecture Patterns
- Keep the LLM client behind one interface the rest of the app calls —
  swapping models/providers shouldn't touch business logic.
- Treat model output as untrusted input to whatever consumes it next
  (don't `eval()` it, don't trust it as ground truth without validation).

## Tools
Whatever LLM provider/SDK the project uses, a lightweight eval harness
(even a handful of hand-checked example cases beats no evaluation).

## Coding Standards
Explicit types for structured model output (a Pydantic model, not a raw
dict). Timeouts and retries on every model call.

## Testing Practices
Test the code around the model call (parsing, fallback behavior, error
handling) deterministically; treat the model's actual output quality as
a separate evaluation concern, not something a unit test asserts exactly.

## Common Failure Modes
- Presenting unverified model output as fact with no grounding or
  disclaimer.
- No fallback when the model call fails or times out — the feature just
  hangs or crashes instead of degrading.
- An eval set that doesn't represent the real input distribution, making
  the reported accuracy meaningless in production.

## Security Considerations
Treat any content that reaches the model from outside the system
(user input, retrieved documents, tool output) as untrusted — it could
attempt prompt injection. Never let model output directly trigger a
privileged action without a validation step in between.

## Examples
An AI task-classification feature: define the exact label set up front,
ask the model for one of those labels as structured JSON, validate the
response against the label set before using it, and fall back to an
"unclassified" state (not a crash) if the call fails or returns garbage.
