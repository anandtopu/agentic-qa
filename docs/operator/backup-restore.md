# Backup & restore

Pointer page that ties together the existing
[disaster-recovery runbook](../runbooks/disaster-recovery.md)
(Story 3.6.3) with the operator-facing day-2 tasks.

## RPO / RTO targets

| Tier | RPO | RTO |
|---|---|---|
| Postgres | 5 min | 1 hr |
| S3 evidence | 0 (versioned) | 15 min |
| Redis | 15 min | 30 min |
| Secrets Manager | 0 | 5 min |

Numbers are wired into the Terraform modules; raise/lower per
environment by tuning `backup_retention_days` (RDS) and
`snapshot_retention_days` (Redis).

## Daily verification

A nightly cron should:

1. Pick a non-prod DB, trigger a PITR restore, time the wall clock
   from `restore-db-instance` to first successful read.
2. Restore one randomly-chosen evidence artifact from versioning
   and hash-match the bytes.
3. Rotate one secret in Secrets Manager and confirm the API picks
   it up after a rolling restart within 5 minutes.

These are the same steps from the
[quarterly DR drill checklist](../runbooks/disaster-recovery.md#quarterly-dr-drill-checklist);
running them daily on a non-prod environment catches regressions
before the quarterly drill.

## Quarterly drill

First Wednesday of the quarter; SRE on-call drives. File results in
`docs/runbooks/dr-drill-log.md`.

## Common scenarios

### "I dropped the wrong table on prod"

Don't panic. RDS PITR can land at 5-minute granularity:

1. `aws rds describe-db-instances ...` — find the
   `LatestRestorableTime`.
2. `aws rds restore-db-instance-to-point-in-time ...` to a **new**
   instance at a chosen timestamp.
3. Validate the restored DB.
4. Update the connection-string secret + rolling-restart the API.
5. Retain the old instance for 30 days before deleting.

Full procedure in
[disaster-recovery.md](../runbooks/disaster-recovery.md#restore-procedure--postgres-pitr).

### "Someone deleted an evidence artifact"

S3 versioning has it. Run:

```bash
aws s3api list-object-versions \
  --bucket aqao-prod-evidence \
  --prefix "test-runs/<run-id>/"
aws s3api copy-object \
  --copy-source 'aqao-prod-evidence/<key>?versionId=<vid>' \
  --bucket aqao-prod-evidence \
  --key '<key>'
```

### "Audit log signature mismatch"

Pull the affected rows via the audit query API; the
`signature_status` field will read `tampered`. Open a SEV1
incident — that's a security event, not just an ops one.
[`runbooks/audit-tampered.md`] is the entry point (body is filled
out as the alert proves out).

## Cross-tenant verification post-restore

After any restore, the new DB carries every tenant's RLS policies.
Set `app.current_tenant_id` correctly on every validator session
before any read; the Phase-3 test suite enforces this in code.

## Validation status

| Item | Status |
|---|---|
| Runbook documented | ✅ Story 3.6.3 |
| First end-to-end drill executed | ⏳ Phase 4 |
| Daily verification cron | ⏳ deferred until a real cluster exists |
