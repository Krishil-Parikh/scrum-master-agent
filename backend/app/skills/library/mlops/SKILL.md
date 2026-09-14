---
name: mlops
specialty: mlops
description: Model lifecycle, training/deployment pipelines, and ML-specific operational concerns.
---

## Purpose
Own the lifecycle of any trained/fine-tuned model the project uses: data
pipeline, training, evaluation gating, deployment, and monitoring — distinct
from the AI/ML skill's focus on model *integration and feature design*.

## Responsibilities
- Training/retraining pipeline design.
- Model versioning and reproducibility (data, code, and config that
  produced a given model artifact).
- Deployment of model artifacts and rollback to a previous version.
- Monitoring for drift/degradation once a model is live.

## Best Practices
- Version the dataset and config alongside the model artifact — a model
  with no record of what produced it can't be reproduced or debugged.
- Gate deployment on an evaluation threshold, not just "training
  finished without an error."
- Keep training and inference code paths sharing the same
  preprocessing logic, so there's no train/serve skew.

## Architecture Patterns
- Pipeline stages (ingest → preprocess → train → evaluate → register →
  deploy) as separate, independently re-runnable steps, not one monolithic
  script.
- A model registry (even a simple versioned artifact store) as the
  handoff point between training and serving.

## Tools
Whatever the project's ML stack is; at minimum, a way to version
artifacts and a way to automate the retrain → evaluate → deploy loop.

## Coding Standards
Deterministic seeds where reproducibility matters. Config-driven
pipelines (no hardcoded hyperparameters buried in code) so a run is
fully described by its config.

## Testing Practices
Test the pipeline's plumbing (does preprocessing produce the expected
shape, does the training step actually consume the versioned dataset it
claims to) separately from model quality, which is an evaluation concern
covered in the [AI/ML](../ai_ml/SKILL.md) skill.

## Common Failure Modes
- Train/serve skew: preprocessing implemented twice (training vs.
  inference) and drifting apart silently.
- No rollback path when a newly deployed model underperforms in
  production.
- Silent data drift — the model keeps running, just getting steadily less
  accurate, with no signal.

## Security Considerations
Treat training data provenance as a trust boundary — poisoned or
low-quality training data is a supply-chain-style risk to the model's
behavior. Restrict who/what can trigger a production model deployment.

## Examples
A retraining pipeline: pull the latest labeled data, run the same
preprocessing module used at inference time, train, evaluate against a
held-out set, and only promote the new model to production if it beats
the current one on the evaluation metric — otherwise keep the existing
model and flag the run for review.
