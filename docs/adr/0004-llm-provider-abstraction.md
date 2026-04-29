# ADR-0004: LLM provider abstraction & default model

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** ML eng, Security
- **Informed:** All eng

## Context

PRD §17 calls for an "OpenAI/Anthropic/Gemini provider abstraction" with Pydantic structured outputs. PRD §14.1 requires graceful degradation on provider failure. PRD §14.4 + Story 0.4.2 require per-call cost and token accounting. Different agents have different cost/quality profiles:

- **High-stakes** (Planner, Failure Classifier, Defect Triage, Release Risk): correctness > latency > cost.
- **Mid-stakes** (API Test, UI Test generators): correctness ≈ latency, cost matters at scale.
- **Low-stakes / high-volume** (heuristic pre-classifier rerank, selector suggestions, summarisation): cost > latency > correctness.

Hard-coding `anthropic` SDK calls everywhere would couple cost tracking, redaction, retries, and provider failover into every agent.

## Decision

Define a single internal interface — `LLMClient` — that wraps provider SDKs and is the **only** way agents call models. The wrapper enforces:

- structured outputs via Pydantic (schema is mandatory; raw-string completions are not exposed);
- cost accounting (`provider`, `model`, `prompt_tokens`, `completion_tokens`, `usd_cost`, `latency_ms`, `correlation_id`) persisted to `usage_records` (PRD §12);
- redaction of inputs and outputs at boundaries (Story 0.4.3);
- retries with provider-aware backoff and a circuit breaker (PRD §14.1);
- fallover chain across providers per `tier` (e.g. `default → secondary` on 5xx).

Default models by tier:

| Tier | Default model | Fallback |
|---|---|---|
| `high` | `claude-opus-4-7` | `claude-sonnet-4-6` |
| `mid`  | `claude-sonnet-4-6` | `gpt-5.1` |
| `low`  | `claude-haiku-4-5` | `gpt-5.1-mini` |

Provider adapters: **Anthropic** (primary), **OpenAI**, **Gemini**. Every adapter implements the same `complete(messages, schema, tier, ...)` signature. Models are configured per-workspace and overridable per-agent in policy (PRD §10.3) — this lets workspaces pin a model for reproducibility.

Prompt caching (Anthropic / OpenAI) is enabled by default for system prompts ≥ 1024 tokens.

## Consequences

- **Positive:** one place to enforce cost caps, redaction, and audit; provider lock-in is contained; A/B model experiments (Phase 3 Epic 3.4) plug in without touching agents.
- **Negative:** the lowest common denominator across providers limits use of provider-specific features (e.g. extended thinking, file uploads) — those features must be feature-detected per-adapter, increasing wrapper complexity over time.
- **Neutral:** every new provider is a new adapter; eval (ADR-0010) must run per-adapter to catch behavioural drift across providers.

## Alternatives considered

- **LiteLLM / LangChain ChatModel** — mature unified interface, but we'd still wrap them for cost/redaction; adding a third party reduces blast radius for upstream changes only marginally and makes our cost ledger dependent on their pricing tables.
- **Direct SDK calls in each agent** — fastest to write, hardest to govern. Rejected on PRD §14.4 + §10.3.
- **Pin to a single provider (Anthropic only)** — simpler, but PRD §17 explicitly calls for multi-provider, and Phase 4 reliability work assumes a degraded-mode failover path.

## References

- PRD §10.3 (Guardrails), §14.1 (Reliability), §14.4 (Observability), §17 (Tech stack)
- Story 0.4.2 (Cost & token accounting)
- ADR-0002 (Agent orchestration runtime)
- ADR-0010 (Eval harness)
