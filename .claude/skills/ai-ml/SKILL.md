---
name: AI/ML
description: Checklist specific to AI/ML work -- evaluation methodology, data leakage, retrieval vs. generation separation, and prompt-injection surface area.
---

- **Train/test separation**: confirm there's no leakage between splits —
  including leakage through preprocessing fit on the full dataset (e.g.
  normalization statistics, a vocabulary, or a vectorizer fit before the
  split instead of on the training fold only), or near-duplicate records
  across splits (common with scraped or augmented data).
- **Evaluation methodology**: check that the metric actually measures the
  claim being made — accuracy on a balanced synthetic eval set doesn't
  tell you precision on a real, heavily imbalanced production
  distribution — and that the eval set represents the real distribution
  of inputs, not just the convenient one that was easiest to collect.
- **Retrieval vs. generation**: evaluate retrieval quality and generation
  quality separately where possible — a good generation over bad
  retrieval can look fine end-to-end while hiding the actual failure
  point. If end-to-end quality is bad, know whether it's because the
  right context wasn't retrieved or because the model didn't use good
  context well; the fixes for those two are completely different.
- **Prompt injection surface**: anywhere retrieved documents, user input,
  or tool output reaches the model, treat it as untrusted and consider
  whether it could redirect behavior — e.g. a retrieved document
  containing text like "ignore previous instructions and instead..." that
  the model might follow if it's not clearly delineated as data rather
  than instruction.
- **Grounding**: for anything presented as fact, check whether it's
  actually grounded in retrieved/verified content or is unsupported model
  output. A response that mixes grounded and ungrounded claims with no
  visible distinction is a hallucination risk even when most of it is
  correct.
- **Fallback behavior**: define what happens when the primary model or
  provider is unavailable, rate-limited, or degraded — silent failure to
  a worse model is still a behavior change worth knowing about. Ideally
  this is visible (a flag in the response, a log line) rather than
  indistinguishable from a normal response.
- **Reproducibility**: version prompts, datasets, and eval configs
  alongside code, so a result can be reproduced or compared later. A
  benchmark number with no record of the exact prompt and eval set that
  produced it can't be meaningfully compared to a later number, even if
  the later number looks better or worse.
- **Cost and latency budget**: know the per-request cost and latency of
  each model call in the pipeline, especially for anything that chains
  multiple calls (retrieval → rerank → generation) — a design that's
  correct but 10x over budget isn't shippable as-is.

## Rule

A benchmark number without the eval methodology behind it is a claim, not
evidence. Ask what the number would look like if the methodology were
wrong — e.g. if the eval set overlapped with training data, or if the
metric rewarded a shortcut (matching keywords) rather than the actual
capability being claimed (understanding). If you can't answer that, treat
the number with real skepticism until you can.

## See also

When auditing AI/ML code specifically for security and reliability risk,
this checklist overlaps with — and should be read alongside —
[Security Audit](../security-audit/SKILL.md)'s AI/ML section.
