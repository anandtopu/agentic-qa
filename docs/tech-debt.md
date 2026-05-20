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
| TD-003 | SDKs not published to npm / PyPI | P2 | Phase 5 / Story 5.3 | @unassigned | 2026-04-29 | First external consumer needs `pip install aqao-sdk` / `npm i @aqao/sdk`; until then the workspace-only install is fine. |
| TD-004 | Real 10× concurrency perf runs deferred | P2 | Phase 4 / Epic 4.5 | @unassigned | 2026-04-29 | Hosted infra with capacity to drive k6 at 10× the baseline; budgets in `aqao_api.perf` already enforced in CI smoke. |
| TD-005 | Postgres-backed integration tests not run on this machine | P3 | Phase 0 / Story 0.3.6 | @unassigned | 2026-04-29 | Docker daemon available locally or in CI; unit suite is fully green. |
| TD-006 | `agent_feedback` snapshot provider returns only the resource pointer | P2 | Phase 6 / Epic 6.3 | @unassigned | 2026-04-29 | Replace `_default_snapshot_provider` with one that pulls the actual prompt/context off the evidence store per `resource_type` (test plan, classification, evidence report). Until then operators fill `expected` by hand at conversion time. |
| TD-007 | Feedback ↔ eval-baseline auto-promotion not wired | P3 | Phase 6 / Epic 6.3 | @unassigned | 2026-04-29 | Feedback cases land in `feedback_cases.jsonl`; promoting them to the pinned baseline still requires a manual `make eval --promote`. Wire to a scheduled nightly once volume warrants. |
| TD-010 | DSAR admin endpoint not built | P2 | Phase 0 / Story 0.1.3 + Phase 6 / Epic 6.5 | @unassigned | 2026-04-29 | Open question Q-001 in `docs/prd-questions.md`. Decide: admin endpoint vs manual SQL. Required before any EU customer; the data-handling doc commits to ≤30-day deletion turnaround. |
| TD-012 | GCP Terraform modules not built | P2 | Phase 3 / Story 3.6.1 | @unassigned | 2026-04-29 | AWS Terraform modules (vpc/eks/rds/redis/s3-evidence/secrets/iam) exist; GCP equivalents (vpc/gke/cloud-sql/memorystore/gcs-evidence/secret-manager/workload-identity) do not. The GCP install runbook drives `gcloud` directly until they land. Removal trigger: any user wanting reproducible GCP environments at >1 footprint. |
| TD-013 | First real `terraform apply` / GCP `gcloud apply` deferred | P2 | Phase 3 / Story 3.6.1 | @unassigned | 2026-04-29 | Both runbooks (`install-aws.md`, `install-gcp.md`) are dry-validated only. Removal trigger: a billable AWS account or GCP project with admin credentials available; run the procedure end-to-end and capture the outputs in the runbook. |

## Resolved items

| ID | Title | Closed | Where |
|---|---|---|---|
| TD-014 | Helm chart exposes `extraContainers` (+ `extraVolumes`) | 2026-05-20 | `infra/helm/aqao-api/values.yaml` adds `extraContainers: []` / `extraVolumes: []` (with a Cloud SQL Auth Proxy example); `templates/deployment.yaml` renders them under `containers:` (after `api`) and `volumes:` (the volumes block now renders when `tmpVolume.enabled` **or** `extraVolumes` is set). `docs/operator/install-gcp.md` Steps 11/13 replace the `kubectl patch` workaround with the inline sidecar + a single `helm upgrade --install`. Chart README documents the fields. Verified with `helm lint` + `helm template` (api stays first, sidecar appended, securityContext preserved). Tests: `test_helm_chart_smoke.py` (values defaults + template wiring). |
| TD-009 | Retention sweep honours per-workspace policy overrides | 2026-05-20 | `AgentPolicy.retention` map (`policies/schema.py`) — a `{class: days}` override, bounded to `RETENTION_MAX_DAYS` (365) and restricted to `OVERRIDABLE_RETENTION_CLASSES` (the non-locked, directly-workspace-owned classes). `RetentionSweepService` is now workspace-aware: `load_active_retention_overrides()` reads active policies, `_plan_buckets()` partitions each class into a default bucket plus one per overriding workspace, and `override_workspaces` is surfaced in the report, the API response, and the audit payload. Docs: `docs/user/policy.md`, `docs/security/data-handling.md`. Tests: `test_policy_schema.py` (validation) + `test_retention_service.py` (planner, override wiring, loader, drift guard). Note: join-only child classes (`agent_tasks`/`evidence_artifacts`/`failure_classifications`) remain default-only — they CASCADE-delete with their parent `test_runs`, so a longer run window already extends them. |
| TD-008 | `PROVIDER_DECISION_OVERDUE` alert kind wired | 2026-04-30 | `aqao_api.incident.AlertKind.PROVIDER_DECISION_OVERDUE` + `aqao_api.services.lifecycle_alerts.ModelLifecycleAlertService` bridges `awaiting_decision()` to the incident router. Runbook stub at `docs/runbooks/provider-decision-overdue.md`; routes to SEV4 alongside `APPROVAL_OVERDUE`. Tests in `apps/api/tests/test_lifecycle_alerts.py` + new case in `test_incident.py`. |
| TD-011 | DSAR-driven access-review escalation wired | 2026-04-30 | New `aqao_api.notifications.DormantUserNotifier` Protocol + `LogDormantUserNotifier` reference impl, `aqao_api.services.dormant_user_review.DormantUserReviewService` bridges `AccessReviewService.snapshot()` to the notifier and audits the aggregate action. Tests in `apps/api/tests/test_dormant_user_review.py`. |

When archiving older entries, move them to `docs/tech-debt-archive.md`
once this list grows past ~20 rows.
