# Agentic QA Orchestrator — Progress Dashboard

**Last updated:** 2026-04-30

Single source of truth for "what's actually done." For the design
intent see [`AgenticQA_PRD.md`](../AgenticQA_PRD.md); for the phase /
epic / story breakdown see
[`docs/IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). This page
just tracks delivery against that plan.

## Headline

| Phase | Status | Notes |
|---|---|---|
| Phase 0 — Foundation, Discovery & Scaffolding | ✅ done | All four epics complete. |
| Phase 1 — MVP 1: Core Agentic QA Workflow | ✅ done | All nine epics complete. |
| Phase 2 — MVP 2: Production-Grade Controls | ✅ done | All six epics complete. |
| Phase 3 — MVP 3: Enterprise Differentiators | ✅ done | All six epics complete. |
| Phase 4 — Hardening: SRE, Security, Performance | ✅ done | All five epics complete. |
| Phase 5 — Documentation, Launch & Adoption | 🟡 4 / 5 | Epics 5.1–5.4 complete; **5.5 (beta onboarding)** is deferred until a hosted environment exists. |
| Phase 6 — Maintenance & Continuous Improvement | 🟡 4 / 5 (code-bearing) | Epics **6.2 / 6.3 / 6.4 / 6.5** code surface complete. Epic **6.1 (operational cadences)** is calendar / `/schedule` work, not code. |

The implementation plan is now substantively complete: the only
items not delivered are the ones that can't be delivered without a
hosted environment (Epic 5.5 beta onboarding, the demo recording,
the published SDK packages, the SOC-2 audit walkthrough). Each is
captured in [`tech-debt.md`](tech-debt.md) with a clear "removal
trigger" so they're easy to pick up later.

## Verification snapshot (last run 2026-04-30)

| Check | Result |
|---|---|
| `ruff check apps packages` | ✅ clean |
| `mypy --strict` (5 packages) | ✅ clean across **250 source files** |
| `pytest` unit suite | ✅ **728 passed**, 51 deselected |
| Integration suite | ⏳ not run on this machine — Docker daemon unavailable (TD-005) |

## Per-phase detail

### Phase 0 — Foundation, Discovery & Scaffolding ✅

| Epic | Status | Where |
|---|---|---|
| 0.1 Requirements review & alignment | ✅ | `docs/scope-baseline.md`, `docs/journeys/`, `docs/security/data-handling.md`, `docs/prd-questions.md` |
| 0.2 System design + ADRs | ✅ | `docs/architecture/`, `docs/adr/0001…0010`, `apis/openapi.yaml` |
| 0.3 Repo, tooling, DevOps bootstrap | ✅ | `Makefile`, `pyproject.toml`, `pnpm-workspace.yaml`, `infra/docker/` |
| 0.4 Cross-cutting foundations | ✅ | `aqao_api.observability`, `aqao_api.usage`, `aqao_redaction`, `aqao_api.flags` |

### Phase 1 — Core Agentic QA Workflow ✅

| Epic | Status |
|---|---|
| 1.1 Workspace management | ✅ workspaces, repository linkage, environments, policy |
| 1.2 Requirement ingestion | ✅ PR-diff webhook, OpenAPI / Postman / SQL-schema / user-story parsers |
| 1.3 Test Planning Agent | ✅ Planner v1, ambiguity detection, plan-review surface |
| 1.4 API Testing Agent | ✅ OpenAPI → contract tests, Newman runner, auth injection |
| 1.5 UI Testing Agent | ✅ Playwright generator, headless runtime, fragility detector |
| 1.6 Execution Orchestrator | ✅ workflow engine, tool router, evidence store |
| 1.7 Failure Classifier v1 | ✅ heuristic + LLM, structured per PRD §9.8 |
| 1.8 Markdown Evidence Report | ✅ Jinja renderer, signed-URL storage |
| 1.9 GitHub Actions integration | ✅ reusable workflow, PR comment, quality gate |

### Phase 2 — Production-Grade Controls ✅

| Epic | Status |
|---|---|
| 2.1 Human approval gates | ✅ approval service, notifier fan-out, queue UI surface |
| 2.2 DB Validation Agent | ✅ read-only validators, snapshot diff, destructive-SQL gate |
| 2.3 Release Risk Scoring | ✅ feature pipeline, weighted rubric, go/no-go + drivers |
| 2.4 Audit logging | ✅ append-only signed events, query/export API |
| 2.5 Cost tracking | ✅ pre-flight estimate + mid-flight kill switch, dashboards |
| 2.6 Agent evaluation suite | ✅ golden datasets, harness, regression gate |

### Phase 3 — Enterprise Differentiators ✅

| Epic | Status |
|---|---|
| 3.1 Multi-tenant RBAC | ✅ row-level security, role matrix, OIDC + SAML SSO |
| 3.2 External issue creation | ✅ Jira + GitHub issue / PR-review integration |
| 3.3 Historical flakiness detection | ✅ flakiness store, 14/30/90-day windows, classifier hint |
| 3.4 Prompt & version registry | ✅ versioned prompts, A/B experiments, one-click promotion |
| 3.5 Eval regression suite (continuous) | ✅ nightly eval, trend dashboards, alert on regression |
| 3.6 Cloud deployment | ✅ Terraform modules, Helm chart hardening, DR runbook |

### Phase 4 — Hardening ✅

| Epic | Status |
|---|---|
| 4.1 SLOs + error budgets | ✅ `aqao_api.slo`, `DEFAULT_SLOS` covering every PRD §14.5 capability |
| 4.2 On-call + incident management | ✅ `aqao_api.incident`, severity matrix, runbook index, postmortem template |
| 4.3 Reliability patterns | ✅ circuit breaker, bulkhead, DLQ, idempotency store; chaos AC verified |
| 4.4 Security hardening | ✅ STRIDE threat model, Semgrep + Trivy + ZAP in CI, SBOM + Cosign, webhook signing |
| 4.5 Performance engineering | ✅ caching package, perf budgets package, k6 scripts. Real 10× concurrency soak deferred (TD-004). |

### Phase 5 — Documentation, Launch & Adoption 🟡

| Epic | Status |
|---|---|
| 5.1 User documentation | ✅ `docs/user/` — getting-started → first-green-run in ≤ 30 min |
| 5.2 Operator documentation | ✅ `docs/operator/` — install local + cloud (AWS step-by-step + GCP step-by-step), upgrade, backup, monitoring. GCP Terraform modules deferred (TD-012). |
| 5.3 API + SDK reference | ✅ `docs/api/`, `sdks/python/`, `sdks/typescript/`. PyPI / npm publish deferred (TD-003). |
| 5.4 Portfolio deliverables | ✅ All 12 PRD §20 artifacts in [`portfolio/`](portfolio/index.md). Live demo recording + screenshots deferred (TD-002). |
| 5.5 Beta onboarding | ⏳ deferred — needs a hosted environment to invite to (TD-001) |

### Phase 6 — Maintenance & Continuous Improvement 🟡

| Epic | Status |
|---|---|
| 6.1 Operational cadences | ⏳ calendar / `/schedule` work — wire once hosted |
| 6.2 Model & Provider Lifecycle | ✅ `model_registry` table + `ModelLifecycleService` + 14-day decision SLA query (`/api/v1/model-registry/awaiting-decision`) |
| 6.3 Feedback loops | ✅ `agent_feedback` ledger, weekly low-rated review, `convert-to-eval` regression-case writer |
| 6.4 Tech debt register | ✅ [`tech-debt.md`](tech-debt.md) with conventions, P-rating, and removal triggers |
| 6.5 Compliance & audit (code surface) | ✅ `RetentionSweepService` (audit events compliance-locked at 7 years), `AccessReviewService` (90-day dormant detection). SOC-2 walkthrough + DSAR endpoint deferred (TD-010). |

## Test growth across phases

| Milestone | Unit-test count |
|---|---|
| End of Phase 3 | 482 |
| End of Phase 4.4 | 571 |
| End of Phase 5.3 | 625 |
| End of Phase 5.4 | 658 |
| End of Phase 6.3 + 6.4 | 677 |
| End of Phase 6.2 | 692 |
| Phase 6.5 code surface complete | 705 |
| **Today (TD-008 + TD-011 wired)** | **728** |

## Source-file growth (mypy strict)

| Milestone | Source files |
|---|---|
| End of Phase 4 | 228 |
| Phase 6 epics 6.3 / 6.4 | 239 |
| Phase 6 epic 6.2 | 243 |
| Epic 6.5 added | 247 |
| **Today (TD-008 + TD-011 wired)** | **250** |

## What's left, honestly

Three buckets, in roughly descending impact:

1. **Anything that needs a hosted environment** — Epic 5.5 beta
   onboarding, the recorded demo video, the published SDK packages
   on npm + PyPI, the live evidence-report screenshot, the actual
   SOC-2 walkthrough. Each entry exists in
   [`tech-debt.md`](tech-debt.md) with the trigger that closes it.
2. **Per-workspace overrides** — TD-009 (retention windows in
   policy YAML) and the per-workspace snapshot-provider for
   feedback (TD-006). Both are upgrades to existing services, not
   new features.
3. **Multi-cloud parity** — TD-012 (GCP Terraform modules),
   TD-013 (first real cloud apply), TD-014 (Helm `extraContainers`
   for the Cloud SQL Auth Proxy sidecar). The GCP install runbook
   already documents the workaround flow.

TD-008 (`PROVIDER_DECISION_OVERDUE` alert kind) and TD-011
(dormant-user notifier) landed 2026-04-30 — both bridge
already-shipped state into the alerting and notifier layers via
in-process service classes that an external scheduler invokes on
a cadence (same pattern as the retention sweep). Their previous
"wiring" entry in this list is now resolved in
[`tech-debt.md`](tech-debt.md).

Operational cadences (Epic 6.1) live in `/schedule`, not in the
repo. They'll appear in this dashboard as routine entries once a
hosted control plane is reachable.
