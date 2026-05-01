# Upgrade

Agentic QA Orchestrator releases follow semver. The upgrade procedure is the same for
patch / minor releases; major releases need extra care, called out
inline.

## Pre-upgrade checklist

- [ ] Read the release notes for any **breaking** items.
- [ ] Take a fresh RDS snapshot (
      `aws rds create-db-snapshot --db-instance-identifier aqao-prod`).
- [ ] Verify the SLO budget for the affected window has headroom
      (Epic 4.1 — if you're already in `SOFT_FREEZE`, defer the
      upgrade).
- [ ] Stage the release in dev first. Smoke + run the
      [DR drill](../runbooks/disaster-recovery.md) abbreviated path
      against the dev environment.

## Standard upgrade

```bash
# 1. Update image tag in values.
helm upgrade aqao ./infra/helm/aqao-api \
  --namespace aqao \
  --reuse-values \
  --set image.tag=v0.2.0           # (mutates)

# 2. Wait for the rollout.
kubectl rollout status -n aqao deployment/aqao-api --timeout=5m

# 3. Run migrations from the new image.
kubectl exec -n aqao deployment/aqao-api -- \
  uv run alembic upgrade head      # (mutates)

# 4. Smoke.
curl https://dev.api.aqao.example.com/api/v1/healthz
```

The HPA + PDB combo (Story 3.6.2) ensures zero-downtime rollouts at
default settings.

## Major-release extras

Major versions may include destructive migrations (column drops,
table renames). The release notes will flag them. Procedure:

1. Take an RDS snapshot **and** a final Postgres dump:
   `pg_dump -Fc -h <endpoint> -U aqao aqao > prod-pre-vN.dump`.
2. Apply migrations in a maintenance window — even though they're
   designed to be online-safe, holding traffic still feels safer
   for the first major.
3. Watch the SLO dashboards for an hour after rollout for latency
   regressions.

## Rolling back

```bash
helm rollback aqao -n aqao   # (mutates)
```

Rollback restores the previous image but **does not** automatically
roll DB migrations back. If the upgrade included a destructive
migration, restore from the pre-upgrade snapshot per the
[disaster-recovery runbook](../runbooks/disaster-recovery.md).

## Schedule

* **Patches** — within 24 hours of release for security CVEs;
  weekly otherwise.
* **Minors** — monthly; coordinate with workspace owners 7 days
  ahead via an in-app banner (deferred — banner UI lands in
  Phase 5).
* **Majors** — quarterly at most; document the migration in
  `docs/upgrades/<version>.md` (deferred until a v1.0 → v2.0
  transition exists).
