# ADR-0003: Workflow engine — Celery + Redis for Phase 1, revisit Temporal at scale

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** SRE, ML eng
- **Informed:** All eng

## Context

PRD §17 lists "Celery or Temporal" as the workflow runtime. The execution plane runs many short-to-medium tasks (Playwright suites, Newman runs, pytest jobs, SQL validators) and a smaller number of long-running, possibly human-paused workflows (approval-gated DB tests, release-risk scoring). PRD §14.1 demands retries with bounded attempts, idempotent run creation, and a DLQ.

Temporal is the strongest answer for durable, long-pause workflows. It is also a heavyweight operational dependency (its own DB cluster, server, UI), which is disproportionate for a Phase 1 MVP that already pauses on the **Approval Service** rather than inside the queue.

We separate two concerns:

1. **Task durability** (this ADR): retry/DLQ for tool executions and ingestion jobs.
2. **Workflow durability** (ADR-0002 + Approval Service): graph state that may pause for hours; persisted to Postgres, resumed via webhook — not a queue.

That split lets us pick the simpler tool for (1).

## Decision

Use **Celery 5.3+ with Redis 7 as broker and Postgres as result backend** for Phase 1. Concretely:

- One queue per execution domain: `api-tests`, `ui-tests`, `db-validators`, `ingest`, `eval`, `default`.
- Per-task hard time limits and per-tool resource budgets (Story 1.6.2).
- Retries: exponential backoff, max 3 attempts; failures land in a DLQ table (`agent_tasks` with status `dead_letter`).
- Idempotency: every mutating task takes a UUID idempotency key; duplicate keys are no-ops.
- No Celery beat for cron — use a Postgres-backed scheduler in `apps/api` so schedules survive worker churn.

Phase 3 cloud deployment will revisit **Temporal** for cross-cluster durability and per-workflow versioning. The seam: our workflows already run **inside** the LangGraph facade (ADR-0002), and Celery is only used for individual node execution; replacing the runner is local change.

## Consequences

- **Positive:** Redis is already in `docker-compose` for caching and rate-limiting; one less production service; Celery's Python API is familiar and well-documented; smaller cold path for new contributors.
- **Negative:** Celery's at-least-once semantics force every task author to implement idempotency carefully; long-pause "wait for human" patterns must NOT live in Celery (a stuck task holds a worker slot) — they live in the Approval Service + LangGraph checkpointer.
- **Neutral:** we accept that a Phase 3 migration to Temporal is plausible; ADR-0003 will be superseded if/when that happens.

## Alternatives considered

- **Temporal** — best fit for long durable workflows but adds a stateful service with its own DB + workers; Phase 1 doesn't yet justify the operational cost.
- **RQ (Redis Queue)** — simpler than Celery but lacks first-class scheduling, priorities, and a mature DLQ workflow.
- **Dramatiq** — clean API but smaller community; less prior art for our patterns.
- **AWS SQS + Lambda** — vendor-locks a decision we're not yet ready to make; cold starts hurt PRD §14.5 budgets.
- **Run everything inside the LangGraph runtime** — couples task durability to the graph runtime; harder to scale workers per tool independently.

## References

- PRD §14.1 (Reliability), §14.3 (Scalability), §14.5 (Performance budgets)
- ADR-0002 (Agent orchestration runtime)
- `docs/IMPLEMENTATION_PLAN.md` Epic 1.6 (Execution Orchestrator)