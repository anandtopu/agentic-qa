# QAForge AI

Agentic software QA platform. Ten specialised AI agents plan, execute, validate, triage, and report software testing across modern release pipelines, with human approval gates and an evaluation harness baked in.

The PRD lives at [`AgenticQA_PRD.md`](AgenticQA_PRD.md). The phased delivery plan lives at [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

## Status

Phase 0 (foundation) in progress. The repo is scaffolded; product features start in Phase 1.

## Quick start

Prerequisites: Python 3.12, Node 20+, Docker, `uv` (`pipx install uv`), `pnpm` (`corepack enable && corepack prepare pnpm@latest --activate`).

```bash
cp .env.example .env
make dev          # brings up Postgres, Redis, MinIO, API
curl http://localhost:8000/healthz
```

## Common commands

| Command | What it does |
|---|---|
| `make dev` | Start the local stack (Postgres + Redis + MinIO + API) via docker compose. |
| `make test` | Run unit + integration tests. |
| `make test-unit` | Run unit tests only. |
| `make lint` | `ruff check` and `eslint`. |
| `make format` | `ruff format` and `prettier --write`. |
| `make typecheck` | `mypy --strict` and `tsc --noEmit`. |
| `make migrate` | Apply Alembic migrations. |
| `make seed` | Seed a demo workspace. |
| `make eval` | Run the agent evaluation harness. |

Run a single test: `uv run pytest apps/api/tests/test_health.py::test_healthz_ok`.

## Repo layout

```
apps/api/           FastAPI backend (Control + Intelligence planes)
apps/web/           Next.js dashboard
packages/agents/    Specialised agents (Planner, API, UI, DB, …)
packages/tools/     Tool wrappers (Playwright, Newman, pytest, SQL)
packages/eval/      Evaluation harness and golden datasets
infra/docker/       Local docker compose + Dockerfiles
infra/helm/         Production Helm chart (Phase 3)
docs/adr/           Architecture decision records
docs/architecture/  C4 diagrams, ERD
apis/openapi.yaml   API contract (PRD §13)
scripts/            Dev utilities (seed, smoke checks)
```

## Docs

- [PRD](AgenticQA_PRD.md) — the product spec.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — phases, epics, stories, acceptance criteria, DoD.
- [ADRs](docs/adr/README.md) — architectural decisions with context.
- [Local setup](docs/dev/local-setup.md) — onboarding for new contributors.
- [Data handling](docs/security/data-handling.md) — data classes, retention, encryption.

## License

TBD.
