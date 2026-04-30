# Tech debt register

Per Epic 6.4 of `docs/IMPLEMENTATION_PLAN.md`. The aim is to keep
deferred work, known shortcuts, and "remove once X" TODOs visible
in one place so they are easy to triage at the bi-weekly grooming
ritual rather than rediscovered ad-hoc.

## Conventions

| Field | Meaning |
|---|---|
| **ID** | `TD-NNN` — append, never reuse. |
| **Title** | One-line summary; no internal jargon. |
| **Severity** | `P1` (blocks GA / blocks a downstream story), `P2` (planned, unblocked), `P3` (cleanup, not load-bearing). |
| **Source story** | The phase / epic / story that introduced the deferral, so context survives the rotation. |
| **Owner** | The engineer who knows where the bodies are buried. `@unassigned` is allowed but should be filled before Stage Up. |
| **Opened** | YYYY-MM-DD. The 90-day clock for P1 items starts here. |
| **Removal trigger** | What needs to be true for this to close — *not* a date. Dates rot; conditions don't. |
| **Notes** | Links to ADRs, runbooks, or related tickets. |

A P1 entry that has been open more than 90 days is a Definition-of-Done
violation per the implementation plan and should be escalated.

## Open items

| ID | Title | Severity | Source story | Owner | Opened | Removal trigger |
|---|---|---|---|---|---|---|
| TD-001 | Beta onboarding (Epic 5.5) deferred until platform is hosted | P2 | Phase 5 / Epic 5.5 | @unassigned | 2026-04-29 | A staging or production deployment is reachable; invite list + NPS survey can be exercised end-to-end. |
| TD-002 | Demo video, screenshots, and live evidence-report not recorded | P2 | Phase 5 / Story 5.4 | @unassigned | 2026-04-29 | Hosted environment + a green run on the sample app to film against. |
| TD-003 | SDKs not published to npm / PyPI | P2 | Phase 5 / Story 5.3 | @unassigned | 2026-04-29 | First external consumer needs `pip install qaforge-sdk` / `npm i @qaforge/sdk`; until then the workspace-only install is fine. |
| TD-004 | Real 10× concurrency perf runs deferred | P2 | Phase 4 / Epic 4.5 | @unassigned | 2026-04-29 | Hosted infra with capacity to drive k6 at 10× the baseline; budgets in `qaforge_api.perf` already enforced in CI smoke. |
| TD-005 | Postgres-backed integration tests not run on this machine | P3 | Phase 0 / Story 0.3.6 | @unassigned | 2026-04-29 | Docker daemon available locally or in CI; unit suite is fully green. |
| TD-006 | `agent_feedback` snapshot provider returns only the resource pointer | P2 | Phase 6 / Epic 6.3 | @unassigned | 2026-04-29 | Replace `_default_snapshot_provider` with one that pulls the actual prompt/context off the evidence store per `resource_type` (test plan, classification, evidence report). Until then operators fill `expected` by hand at conversion time. |
| TD-007 | Feedback ↔ eval-baseline auto-promotion not wired | P3 | Phase 6 / Epic 6.3 | @unassigned | 2026-04-29 | Feedback cases land in `feedback_cases.jsonl`; promoting them to the pinned baseline still requires a manual `make eval --promote`. Wire to a scheduled nightly once volume warrants. |
| TD-008 | `PROVIDER_DECISION_OVERDUE` alert kind not wired | P3 | Phase 6 / Epic 6.2 | @unassigned | 2026-04-29 | The `awaiting_decision()` query already returns `sla_breached` rows; the Phase-4 incident-router needs a new `AlertKind` + runbook + scheduled job that fires when `breach_count > 0`. Decision-overdue is currently visible via the API but does not page. |
| TD-009 | Retention sweep ignores per-workspace policy overrides | P2 | Phase 6 / Epic 6.5 | @unassigned | 2026-04-29 | `RetentionSweepService` uses the hard-coded class registry; `WorkspacePolicy` YAML doesn't pin a `retention.<class>.days` key today. Add the schema field, then read overrides at sweep time so a workspace that opts into the documented 365-day max actually gets it. Reason: keeping the sweep predictable while we land the schema; opt-out is currently per-deployment, not per-workspace. |
| TD-010 | DSAR admin endpoint not built | P2 | Phase 0 / Story 0.1.3 + Phase 6 / Epic 6.5 | @unassigned | 2026-04-29 | Open question Q-001 in `docs/prd-questions.md`. Decide: admin endpoint vs manual SQL. Required before any EU customer; the data-handling doc commits to ≤30-day deletion turnaround. |
| TD-011 | DSAR-driven access-review escalation not wired | P3 | Phase 6 / Epic 6.5 | @unassigned | 2026-04-29 | `AccessReviewService` reports `dormant_count`, but no automated workflow notifies admins about dormant users to revoke. Wire to the notifier (Story 2.1.2) once a quarterly cadence is running. |
| TD-012 | GCP Terraform modules not built | P2 | Phase 3 / Story 3.6.1 | @unassigned | 2026-04-29 | AWS Terraform modules (vpc/eks/rds/redis/s3-evidence/secrets/iam) exist; GCP equivalents (vpc/gke/cloud-sql/memorystore/gcs-evidence/secret-manager/workload-identity) do not. The GCP install runbook drives `gcloud` directly until they land. Removal trigger: any user wanting reproducible GCP environments at >1 footprint. |
| TD-013 | First real `terraform apply` / GCP `gcloud apply` deferred | P2 | Phase 3 / Story 3.6.1 | @unassigned | 2026-04-29 | Both runbooks (`install-aws.md`, `install-gcp.md`) are dry-validated only. Removal trigger: a billable AWS account or GCP project with admin credentials available; run the procedure end-to-end and capture the outputs in the runbook. |
| TD-014 | Helm chart does not expose `extraContainers` | P3 | Phase 3 / Story 3.6.2 | @unassigned | 2026-04-29 | The GCP install path needs a Cloud SQL Auth Proxy sidecar; today it requires a post-`helm template` `kubectl patch`. Add an `extraContainers` field to `values.yaml` and the deployment template so `values-gcp.yaml` can declare the sidecar inline. |

## Resolved items

*(empty)* — when an item lands, move it here with a `Closed` date and a
link to the PR / commit. Keep them in this file for one quarter then
archive to `docs/tech-debt-archive.md` if the list grows past ~20 rows.
