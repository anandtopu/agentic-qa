# Disaster Recovery Runbook

**Story 3.6.3** — covers the Agentic QA Orchestrator Control Plane and its hard
state stores (Postgres, S3 evidence). The agent code is immutable and
re-deployable from container images, so DR focuses on recovering
**data** and **configuration**, not workloads.

## RPO / RTO targets

| Tier | RPO | RTO | Rationale |
|---|---|---|---|
| Postgres (Control Plane) | **5 min** | **1 hr** | PITR window; rebuild from snapshot or PITR target |
| S3 evidence store | **0** (versioned) | **15 min** | Versioning + lifecycle keeps every artifact recoverable |
| Redis (Celery state) | **15 min** | **30 min** | Snapshot + replication group failover |
| Secrets Manager | **0** | **5 min** | Multi-Region replication when ``replicate_to`` is set |

These are the **defaults** the Terraform modules wire up. Tighter
targets per tenant cost more and require explicit per-environment
overrides.

## Inventory of recoverable assets

1. **Postgres RDS**: `rds.backup_retention_period=7` days; PITR window
   = 7 days. Final-snapshot retained on prod-only deletion.
2. **S3 evidence bucket**: versioning enabled; lifecycle moves
   non-current versions to STANDARD_IA after 30 days, expires after
   365 days.
3. **Secrets Manager**: ``recovery_window_in_days=7`` in prod, so a
   deleted secret can be restored for one week.
4. **Terraform state**: stored in an S3 bucket with versioning + a
   DynamoDB lock table — itself a recovery dependency. Treat the
   state bucket as production-tier.

## Restore procedure — Postgres (PITR)

When data corruption is detected (bad migration, accidental DELETE,
ransomware):

```bash
# 1. Identify the last-good timestamp.
aws rds describe-db-instances --db-instance-identifier aqao-prod \
  --query 'DBInstances[0].LatestRestorableTime'

# 2. Restore to a NEW instance at a chosen point in time (5-min granularity).
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier aqao-prod \
  --target-db-instance-identifier aqao-prod-restore-$(date +%Y%m%dT%H%M) \
  --restore-time 2026-05-01T11:55:00Z \
  --db-subnet-group-name aqao-prod-db \
  --vpc-security-group-ids sg-xxxxxxxx \
  --no-publicly-accessible

# 3. Validate the restored instance: connect from a bastion / kubectl debug
#    pod and run the read-only checks from the FlakinessService /
#    DbValidator suites against the restored DB.

# 4. Cut over: update the connection-string secret in Secrets Manager
#    (aqao/prod/database_url) to point at the restored endpoint, then
#    rolling-restart the API Deployment so pods pick up the new endpoint.
kubectl -n aqao rollout restart deployment/aqao-api

# 5. Once the new instance is the live target, retain the old instance
#    (final-snapshot) for 30 days before deletion in case the cutover
#    surfaced an issue we didn't catch.
```

**Test it**: Story 3.6.3 AC requires this drill to succeed end-to-end
**within the RTO of 1 hour**. Drill-mode bypasses the secret update
and writes to a parallel namespace.

## Restore procedure — S3 evidence

S3 versioning means every artifact is a `VersionId` away. To recover
a specific evidence artifact:

```bash
# List versions for the object.
aws s3api list-object-versions \
  --bucket aqao-prod-evidence \
  --prefix "test-runs/<run-id>/"

# Restore a specific version by copying it on top of the current.
aws s3api copy-object \
  --copy-source 'aqao-prod-evidence/<key>?versionId=<vid>' \
  --bucket aqao-prod-evidence \
  --key '<key>'
```

For a wholesale bucket recovery (ransomware, accidental
``aws s3 rm --recursive``), enable Object Lock + replication to a
**second region** (deferred — requires a separate Terraform variable
``evidence_replicate_to`` set to a region; not in the dev defaults).

## Quarterly DR drill checklist

Run on the first Wednesday of every quarter. Owner: SRE on-call.

- [ ] Identify a non-prod DB and trigger a PITR restore to a new
      instance, timing wall-clock from `restore-db-instance` call to
      first successful read against the restored endpoint. Target:
      under 1 hr.
- [ ] Restore one randomly-chosen evidence artifact from versioning;
      confirm the recovered bytes hash-match the version listed in
      `external_issues.raw`.
- [ ] Rotate one secret in Secrets Manager and confirm the API picks
      it up after a rolling restart within 5 minutes.
- [ ] File the drill outcome in `docs/runbooks/dr-drill-log.md`
      with timestamps + the reviewer who confirmed.

## Cross-cutting concerns

- **Tenant isolation during DR**: the restored DB carries every
  tenant's RLS policies. Set `app.current_tenant_id` correctly on
  the validator session before any read.
- **Audit log integrity**: the HMAC signature on `audit_events` rows
  is verifiable post-restore — Story 2.4.2's `AuditQueryService.export_*`
  methods report `signature_status` per row. Run an export against
  the restored DB and confirm no `tampered` rows.
- **External issues sync**: restoring the DB does **not** replay
  external-issue webhooks. After cutover, run a one-off
  `ExternalIssueService.fetch + sync_from_provider` sweep over the
  open `external_issues` rows so the local statuses converge with
  the upstream trackers' current state.

## Validation status

| Item | Status |
|---|---|
| Procedure documented | ✅ Story 3.6.3 |
| RPO / RTO targets agreed | ✅ Story 3.6.3 |
| First end-to-end drill executed | ⏳ deferred — requires a real cloud account (Story 3.6.1 apply) |

The first drill is a Phase-4 milestone. Until then, the runbook is
the contract.
