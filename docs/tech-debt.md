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
| TD-010 | DSAR admin endpoint not built | P2 | Phase 0 / Story 0.1.3 + Phase 6 / Epic 6.5 | @unassigned | 2026-04-29 | Open question Q-001 in `docs/prd-questions.md`. Decide: admin endpoint vs manual SQL. Required before any EU customer; the data-handling doc commits to ≤30-day deletion turnaround. |
| TD-013 | First real `terraform apply` / GCP `gcloud apply` deferred | P2 | Phase 3 / Story 3.6.1 | @unassigned | 2026-04-29 | Both runbooks (`install-aws.md`, `install-gcp.md`) are dry-validated only. Removal trigger: a billable AWS account or GCP project with admin credentials available; run the procedure end-to-end and capture the outputs in the runbook. |

## Resolved items

| ID | Title | Closed | Where |
|---|---|---|---|
| TD-012 | GCP Terraform modules built (parity with AWS) | 2026-05-20 | New `infra/terraform/modules/gcp/{vpc,gke,cloud-sql,memorystore,gcs-evidence,secret-manager,workload-identity}` + `environments/gcp-dev` composing all seven. Mirrors the AWS set: Workload Identity for IRSA, Private Service Access for Cloud SQL + Memorystore private IPs, CMEK on the evidence bucket, AUTH+TLS Redis. `cloud_sql_connection_name` output feeds the TD-014 proxy sidecar. Verified with `terraform fmt` + `init -backend=false` + **`terraform validate` (green)** — the validate caught a real sensitive-`for_each` bug that the (git-ignored, never-validated) AWS secrets module still has; the GCP `secret-manager` module keys `for_each` off the static secret names instead. Tests: 2 new GCP cases in `test_helm_chart_smoke.py`. README documents the layout + validate/apply flow. **TD-013** (the real `apply`) remains — still needs a billable project. |
| TD-007 | Feedback cases promoted into the scored eval dataset | 2026-05-20 | New `aqao_eval.promotion` (`promote_feedback_cases` / `promote_all_feedback_cases`). Root cause was deeper than "needs a scheduler": `load_dataset` only read `<agent>/<version>.jsonl`, so the `feedback_cases.jsonl` written by `convert_to_eval_case` was never scored. Promotion merges new cases into the pinned dataset version (idempotent on case id; creates the file if absent; dedupes within the feedback file). Baseline re-pinning stays the deliberate `set-baseline` step so promotion can't mask a regression. Exposed via `python -m aqao_eval.cli promote-feedback` + `make eval-promote`; an external scheduler drives the cadence (same shape as the retention sweep). Tests: `packages/eval/tests/test_promotion.py` (merge, idempotency, create-if-missing, no-op, dedupe, multi-agent). |
| TD-006 | `agent_feedback` snapshot provider pulls real inputs off the owning store | 2026-05-20 | New `aqao_api.services.feedback_snapshot.EvidenceStoreSnapshotProvider` — a registry routing `resource_type` to a resolver: `failure_classification` → the row's `raw_signal` + `signal_id`; `test_plan` → the source `Requirement` (raw + parsed); `evidence_report` → the artifact's run context (test_run_id, plan summary, failure rows). Unknown types / pruned rows fall back to the pointer (with a `snapshot_unavailable` flag) so conversion never fails. Wired into `routers/agent_feedback._service` with the tenant-scoped session (RLS-isolated). `_default_snapshot_provider` stays as the service's no-wiring default. Redaction still applied downstream by `build_feedback_case`. Tests: `test_feedback_snapshot.py` (resolvers + routing + both fallbacks). |
| TD-014 | Helm chart exposes `extraContainers` (+ `extraVolumes`) | 2026-05-20 | `infra/helm/aqao-api/values.yaml` adds `extraContainers: []` / `extraVolumes: []` (with a Cloud SQL Auth Proxy example); `templates/deployment.yaml` renders them under `containers:` (after `api`) and `volumes:` (the volumes block now renders when `tmpVolume.enabled` **or** `extraVolumes` is set). `docs/operator/install-gcp.md` Steps 11/13 replace the `kubectl patch` workaround with the inline sidecar + a single `helm upgrade --install`. Chart README documents the fields. Verified with `helm lint` + `helm template` (api stays first, sidecar appended, securityContext preserved). Tests: `test_helm_chart_smoke.py` (values defaults + template wiring). |
| TD-009 | Retention sweep honours per-workspace policy overrides | 2026-05-20 | `AgentPolicy.retention` map (`policies/schema.py`) — a `{class: days}` override, bounded to `RETENTION_MAX_DAYS` (365) and restricted to `OVERRIDABLE_RETENTION_CLASSES` (the non-locked, directly-workspace-owned classes). `RetentionSweepService` is now workspace-aware: `load_active_retention_overrides()` reads active policies, `_plan_buckets()` partitions each class into a default bucket plus one per overriding workspace, and `override_workspaces` is surfaced in the report, the API response, and the audit payload. Docs: `docs/user/policy.md`, `docs/security/data-handling.md`. Tests: `test_policy_schema.py` (validation) + `test_retention_service.py` (planner, override wiring, loader, drift guard). Note: join-only child classes (`agent_tasks`/`evidence_artifacts`/`failure_classifications`) remain default-only — they CASCADE-delete with their parent `test_runs`, so a longer run window already extends them. |
| TD-008 | `PROVIDER_DECISION_OVERDUE` alert kind wired | 2026-04-30 | `aqao_api.incident.AlertKind.PROVIDER_DECISION_OVERDUE` + `aqao_api.services.lifecycle_alerts.ModelLifecycleAlertService` bridges `awaiting_decision()` to the incident router. Runbook stub at `docs/runbooks/provider-decision-overdue.md`; routes to SEV4 alongside `APPROVAL_OVERDUE`. Tests in `apps/api/tests/test_lifecycle_alerts.py` + new case in `test_incident.py`. |
| TD-011 | DSAR-driven access-review escalation wired | 2026-04-30 | New `aqao_api.notifications.DormantUserNotifier` Protocol + `LogDormantUserNotifier` reference impl, `aqao_api.services.dormant_user_review.DormantUserReviewService` bridges `AccessReviewService.snapshot()` to the notifier and audits the aggregate action. Tests in `apps/api/tests/test_dormant_user_review.py`. |

When archiving older entries, move them to `docs/tech-debt-archive.md`
once this list grows past ~20 rows.
