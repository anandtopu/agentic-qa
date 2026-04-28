# QAForge AI — Comprehensive Design & Implementation Plan

**Source of truth:** `AgenticQA_PRD.md`
**Status:** Pre-implementation (no code yet)
**Plan owner:** Engineering lead
**Last updated:** 2026-04-27

This document operationalises the PRD into a phase-by-phase delivery plan covering the full SDLC: discovery, design, implementation, testing, DevOps, SRE, security, documentation, launch, and ongoing maintenance. It is structured as Phases → Epics → Stories → Tasks, each with explicit Acceptance Criteria. A single global Definition of Done (DoD) applies to every story unless overridden.

---

## 0. Global Definition of Done (DoD)

Every story must satisfy ALL of the following before being marked complete. Phase-specific overrides are noted inline.

1. **Code merged** to `main` via PR with at least one peer review.
2. **CI green**: lint, type check, unit tests, integration tests (where applicable), and security scans pass.
3. **Test coverage**: ≥ 80% line coverage on new modules; critical paths have integration tests.
4. **Type safety**: Python code passes `mypy --strict` (or project-equivalent); TS code passes `tsc --noEmit`.
5. **Structured outputs validated**: any agent output bound to a Pydantic / JSON schema is fuzz-tested with at least 20 sampled inputs.
6. **Docs updated**: README, API reference (OpenAPI), `CLAUDE.md`, ADR (if architectural), and runbook (if operational) reflect the change.
7. **Observability wired**: traces, metrics, and structured logs emitted with the canonical correlation ID.
8. **Cost & latency tracked**: token usage, dollar cost, and stage latency are recorded for every agent or tool invocation.
9. **Secret redaction verified**: a redaction unit test asserts secrets do not appear in logs or artifacts.
10. **Feature-flagged** if user-facing and not yet GA; default OFF in prod.
11. **Security review** for any new external surface, auth flow, or data store.
12. **Rollback plan** documented for any change that touches DB schema, queues, or persisted artifacts.
13. **Demo recorded** (Loom / 2-min screencast) for stakeholder-visible features.

---

## Phase 0 — Foundation, Discovery & Scaffolding

**Goal:** Translate the PRD into actionable design artifacts and stand up a working dev environment before any product feature is built.
**Duration estimate:** 3–4 weeks
**Exit criteria:** A new engineer can clone the repo, run `make dev`, and hit a `/healthz` endpoint within 15 minutes.

### Epic 0.1 — Requirements Review & Stakeholder Alignment

#### Story 0.1.1 — PRD walkthrough & gap analysis
- **As a** product engineer, **I want** every PRD section reviewed by Eng + QA + Security, **so that** ambiguities are captured before design starts.
- **Tasks**
  - Schedule three 90-min PRD review sessions (functional, NFR, architecture).
  - Maintain a `docs/prd-questions.md` log of open questions.
  - Produce a signed-off `docs/scope-baseline.md` listing in-scope / out-of-scope items per MVP.
- **Acceptance Criteria**
  - All ten agent types in PRD §10.1 have a named owner.
  - Every non-functional requirement in PRD §14 has a measurable target captured in `scope-baseline.md`.
  - Zero P0 open questions remain (P1/P2 may persist with mitigation notes).

#### Story 0.1.2 — Persona-driven user journey mapping
- **As a** product manager, **I want** end-to-end user journeys for each persona (PRD §8), **so that** UX and API design align with real workflows.
- **Tasks**
  - Author `docs/journeys/{qa-engineer,developer,release-manager,hiring-manager}.md`.
  - For each journey, list trigger → steps → expected agent outputs → success metric.
- **Acceptance Criteria**
  - Each journey ties to at least one PRD-defined success metric (§19).
  - Journeys are linked from `docs/scope-baseline.md`.

#### Story 0.1.3 — Compliance & data-handling baseline
- **As a** security lead, **I want** a written data-handling policy, **so that** the platform is built compliant from day one.
- **Tasks**
  - Document data classes (PII, secrets, source code, test artifacts).
  - Define retention windows per class.
  - Document regions and residency assumptions.
- **Acceptance Criteria**
  - `docs/security/data-handling.md` is approved by the security reviewer.
  - Each data class has an encryption-at-rest and in-transit decision recorded.

---

### Epic 0.2 — System Design & ADRs

#### Story 0.2.1 — High-level architecture diagram
- **Tasks**
  - Produce C4 diagrams (context, container, component) for the four planes (Control, Execution, Intelligence, Evaluation).
  - Capture as Mermaid in `docs/architecture/`.
- **Acceptance Criteria**
  - Each diagram lists owning team and data flows.
  - Diagrams are reviewed against PRD §15 system architecture.

#### Story 0.2.2 — Foundational ADRs
- **Tasks (one ADR each in `docs/adr/NNNN-title.md`)**
  - ADR-0001: Backend language & framework (Python + FastAPI per PRD §17).
  - ADR-0002: Agent orchestration (LangGraph vs. custom state machine).
  - ADR-0003: Workflow engine (Celery vs. Temporal).
  - ADR-0004: LLM provider abstraction & default model.
  - ADR-0005: Object storage (MinIO local, S3/GCS prod).
  - ADR-0006: Frontend stack (Next.js + Tailwind).
  - ADR-0007: Multi-tenancy model (row-level vs. schema-level).
  - ADR-0008: Secrets management (Vault / cloud KMS).
  - ADR-0009: Telemetry stack (OpenTelemetry + Grafana).
  - ADR-0010: Evaluation harness design.
- **Acceptance Criteria**
  - Each ADR follows the template: Context, Decision, Consequences, Alternatives.
  - Each ADR is reviewed and linked from `docs/adr/README.md`.

#### Story 0.2.3 — Canonical data model & migrations strategy
- **Tasks**
  - Convert PRD §12 entity list into ER diagram (`docs/architecture/erd.md`).
  - Define migrations conventions (Alembic, forward-only, reversible where possible).
  - Document tenancy column placement and indexes.
- **Acceptance Criteria**
  - Every entity in PRD §12 has fields, FKs, and indexes documented.
  - Sample migration scaffold passes `alembic upgrade head` against a fresh DB.

#### Story 0.2.4 — API contract first-cut (OpenAPI)
- **Tasks**
  - Author `apis/openapi.yaml` with all groups in PRD §13 stubbed.
  - Generate Pydantic models from the spec via `datamodel-codegen`.
- **Acceptance Criteria**
  - OpenAPI lints clean (`spectral lint`).
  - Mock server (`prism mock`) responds to every endpoint.

---

### Epic 0.3 — Repository, Tooling & DevOps Bootstrap

#### Story 0.3.1 — Monorepo scaffolding
- **Tasks**
  - `git init` and create branch protection rules.
  - Layout: `apps/api`, `apps/web`, `packages/agents`, `packages/tools`, `packages/eval`, `infra/`, `docs/`.
  - Add `pyproject.toml` (uv or Poetry), `package.json` (pnpm workspaces), `Makefile`.
- **Acceptance Criteria**
  - `make help` lists targets: `dev`, `test`, `lint`, `format`, `typecheck`, `migrate`, `seed`, `eval`.
  - `make dev` brings up API + Web + Postgres + Redis + MinIO via Docker Compose.

#### Story 0.3.2 — Linting, formatting, type-checking
- **Tasks**
  - Configure `ruff`, `black`, `mypy --strict`, `eslint`, `prettier`, `tsc`.
  - Add `pre-commit` hooks running fast checks.
- **Acceptance Criteria**
  - A deliberately broken commit is rejected by pre-commit locally and by CI.

#### Story 0.3.3 — CI pipeline
- **Tasks**
  - GitHub Actions matrix: lint → typecheck → unit → integration → build images → push to GHCR.
  - Cache pip / pnpm / Playwright browsers.
- **Acceptance Criteria**
  - Cold CI run < 12 min; warm < 6 min.
  - Failing tests block merge via required check.

#### Story 0.3.4 — CD pipeline (staging)
- **Tasks**
  - Add `deploy-staging.yml` triggered on `main` merge.
  - Use Helm chart in `infra/helm/qaforge`.
- **Acceptance Criteria**
  - Staging URL serves `/healthz` with the new image SHA within 10 min of merge.

#### Story 0.3.5 — Secrets, env, and config
- **Tasks**
  - Wire `pydantic-settings` for typed config.
  - Provide `.env.example`, document each var.
  - Integrate Vault / cloud KMS for production secrets.
- **Acceptance Criteria**
  - Starting the API without a required secret yields a clear startup error naming the missing variable.

#### Story 0.3.6 — Local developer experience
- **Tasks**
  - Provide `scripts/seed.py` to populate demo workspace.
  - Provide `make playwright-install` and a hello-world Playwright spec.
  - Document IDE setup in `docs/dev/local-setup.md`.
- **Acceptance Criteria**
  - A new engineer can complete the onboarding journey in < 30 min on a clean machine.

---

### Epic 0.4 — Cross-Cutting Foundations

#### Story 0.4.1 — Observability skeleton
- **Tasks**
  - Add `structlog` JSON logging, OpenTelemetry tracing, Prometheus metrics.
  - Define correlation ID middleware (`x-qaforge-trace-id`).
  - Provision Grafana dashboards for golden signals (latency, errors, saturation, traffic).
- **Acceptance Criteria**
  - A request from the web app produces a single trace spanning Web → API → Worker → LLM call.

#### Story 0.4.2 — Cost & token accounting
- **Tasks**
  - Implement `LLMClient` wrapper that records `(provider, model, prompt_tokens, completion_tokens, usd_cost)` per call.
  - Persist to `usage_records` (PRD §12).
- **Acceptance Criteria**
  - Sum of recorded costs matches provider invoice within ±2% over a calibration week.

#### Story 0.4.3 — Secret redaction utility
- **Tasks**
  - Implement `redact(text)` covering common token patterns + workspace-defined regexes.
  - Apply at log sink, evidence writer, and report generator.
- **Acceptance Criteria**
  - Property-based tests with 1k+ generated payloads show no leakage.

#### Story 0.4.4 — Feature flag service
- **Tasks**
  - Adopt OpenFeature SDK with a local provider; pluggable for LaunchDarkly later.
  - Provide `flag_enabled("name", workspace_id)` helper.
- **Acceptance Criteria**
  - Toggling a flag in the admin UI propagates to running pods within 30s.

---

## Phase 1 — MVP 1: Core Agentic QA Workflow

**Goal:** Deliver the headline workflow end-to-end for a single workspace: PR diff → test plan → API + UI tests → failure classification → Markdown evidence report posted to PR.
**Duration estimate:** 8–10 weeks
**Exit criteria:** Demo scenario in PRD §21 runs unattended on the sample e-commerce app.

### Epic 1.1 — Workspace Management

#### Story 1.1.1 — Create / read / update workspace
- **Tasks**: CRUD endpoints, persistence, validation, audit hook.
- **AC**: 100% of fields in PRD §9.1 supported; unique `(tenant, name)` enforced.

#### Story 1.1.2 — Repository linkage
- **Tasks**: GitHub App install flow, store install ID, fetch default branch.
- **AC**: Linked repo can be read via API; unlinking revokes app access.

#### Story 1.1.3 — Environment & policy config
- **Tasks**: per-environment configs (dev/staging/prod), policy YAML editor with schema validation.
- **AC**: Policy violating schema returns 422 with field-level errors.

---

### Epic 1.2 — Requirement & Change Ingestion

#### Story 1.2.1 — PR diff ingestion
- **Tasks**: webhook handler, signature verification, diff parser, store as `requirements` rows linked to commit SHA.
- **AC**: PR opened → ingestion record visible in UI within 10 s.

#### Story 1.2.2 — User story / acceptance criteria upload
- **Tasks**: Markdown upload endpoint, parser extracts AC bullets, stores structured form.
- **AC**: 95% extraction accuracy on 50-item gold set.

#### Story 1.2.3 — OpenAPI / Postman / SQL schema ingestion
- **Tasks**: validators per format, normalised internal representation.
- **AC**: Round-trip preserves operationIds for OpenAPI; Postman variables resolved.

---

### Epic 1.3 — Test Planning Agent

#### Story 1.3.1 — Planner agent v1
- **Tasks**
  - Prompt template with PRD §9.3 output schema.
  - Tool: repo retrieval (RAG over linked repo + recent commits).
  - Tool: existing-test-case lookup.
- **AC**
  - Generates ≥ 1 test case per acceptance criterion on the gold dataset.
  - Output validates against the JSON schema 100% of the time.

#### Story 1.3.2 — Open-question detection
- **Tasks**: ambiguity classifier; surface as `open_questions[]`.
- **AC**: Recall ≥ 70% on labeled ambiguity set.

#### Story 1.3.3 — Plan review UI
- **Tasks**: diff-view of plan changes, accept/reject per case.
- **AC**: Edits persist and re-run only affected downstream steps.

---

### Epic 1.4 — API Testing Agent

#### Story 1.4.1 — OpenAPI → contract tests
- **Tasks**: pytest+httpx generator; positive + negative scaffolds.
- **AC**: Generated suite executes with zero hand-edits on a reference OpenAPI ≥ 70% of the time.

#### Story 1.4.2 — Newman runner integration
- **Tasks**: tool wrapper; capture request/response; redact secrets.
- **AC**: Runs imported Postman collections end-to-end with evidence captured.

#### Story 1.4.3 — Auth injection
- **Tasks**: per-environment credential vault references; injection middleware.
- **AC**: Tokens never appear in logs or evidence (verified by redaction test).

---

### Epic 1.5 — UI Testing Agent (Playwright)

#### Story 1.5.1 — Journey-to-Playwright generator
- **Tasks**: prompt template producing Playwright TS; locator strategy heuristics.
- **AC**: Generated spec passes `npx playwright test --list` without syntax errors 100% of the time.

#### Story 1.5.2 — Headless execution runtime
- **Tasks**: containerized runner; trace/video/screenshot capture; artifact upload to MinIO/S3.
- **AC**: Trace viewer link is included in evidence for every UI run.

#### Story 1.5.3 — Selector fragility detection
- **Tasks**: post-run analyzer flags brittle selectors; suggests `data-testid` alternatives.
- **AC**: ≥ 60% of brittle selectors in the gold set are flagged.

---

### Epic 1.6 — Execution Orchestrator

#### Story 1.6.1 — Workflow engine wiring
- **Tasks**: implement orchestrator per ADR-0003; states: `planned → executing → classifying → reporting → done`.
- **AC**: Idempotent retries; stuck workflows visible in admin UI.

#### Story 1.6.2 — Tool router & executor
- **Tasks**: typed tool registry; per-tool timeouts and resource limits.
- **AC**: A misbehaving tool cannot exceed declared CPU/RAM/wallclock.

#### Story 1.6.3 — Evidence store
- **Tasks**: write-once artifact API; SHA-256 content addressing.
- **AC**: Evidence URLs are stable and tamper-evident.

---

### Epic 1.7 — Failure Classifier (v1, rules + LLM)

#### Story 1.7.1 — Heuristic pre-classifier
- **Tasks**: rule pack for obvious cases (network timeout, 5xx pattern, selector-not-found).
- **AC**: ≥ 30% of failures classified without LLM call.

#### Story 1.7.2 — LLM classifier
- **Tasks**: prompt with structured output per PRD §9.8.
- **AC**: ≥ 75% classification accuracy on bootstrap gold set; confidence calibrated.

---

### Epic 1.8 — Markdown Evidence Report

#### Story 1.8.1 — Report renderer
- **Tasks**: Jinja-based renderer covering PRD §9.11 sections.
- **AC**: Snapshot tests across 5 fixture runs are stable.

#### Story 1.8.2 — Report storage & sharing
- **Tasks**: persist as artifact; signed URL for sharing; download from UI.
- **AC**: Reports remain accessible 90 days; access is audit-logged.

---

### Epic 1.9 — GitHub Actions Integration

#### Story 1.9.1 — Reusable workflow
- **Tasks**: publish `qaforge/qaforge-action@v1`; inputs for workspace, env, gates.
- **AC**: Sample app integrates in < 10 lines of YAML.

#### Story 1.9.2 — PR comment summarizer
- **Tasks**: collapsed-by-default comment with risk badge, top failures, evidence link.
- **AC**: Comment updates in place across pushes (no spam).

#### Story 1.9.3 — Quality gate
- **Tasks**: action exits non-zero when configured risk threshold breached.
- **AC**: Gate respects branch protection; bypass requires admin.

---

### Phase 1 Test Strategy
- **Unit**: every agent prompt has fixture-based tests.
- **Contract**: OpenAPI consumer-driven via `schemathesis`.
- **Integration**: docker-compose harness runs the full Phase-1 demo end-to-end.
- **E2E**: nightly run on the sample e-commerce app in staging.
- **Performance**: PR-analysis budget (PRD §14.5) enforced as a CI assertion.

### Phase 1 Exit Checklist
- Demo scenario (PRD §21) passes 5 consecutive runs.
- Success metrics (PRD §19) measured and recorded; gaps logged for Phase 2.
- Public demo video recorded; sample app repo published.

---

## Phase 2 — MVP 2: Production-Grade Controls

**Goal:** Make the platform safe to point at non-toy systems. Everything destructive or expensive is gated; everything is auditable, evaluatable, and cost-tracked.
**Duration estimate:** 6–8 weeks
**Exit criteria:** A real PR on a real (volunteer) repo can run with destructive DB tests behind approval gates and produce a release risk score that a release manager trusts enough to act on.

### Epic 2.1 — Human Approval Gates

#### Story 2.1.1 — Approval service
- **Tasks**: `approval_requests` table (states per PRD §9.10), API, expirations, escalations.
- **AC**: All event types in PRD §9.10 emit approval requests; unhandled requests auto-expire per policy.

#### Story 2.1.2 — Notification fan-out
- **Tasks**: Slack + email + in-app; signed approval links.
- **AC**: Approver clicking link without auth is redirected to SSO and back to original action.

#### Story 2.1.3 — Approval UI
- **Tasks**: queue view with filters; one-click approve/reject with comment.
- **AC**: Median approval latency < 5 min on the bootstrap team.

---

### Epic 2.2 — DB Validation Agent

#### Story 2.2.1 — Read-only validators
- **Tasks**: schema constraint checks, orphan detection, audit-trail verification.
- **AC**: Runs against PostgreSQL ≥ 13 with no write side effects (verified by `pg_stat`).

#### Story 2.2.2 — Pre/post snapshot diffing
- **Tasks**: row-hash diff for tables in scope; bounded by row-count budget.
- **AC**: Diff produces structured deltas; budget overruns abort with clear error.

#### Story 2.2.3 — Destructive SQL pathway
- **Tasks**: parser identifies destructive statements; routes to approval gate.
- **AC**: 100% of `DELETE/UPDATE/DROP/TRUNCATE/ALTER` statements require approval before execution.

---

### Epic 2.3 — Release Risk Scoring

#### Story 2.3.1 — Feature pipeline
- **Tasks**: assemble inputs from PRD §9.9 (test results, change set, history, ownership, security flags).
- **AC**: All ten input sources are persisted per scoring run.

#### Story 2.3.2 — Scoring model
- **Tasks**: weighted rubric v1; calibration against historical incidents.
- **AC**: Backtest ≥ 0.7 ROC-AUC vs. labeled "shipped → incident" set.

#### Story 2.3.3 — Explanation & go/no-go
- **Tasks**: surface top drivers, untested high-risk areas, recommendation.
- **AC**: Every score includes ≥ 3 drivers and a recommendation.

---

### Epic 2.4 — Audit Logging

#### Story 2.4.1 — `audit_events` write path
- **Tasks**: append-only store; per-event signing; tenant scoping.
- **AC**: Tampering with a row breaks signature verification.

#### Story 2.4.2 — Audit query API & UI
- **Tasks**: filterable timeline; export CSV/JSON.
- **AC**: Common queries (last-24h, by-actor, by-resource) return < 2 s on 10M rows.

---

### Epic 2.5 — Cost Tracking

#### Story 2.5.1 — Per-run budget enforcement
- **Tasks**: pre-flight estimate; mid-flight kill switch when budget exhausted.
- **AC**: No run exceeds workspace `max_cost_usd_per_run` by > 5%.

#### Story 2.5.2 — Cost dashboards
- **Tasks**: workspace-level cost by agent, by day, by failure class.
- **AC**: Dashboards refresh ≤ 5 min behind real time.

---

### Epic 2.6 — Agent Evaluation Suite

#### Story 2.6.1 — Golden datasets
- **Tasks**: build datasets per PRD §9.13 (broken schema, flaky selector, missing tx, etc.).
- **AC**: ≥ 50 cases per agent type, version-controlled, with labels.

#### Story 2.6.2 — Eval harness
- **Tasks**: deterministic seeds; sandboxed tool calls; per-dimension scoring (PRD §9.13 table).
- **AC**: `make eval` produces a reproducible scorecard JSON.

#### Story 2.6.3 — Eval regression gating
- **Tasks**: CI step compares branch scorecard to baseline; blocks regressions > threshold.
- **AC**: A deliberate prompt regression is caught and blocked.

---

## Phase 3 — MVP 3: Enterprise Differentiators

**Goal:** Make the platform multi-tenant, enterprise-deployable, and continuously improving on its own quality.
**Duration estimate:** 8–10 weeks

### Epic 3.1 — Multi-tenant RBAC

#### Story 3.1.1 — Tenant isolation
- **Tasks**: row-level security; per-tenant DB roles; hard isolation tests.
- **AC**: Cross-tenant access attempts return 404 (not 403) and are alerted.

#### Story 3.1.2 — Roles & permissions
- **Tasks**: roles (owner, admin, engineer, approver, viewer); permission matrix; SCIM optional.
- **AC**: Permission matrix has 100% coverage in policy tests.

#### Story 3.1.3 — SSO
- **Tasks**: OIDC + SAML; group-to-role mapping.
- **AC**: Login with Okta / Google Workspace / Entra succeeds end-to-end.

---

### Epic 3.2 — External Issue Creation (Jira / GitHub)

#### Story 3.2.1 — Jira integration
- **Tasks**: per-workspace project mapping; templated issue body.
- **AC**: Defect with confidence ≥ threshold creates Jira issue after approval; deduplicated within 24 h window.

#### Story 3.2.2 — GitHub issue / PR review integration
- **Tasks**: issue creation; PR review-comment with code-line anchoring where possible.
- **AC**: Closing the upstream issue reflects in the QAForge defect record within 60 s.

---

### Epic 3.3 — Historical Flakiness Detection

#### Story 3.3.1 — Flakiness store
- **Tasks**: per-test rolling pass-rate; 14/30/90-day windows.
- **AC**: API exposes flakiness for any test ID.

#### Story 3.3.2 — Triage hint integration
- **Tasks**: classifier consumes flakiness as a feature.
- **AC**: False-positive defect rate drops measurably vs. Phase 2 baseline (target < 15% per PRD §19).

---

### Epic 3.4 — Prompt & Version Registry

#### Story 3.4.1 — Versioned prompts
- **Tasks**: every prompt has semver, changelog, eval link.
- **AC**: Production traffic can be pinned to a specific prompt version.

#### Story 3.4.2 — A/B prompt experiments
- **Tasks**: traffic split per workspace; evaluation of online metrics.
- **AC**: Winner promotion is one-click and audit-logged.

---

### Epic 3.5 — Eval Regression Suite (continuous)

- **Tasks**: nightly eval against pinned datasets; trend dashboards; alerting on > X% drop.
- **AC**: Regression catches a planted prompt regression within one nightly cycle.

---

### Epic 3.6 — Cloud Deployment

#### Story 3.6.1 — Terraform modules
- **Tasks**: VPC, EKS/GKE, RDS, Redis, S3/GCS, secrets, IAM.
- **AC**: `terraform apply` from a fresh account produces a working environment in < 60 min.

#### Story 3.6.2 — Helm chart hardening
- **Tasks**: HPA, PDBs, network policies, pod security standards.
- **AC**: Pen-test pass clean.

#### Story 3.6.3 — Disaster recovery
- **Tasks**: RPO/RTO targets; backup/restore drills; PITR for Postgres.
- **AC**: Documented quarterly DR drill restores from backup within RTO.

---

## Phase 4 — Hardening: SRE, Security, Performance

**Goal:** Operate the platform reliably at scale. Run as if production traffic depends on it (it does).
**Duration estimate:** 4–6 weeks (parallelizable with Phase 3)

### Epic 4.1 — SLOs & Error Budgets

- **Tasks**: define per-surface SLOs (API availability ≥ 99.9%, PR analysis P95 ≤ 60s, eval success ≥ 95%); error-budget policy.
- **AC**: SLOs visible in Grafana; breach triggers freeze policy.

### Epic 4.2 — On-Call & Incident Management

- **Tasks**: PagerDuty rotation; runbooks per alert; severity matrix; post-mortem template.
- **AC**: Mock incident drill resolves within target MTTR; post-mortem published within 5 business days.

### Epic 4.3 — Reliability Patterns

- **Tasks**: circuit breakers around LLM providers; bulkheads per workspace; DLQ for failed agent tasks; idempotency keys on all mutating endpoints.
- **AC**: Chaos test (provider 500s for 5 min) keeps platform operational with degraded mode.

### Epic 4.4 — Security Hardening

- **Tasks**: threat model (STRIDE); SAST (Semgrep), SCA (Trivy/Snyk), DAST (ZAP) in CI; dependency pinning; SBOM generation; signed images (cosign); webhook signature verification end-to-end.
- **AC**: External pen-test produces zero criticals/highs.

### Epic 4.5 — Performance Engineering

- **Tasks**: load tests (k6) targeting PRD §14.5 budgets; profiling; caching (HTTP, embeddings, plan reuse).
- **AC**: All §14.5 targets met at 10× expected concurrency.

---

## Phase 5 — Documentation, Launch & Adoption

**Goal:** Make the platform legible and adoptable.
**Duration estimate:** 2–3 weeks (parallel with later phases)

### Epic 5.1 — User Documentation

- **Tasks**: getting-started, workspace setup, GitHub Actions integration, FAQ; hosted on Mintlify or Docusaurus.
- **AC**: First-run user reaches a green run in ≤ 30 min using only docs.

### Epic 5.2 — Operator Documentation

- **Tasks**: install (local & cloud), upgrade, backup/restore, troubleshooting, runbooks.
- **AC**: An ops engineer not on the build team can deploy and recover a cluster from docs alone.

### Epic 5.3 — API & SDK Reference

- **Tasks**: published OpenAPI; auto-generated TS + Python SDKs; example notebooks.
- **AC**: SDKs published to npm + PyPI under `@qaforge/*` and `qaforge-*`.

### Epic 5.4 — Portfolio Deliverables (PRD §20)

- **Tasks**: architecture diagrams, demo video, sample app, generated test plans, CI screenshots, evidence reports, risk dashboard, eval report, cost/latency benchmark, security/audit design doc.
- **AC**: All 12 deliverables checked into `docs/portfolio/` and linked from README.

### Epic 5.5 — Beta Onboarding

- **Tasks**: invite list, white-glove onboarding, weekly feedback ritual, NPS measurement.
- **AC**: ≥ 5 external workspaces active, NPS captured ≥ 4 weeks running.

---

## Phase 6 — Maintenance & Continuous Improvement

**Goal:** Keep the platform sharp once it's live. This phase has no end date; it has cadences.

### Epic 6.1 — Operational Cadences

| Cadence | Activity | Owner |
|---|---|---|
| Daily | On-call triage, dashboard sweep | SRE |
| Weekly | Eval scorecard review, cost review, flaky-test report | Eng lead |
| Bi-weekly | Backlog grooming, ADR review | Eng lead + PM |
| Monthly | Security patch sweep, dependency upgrade train, DR table-top | Security + SRE |
| Quarterly | DR full drill, threat model refresh, prompt version retirement, customer business review | Cross-functional |

### Epic 6.2 — Model & Provider Lifecycle

- **Tasks**: track new model releases (e.g., Anthropic / OpenAI / Gemini cadence); A/B against pinned prompts; promote on eval + cost win; deprecate old models with migration window.
- **AC**: A new flagship model is evaluated and a go/no-go decision is recorded within 14 days of release.

### Epic 6.3 — Feedback Loops

- **Tasks**: in-product thumbs up/down on every agent output; weekly review of low-rated outputs; convert findings into eval cases.
- **AC**: ≥ 70% of negatively-rated outputs become regression-test cases within two weeks.

### Epic 6.4 — Tech Debt & Refactoring

- **Tasks**: maintain `docs/tech-debt.md` register; allocate ≥ 15% of each sprint to debt; quarterly refactor week.
- **AC**: No P1 debt item lingers > 90 days.

### Epic 6.5 — Compliance & Audit

- **Tasks**: annual SOC 2 readiness review; quarterly access reviews; data retention sweeps.
- **AC**: Audit findings closed within agreed window.

---

## Cross-Cutting RACI (summary)

| Stream | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Product & PRD | PM | Eng director | Design, QA lead | All eng |
| Architecture & ADRs | Tech lead | Eng director | Senior eng | All eng |
| Implementation | Feature owners | Tech lead | QA, Security | PM |
| Eval & quality | ML eng | Tech lead | QA | All eng |
| SRE & on-call | SRE lead | Eng director | Tech lead | All eng |
| Security | Security lead | CTO | Tech lead, SRE | All eng |
| Docs | Tech writer + author | Tech lead | PM | All eng |
| Release & launch | Release manager | PM | Eng, SRE | Customers |

---

## Risk Register (top items)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM provider outage or pricing shift | Med | High | Multi-provider abstraction; cached plans; degraded mode |
| Hallucinated test cases damage trust | High | High | Strict structured outputs; eval gates; human review before run |
| Browser flakiness pollutes signal | High | Med | Flakiness detector; quarantine; auto-retry with backoff |
| Cost overrun on a single PR | Med | High | Pre-flight estimate + mid-run kill switch (Epic 2.5) |
| Data leakage via evidence artifacts | Low | Critical | Redaction utility (Story 0.4.3) + tests + signed URLs |
| Multi-tenant data crossover | Low | Critical | RLS + isolation tests (Story 3.1.1) |
| Eval drift unnoticed | Med | High | Nightly eval regression suite (Phase 3) |

---

## How to Use This Plan

- New work should map to a story or be added as a new story under the appropriate epic — never freelance.
- Every story merged should tick the global DoD; deviations require a recorded waiver.
- Phase exit checklists are gates, not suggestions: do not start the next phase until the current one's exit criteria are met.
- When the PRD changes, update this plan in the same PR; out-of-sync PRD vs. plan is a defect.
