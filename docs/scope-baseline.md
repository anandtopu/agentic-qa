# Scope Baseline

The MVP-by-MVP commitment, derived from PRD §18. This is the document the
team treats as authoritative when deciding whether work is in scope. Out-
of-scope items go to `docs/parking-lot.md` (created when first needed),
not the backlog.

> **Delivery status (2026-04-29):** All MVP-1, MVP-2, and MVP-3 scope items
> below are shipped. Phases 4 (hardening), 5 (docs + portfolio, minus 5.5),
> and 6 (maintenance, minus the 6.1 calendar cadence) are also shipped.
> See [`PROGRESS.md`](PROGRESS.md) for the live dashboard and
> [`tech-debt.md`](tech-debt.md) for deferred items.

## In scope — MVP 1 (Core Agentic QA Workflow)

| Item | PRD ref | Owner |
|---|---|---|
| Workspace creation & GitHub linkage | §9.1 | TBD |
| Requirement ingestion (PR diff, OpenAPI, Postman, SQL schema, Markdown) | §9.2 | TBD |
| Test Planning Agent with structured output | §9.3 | TBD |
| API Testing Agent (Newman + pytest+httpx) | §9.4 | TBD |
| UI Testing Agent (Playwright TS) | §9.5 | TBD |
| Failure Classifier (rules + LLM) | §9.8 | TBD |
| Markdown Evidence Report | §9.11 | TBD |
| GitHub Actions integration (PR comment + gate) | §9.12 | TBD |

## In scope — MVP 2 (Production-Grade Controls)

| Item | PRD ref |
|---|---|
| Human approval gates (all six events) | §9.10 |
| DB Validation Agent (read-only by default) | §9.6 |
| Release Risk Scoring | §9.9 |
| Audit logging | §14.2 |
| Per-run cost & runtime caps | §10.3 |
| Agent evaluation suite | §9.13 |

## In scope — MVP 3 (Enterprise Differentiators)

| Item | PRD ref |
|---|---|
| Multi-tenant RBAC + SSO | §14.2 |
| Jira / GitHub issue creation | §9.10, §9.8 |
| Historical flakiness detection | §9.13 |
| Prompt & version registry | §10.2 |
| Continuous eval regression suite | §9.13 |
| Cloud deployment (Terraform + Helm) | §16 |

## Explicitly out of scope (PRD §6)

- Replacing QA engineers wholesale.
- Fully autonomous production deployment approvals.
- Generic LLM chatbot UX.
- Test management system clone.
- Every test framework — Phase 1 is Playwright + pytest + Newman only.

## Non-functional commitments

PRD §14 targets are commitments, not aspirations. Each is owned and
tracked:

| Target | PRD ref | Phase | Verified by |
|---|---|---|---|
| API availability ≥ 99.9% | §14.1 | Phase 4 | SLO dashboard |
| Tool execution success ≥ 95% | §14.1, §19 | Phase 1+ | eval harness |
| PR analysis P95 ≤ 60s | §14.5 | Phase 1 | CI perf assertion |
| Test plan generation P95 ≤ 90s | §14.5 | Phase 1 | CI perf assertion |
| API smoke ≤ 3 min | §14.5 | Phase 1 | CI perf assertion |
| UI smoke ≤ 10 min | §14.5 | Phase 1 | CI perf assertion |
| Failure classification P95 ≤ 60s | §14.5 | Phase 1 | CI perf assertion |
| Evidence report P95 ≤ 30s | §14.5 | Phase 1 | CI perf assertion |
| Generated test cases executable without edits ≥ 70% | §19 | Phase 2 | eval scorecard |
| Failure classification accuracy ≥ 80% | §19 | Phase 2 | eval scorecard |
| False-positive defect rate < 15% | §19 | Phase 2/3 | eval scorecard |
| Avg cost per PR analysis < $1.00 | §19 | Phase 2 | usage_records |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Eng director | | |
| Product manager | | |
| Security lead | | |
| QA lead | | |
