# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Repository overview

QAForge AI — an agentic software QA platform. The product spec lives in `AgenticQA_PRD.md`; the phased delivery plan lives in `docs/IMPLEMENTATION_PLAN.md`. **Treat both as authoritative.** Live progress dashboard: `docs/PROGRESS.md` (Phases 0–4 complete, Phase 5 done except 5.5 beta-onboarding, Phase 6 code surface complete except 6.1 operational cadences as of 2026-04-29).

## Common commands

All workflows route through the root `Makefile`. Run `make help` to list targets.

| Command | What it does |
|---|---|
| `make install` | `uv sync --all-packages` + `pnpm install`. |
| `make dev` | Bring up the local stack (Postgres + Redis + MinIO + API) via `infra/docker/docker-compose.yml`. |
| `make api` | Run API outside docker with `uvicorn --reload`. |
| `make test` | Run all tests. |
| `make test-unit` / `make test-int` | Unit / integration only. Integration requires `make dev`. |
| `make lint` / `make format` | `ruff` + `eslint` / `ruff format` + `prettier`. |
| `make typecheck` | `mypy --strict` over `apps` and `packages`; `tsc --noEmit` for web. |
| `make migrate` / `make seed` | Alembic upgrade / demo workspace seed (Phase 1). |
| `make eval` | Run the agent evaluation harness (Phase 2). |

Run a single test: `uv run pytest packages/redaction/tests/test_redactor.py::TestBuiltinPatterns::test_url_userinfo_is_redacted`.

## Repo layout

```
apps/api/                 FastAPI backend — Control Plane (PRD §13)
apps/web/                 Next.js dashboard (Phase 1+)
packages/agents/          Specialised agents (Planner, API, UI, DB, …)
packages/tools/           Tool wrappers (Playwright, Newman, pytest, SQL)
packages/eval/            Evaluation harness + golden datasets
packages/redaction/       Secret redaction utility used by every text sink
infra/docker/             docker-compose + Dockerfile.api
infra/helm/               Production Helm chart (Phase 3)
apis/openapi.yaml         API contract (PRD §13)
docs/adr/                 Architecture decision records
docs/architecture/        C4 diagrams + ERD
docs/journeys/            Persona user journeys
docs/IMPLEMENTATION_PLAN.md  Phased SDLC plan
docs/scope-baseline.md    What's in / out of each MVP
docs/prd-questions.md     Open questions log
docs/security/            Data handling, threat model
.github/workflows/        CI/CD
```

## Architecture (big picture)

QAForge AI is structured as four planes (PRD §11). Keep boundaries crisp — code that mixes planes is a smell.

- **Control Plane** (`apps/api`) — workspaces, users, policies, environments, approval workflows, audit logs.
- **Execution Plane** (`packages/tools`) — test runners (Playwright, Newman, pytest, SQL validators) sandboxed and resource-bounded.
- **Intelligence Plane** (`packages/agents`) — orchestration, prompt templates, retrieval, classification, risk scoring.
- **Evaluation Plane** (`packages/eval`) — golden datasets, agent scoring, regression tracking, cost/latency analytics.

Orchestration pattern (PRD §10.2): `Workflow Orchestrator → Agent Task Planner → Tool Router → Tool Executor → Evidence Store → Evaluator → Human Approval Service → Report Generator`.

The agent roster has **ten specialised agents** (Planner, API Test, UI Test, DB Validation, Integration Test, Failure Classifier, Defect Triage, Release Risk, Report, Policy Guard). Do not collapse them into a single generic agent — separation is the design.

## Non-negotiable constraints

These come from the PRD and apply to every change:

- **DB read-only by default.** Destructive SQL (`DELETE/UPDATE/DROP/TRUNCATE/ALTER`) requires a human approval gate.
- **Approval gates are required for**: destructive SQL, production-environment tests, external Jira/GitHub issue creation, release readiness approval, CI pipeline modifications, high-cost eval runs (PRD §9.10).
- **Secret redaction is mandatory** at every text sink. Use `qaforge_redaction.redact()` or a derived `Redactor`. Property-based tests in `packages/redaction/tests/test_redactor.py` are the contract — do not weaken them.
- **Per-run cost / runtime caps** are enforced by the Policy Guard agent. Defaults: `$5.00`, `30 min`. Exceeding by > 5% is a regression.
- **Every agent decision is auditable.** Tool inputs/outputs (redacted), token usage, and stage latency must be traced.
- **Risk score is evidence-based**, not vibes — inputs in PRD §9.9, with top drivers and a go/no-go.

## Working notes for future sessions

- The PRD pins JSON schemas: test plan §9.3, failure classification §9.8, policy config §10.3. Reuse verbatim.
- API surface is enumerated in PRD §13 and stubbed in `apis/openapi.yaml`. Stick to those paths.
- Data model entity list is PRD §12; ERD lives at `docs/architecture/erd.md`.
- Confirm MVP phase + plane before starting work — `docs/scope-baseline.md` is the gatekeeper.
- Architectural changes need an ADR in `docs/adr/` (template at `_template.md`).
- Open questions go in `docs/prd-questions.md`; resolve in place rather than deleting.
- The repo has no remote yet — `gh` operations and force-push concerns don't apply until one is added.
