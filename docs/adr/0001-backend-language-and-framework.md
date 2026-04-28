# ADR-0001: Backend language & framework — Python 3.12 + FastAPI

- **Status:** Accepted
- **Date:** 2026-04-27
- **Deciders:** Tech lead
- **Consulted:** Senior eng
- **Informed:** All eng

## Context

PRD §17 names Python + FastAPI as the suggested stack. The platform must
support: high-throughput async I/O (LLM provider calls, webhook fan-out),
strong typing for agent/tool contracts, first-class Pydantic structured
outputs, and SQL access via SQLAlchemy. The team's existing expertise is
Python-heavy.

The agentic ecosystem (LangGraph, OpenAI/Anthropic/Gemini SDKs, Schemathesis,
pytest, Newman wrappers) is most mature in Python.

## Decision

The backend is **Python 3.12 + FastAPI**, packaged with **uv** and built as
a uv workspace spanning `apps/api`, `packages/agents`, `packages/tools`,
`packages/eval`, and `packages/redaction`.

- Type checking: `mypy --strict`.
- Linting/formatting: `ruff` (single tool replaces black + isort + flake8).
- Validation/serialisation: Pydantic v2.
- Async runtime: `uvicorn`.
- ORM/migrations: SQLAlchemy 2.0 + Alembic.

## Consequences

- **Positive:** alignment with the PRD; mature LLM and testing libraries;
  one language across agents, API, and orchestration; uv workspaces give
  fast installs and per-package isolation.
- **Negative:** Python's GIL limits CPU-bound parallelism — the execution
  plane will rely on subprocesses (Playwright, Newman) and async I/O
  rather than threads. Cold-start latency for serverless deployment is a
  concern we'll revisit if/when we move off long-running pods.
- **Neutral:** the frontend remains TypeScript (separate ADR), so we
  accept polyglot at the repo level.

## Alternatives considered

- **Node.js + NestJS** — best-in-class for the frontend stack, but the
  agent ecosystem trails Python and Pydantic structured outputs have no
  direct analog.
- **Go + chi/echo** — superb runtime characteristics but immature LLM
  tooling and no Pydantic equivalent; would force prompt/contract code
  out of the typed core.
- **Rust + Axum** — over-fits the problem; iteration speed cost is too
  high for a Phase-1 MVP.

## References

- PRD §17 (Suggested Tech Stack)
- PRD §14.5 (Performance targets)
- `docs/IMPLEMENTATION_PLAN.md` Phase 0 Epic 0.3
