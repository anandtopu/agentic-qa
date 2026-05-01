# Agentic QA Orchestrator

Agentic software QA platform. Ten specialised AI agents plan, execute, validate, triage, and report software testing across modern release pipelines, with human approval gates and an evaluation harness baked in.

The PRD lives at [`AgenticQA_PRD.md`](AgenticQA_PRD.md). The phased delivery plan lives at [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

## Features

**Agentic core**
- **Ten specialised agents** — Planner, API Test, UI Test, DB Validation, Integration Test, Failure Classifier, Defect Triage, Release Risk, Report, Policy Guard (PRD §10.1).
- **PR-driven workflow** — GitHub webhook → test plan → execution → evidence → PR comment + quality gate.
- **Multi-tool execution layer** — Playwright (UI), Newman + `pytest`+`httpx` (API), SQL validators (DB), each sandboxed and resource-bounded.
- **Versioned prompt registry** — A/B experiments, per-workspace pins, one-click promotion.

**Quality + control**
- **Human approval gates** — destructive SQL, production-environment runs, external issue creation, release readiness, CI changes, high-cost eval runs.
- **Evidence-based release risk scoring** — go/no-go with top drivers; inputs spelled out in PRD §9.9.
- **Failure classification** — five categories with rationale; heuristic + LLM ensemble.
- **Evaluation harness with regression gate** — golden datasets per agent, scorecards, blocks merge on regression.
- **Per-run cost + runtime caps** — pre-flight estimate, mid-flight kill switch, dashboards.

**Enterprise-grade**
- **Multi-tenant** — Postgres `FORCE ROW LEVEL SECURITY`, role matrix, OIDC + SAML SSO.
- **External issue creation** — Jira + GitHub issues / PR reviews with 24-hour dedup.
- **Historical flakiness detection** — 14 / 30 / 90-day windows fed back into the classifier.
- **Append-only signed audit log** — HMAC-SHA256, queryable and exportable.
- **Mandatory secret redaction** — applied at every text sink; property-based contract tests in `aqao_redaction`.

**Reliability + ops**
- **SRE foundations** — SLOs + error budgets, incident runbooks, postmortem template, on-call severity matrix.
- **Reliability patterns** — circuit breaker, bulkhead, DLQ, idempotency store; chaos-tested.
- **Security hardening** — STRIDE threat model, Semgrep + Trivy + ZAP in CI, SBOM + Cosign, signed webhooks.
- **OpenTelemetry pipeline** — traces (Tempo) + metrics (Prom) + logs (Loki) → Grafana.
- **Lifecycle controls** — model registry with 14-day decision SLA, 7-year audit retention lock, 90-day dormant-user access review.
- **Deploy anywhere** — Docker Compose locally; Helm + Terraform on AWS or GCP.

## What ships today

| Phase | Status | Highlights |
|---|---|---|
| 0 — Foundation | ✅ done | Repo, ADRs, OpenAPI surface, redaction, observability, feature flags. |
| 1 — Core agentic QA | ✅ done | Planner / API / UI agents, orchestrator, evidence store, classifier v1, GH Actions integration. |
| 2 — Production-grade controls | ✅ done | Approval gates, DB validation, risk scoring, audit log, cost tracking, eval harness. |
| 3 — Enterprise differentiators | ✅ done | RBAC + SSO, Jira/GitHub issues, flakiness, prompt registry, nightly eval, Helm + Terraform. |
| 4 — Hardening | ✅ done | SLOs, incident management, reliability patterns, security hardening, perf budgets. |
| 5 — Docs, launch, adoption | 🟡 4 / 5 | User + operator + API docs, SDKs, portfolio. Beta onboarding deferred until hosted. |
| 6 — Maintenance | 🟡 4 / 5 code-bearing | Model lifecycle, feedback loops, tech-debt register, retention sweep + access review. |

Verification (last run 2026-04-30): `ruff` clean, `mypy --strict` clean across **250 source files**, **728 unit tests passing**. Per-phase detail in [`docs/PROGRESS.md`](docs/PROGRESS.md); architecture diagrams in [`docs/architecture/`](docs/architecture/) and [`docs/portfolio/architecture.md`](docs/portfolio/architecture.md).

## Status

All implementation-plan phases substantively complete. Phases 0–4 done; Phase 5 has 4 of 5 epics shipped (5.5 beta onboarding deferred until a hosted environment exists); Phase 6 has 4 of 5 code-bearing epics shipped (6.2 model lifecycle, 6.3 feedback loops, 6.4 tech-debt register, 6.5 compliance code surface). Epic 6.1 is operational cadence work that lives in `/schedule`, not the repo.

Latest verification: ruff clean, mypy `--strict` clean across 247 source files, **705 unit tests passing**. Full breakdown in [`docs/PROGRESS.md`](docs/PROGRESS.md).

## Portfolio deliverables

The 12 PRD §20 deliverables live under [`docs/portfolio/`](docs/portfolio/index.md):

* [Architecture diagrams](docs/portfolio/architecture.md)
* [Demo video script + storyboard](docs/portfolio/demo-video.md)
* [Sample target application](docs/portfolio/sample-app.md)
* [Generated test plans](docs/portfolio/generated-test-plans.md)
* [CI/CD run screenshots (storyboard)](docs/portfolio/ci-runs.md)
* [Evidence reports](docs/portfolio/evidence-reports.md)
* [Failure classification examples](docs/portfolio/classification-examples.md)
* [Release risk dashboard](docs/portfolio/risk-dashboard.md)
* [Evaluation report](docs/portfolio/evaluation-report.md)
* [Cost & latency benchmarks](docs/portfolio/benchmarks.md)
* [Security & audit design](docs/portfolio/security-audit.md)
* This repository itself

## User + operator + API guides

* [User guide](docs/user/index.md) — workspace setup → first green run in ≤ 30 min.
* [Operator guide](docs/operator/index.md) — install, upgrade, backup, monitoring.
  * [Install on AWS](docs/operator/install-aws.md) — Terraform + Helm step-by-step.
  * [Install on GCP](docs/operator/install-gcp.md) — `gcloud` + Helm step-by-step.
* [API reference](docs/api/index.md) — REST surface + Python + TypeScript SDKs.

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
- [Progress dashboard](docs/PROGRESS.md) — per-phase status + verification snapshot.
- [Tech-debt register](docs/tech-debt.md) — deferred items with removal triggers.
- [ADRs](docs/adr/README.md) — architectural decisions with context.
- [Local setup](docs/dev/local-setup.md) — onboarding for new contributors.
- [Data handling](docs/security/data-handling.md) — data classes, retention, encryption.

## License

TBD.
