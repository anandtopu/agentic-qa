# ADR-0002: Agent orchestration runtime — LangGraph behind a thin facade

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** ML eng
- **Informed:** All eng

## Context

PRD §10.2 prescribes the orchestration pattern (`Workflow Orchestrator → Agent Task Planner → Tool Router → Tool Executor → Evidence Store → Evaluator → Human Approval Service → Report Generator`). PRD §17 lists "LangGraph or custom state-machine orchestration" as the suggested approach. We need:

- typed nodes with structured I/O (Pydantic) so each agent's contract is checkable;
- checkpointable state so a workflow can pause for human approval (PRD §9.10) for minutes-to-hours and resume on a different worker;
- streaming token output for the UI;
- provider-neutrality (we may run Anthropic, OpenAI, Gemini under one workflow per ADR-0004);
- a path off the runtime if the upstream project changes shape.

A custom state machine is feasible but pulls in checkpointing, retry semantics, and event sourcing — work that doesn't differentiate the product.

## Decision

Use **LangGraph (>= 0.2)** as the agent orchestration runtime, wrapped behind an internal `aqao_agents.runtime` facade so consumers depend on our types, not LangGraph's. Key choices:

- One graph per workflow type (PR analysis, scheduled regression, approval-gated DB run).
- State is a Pydantic model; checkpointer is the **PostgresCheckpointSaver** (same Postgres as the Control Plane).
- Long-pause states (waiting on human approval) are persisted to `approval_requests` (PRD §12); the graph resumes via a webhook from the Approval Service rather than blocking a worker.
- Tool calls go through the typed Tool Router (separate from LangGraph's tool primitives) so resource limits and redaction are enforced regardless of runtime.

## Consequences

- **Positive:** mature ecosystem; checkpointing, streaming, and retry are off-the-shelf; aligns with PRD §17; the facade lets us swap runtimes without touching agent code.
- **Negative:** LangGraph is pre-1.0 — breaking changes are likely; we accept a quarterly upgrade tax. A thicker facade than strictly necessary today is the price of optionality tomorrow.
- **Neutral:** team needs to learn LangGraph state/edges semantics; small migration cost from any prototyping done before this ADR.

## Alternatives considered

- **Custom state machine** — full control, no runtime risk, but ~4–6 weeks to reach feature parity with LangGraph's checkpointer, retries, and streaming. Not differentiating.
- **CrewAI** — opinionated multi-agent collaboration, weak on long-pause/durable state, and harder to constrain to deterministic workflows that approvals demand.
- **AutoGen** — strong on multi-agent chat patterns, weak on the linear, gated, tool-heavy workflows we need; unclear durability story.
- **Temporal SDK as the orchestrator** — durable and battle-tested, but Temporal's programming model is workflow-as-code without a graph abstraction; wiring agent prompt/tool semantics on top of it is more code, not less. We separately use Temporal/Celery for **task-level** durability — see ADR-0003.

## References

- PRD §10.2 (Orchestration pattern), §10.3 (Guardrails)
- PRD §17 (Suggested tech stack)
- ADR-0003 (Workflow engine — task durability)
- ADR-0004 (LLM provider abstraction)
- `docs/IMPLEMENTATION_PLAN.md` Epic 1.6