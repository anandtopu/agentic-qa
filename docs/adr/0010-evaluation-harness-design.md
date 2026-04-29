# ADR-0010: Evaluation harness design — custom Python harness in `packages/eval`

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead, ML eng
- **Consulted:** QA lead
- **Informed:** All eng

## Context

PRD §9.13 + Epic 2.6 require a per-agent evaluation suite with golden datasets (≥ 50 cases per agent), per-dimension scoring, and CI regression gating. Phase 3 Epic 3.5 then runs the same harness nightly with trend dashboards. The harness must:

- Run reproducibly: same dataset + same prompt version + same seeds → same scorecard.
- Support multiple agent types (Planner, Failure Classifier, Triage, Risk, etc.) — each scored on its own rubric.
- Be cheap to run (mocked tools, cached LLM responses where appropriate, but real LLM calls when measuring quality).
- Produce a machine-readable scorecard that CI can diff against a baseline.

Off-the-shelf evaluation frameworks (LangSmith, Promptfoo, Ragas, OpenAI Evals) each optimise for a slightly different paradigm — RAG, chat quality, or single-agent prompts — and most bind tightly to one provider. We need full control over the scoring rubric per agent and the ability to hold the evaluation logic itself stable across model upgrades.

## Decision

A **custom Python harness in `packages/eval`** with the following design:

- **Datasets**: JSONL under `packages/eval/datasets/<agent>/<vN>.jsonl`. Each line: `{id, inputs, expected, labels, metadata}`. Versioned in git; labels (e.g. `broken_schema`, `flaky_selector`, `missing_tx`) come from PRD §9.13.
- **Cases**: dataset entries plus a per-case `scoring_spec` referencing one or more **scorers**.
- **Scorers**: pluggable `Scorer` classes, one per dimension. Examples: `JsonSchemaValid`, `FieldExactMatch`, `CategoricalAccuracy`, `LlmJudgePairwise`, `LatencyBudget`, `CostBudget`. Each returns `(score: float[0..1], rationale: str)`.
- **Runner**: orchestrates `(dataset × prompt_version × model × seed)`; uses the production `LLMClient` (ADR-0004) so cost tracking and redaction apply identically; sandboxed tool calls (mock fakes register against the real Tool Router).
- **Output**: a `Scorecard` JSON with per-case scores, aggregate per-dimension, prompt/model/dataset versions, total cost, total latency. Stable schema across runs.
- **CI gating**: `make eval` produces a Scorecard for the current branch; CI compares to the baseline Scorecard pinned on `main`; per-dimension regressions > the configured threshold fail the build.
- **Determinism knobs**: temperature 0 by default; LLM responses **not** cached during quality measurement (we measure the model, not the cache); cached during smoke runs to keep CI fast.

The harness does not depend on any production agent runtime detail beyond the `LLMClient` interface and the Tool Router contract. It can be invoked offline against any prompt change.

## Consequences

- **Positive:** total control over scoring; rubric is auditable Python, not a YAML DSL; CI gating is straightforward; works uniformly across providers; integrates with our cost accounting and redaction.
- **Negative:** more code to write and maintain than adopting a framework; we must build dataset tooling, scorer libraries, and Scorecard diffing ourselves. We accept this in exchange for evaluation logic that won't drift under our feet.
- **Neutral:** datasets live in the repo — for sensitive customer data, we'll need a per-tenant private dataset path in Phase 3; designed-for but not built in Phase 0.

## Alternatives considered

- **LangSmith** — strong UI, tightly coupled to LangChain runtime; pricing and lock-in concerns; opaque scoring logic.
- **Promptfoo** — good for prompt-level A/B; thin on multi-step agent + tool-call evaluation; YAML-based scoring is hard to grow.
- **Ragas** — RAG-specific; we have a few RAG flows (test-case retrieval) but most agents aren't RAG-shaped.
- **OpenAI Evals** — provider-coupled; rubric expressiveness limited.
- **Roll our own + use Promptfoo for prompt A/B only** — viable Phase 3 hybrid; we'll revisit when prompt experimentation (Story 3.4.2) ramps up.

## References

- PRD §9.13 (Agent evaluation suite)
- Epic 2.6 (Eval suite), Phase 3 Epic 3.4 (Prompt registry), Epic 3.5 (Continuous regression)
- ADR-0004 (LLM provider abstraction)
- `packages/eval/`
