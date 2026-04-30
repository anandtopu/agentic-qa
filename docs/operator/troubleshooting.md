# Troubleshooting (operator)

Problem-first index. Each entry links to the runbook + the
underlying story for context.

## Pods are CrashLoopBackOff

1. `kubectl logs -n qaforge deployment/qaforge-api --previous` —
   the boot error.
2. Common causes:
   * Database password rotated but the `database_url` secret
     wasn't refreshed → see
     [backup-restore.md](backup-restore.md#secrets-manager).
   * Migration drift after a partial upgrade rollback → run
     `alembic upgrade head` from a clean image.
   * IRSA role missing the new Secrets Manager ARN → re-apply
     Terraform (`terraform apply` on the `iam` module).

## Pods are OOMKilled

1. `kubectl describe pod -n qaforge $POD` — check the resource
   limits.
2. Bump `resources.limits.memory` in the Helm values and roll the
   release. The default 1Gi is sized for ~50 concurrent agent
   tasks per pod; sustained higher load needs a bigger box or more
   replicas.

## Latency is high but no SLO breach yet

1. Pull `/api/v1/usage/summary` — is one provider dominating the
   spend? That usually correlates with provider-side latency.
2. Check the circuit-breaker state via
   `/metrics` (`qaforge_breaker_state` gauge). If a breaker is
   half-open, you're recovering from a recent outage.
3. Inspect the LRU cache hit rates — `qaforge_cache_hit_rate`. A
   sudden drop means a deploy invalidated the cache; let it warm
   up for ~10 minutes before escalating.

## DLQ is growing

1. `/metrics` exposes `qaforge_dlq_depth`. Drain via the admin API
   (deferred — Phase-5 admin UI) or directly through the service:
   ```python
   from qaforge_api.reliability import InMemoryDeadLetterQueue
   ```
2. Inspect the most recent failures — they all share a root cause
   90% of the time.
3. If the cause is upstream (LLM 5xx, RDS connection cap), fix the
   cause first; replaying letters into a still-broken downstream
   just re-fills the DLQ.

## Webhook signature failures

GitHub: re-issue the webhook secret via
`POST /api/v1/repositories/{id}/webhook-secret` and update GitHub.
Jira: same shape via the Phase-3 Jira adapter (Story 3.2.x).

## Cross-tenant access alert fired

Story 3.1.1 emits `tenant_isolation.resource_miss` on every
tenant-scoped 404. Real cross-tenant probes look identical to a
stale UI link to a deleted workspace at this layer; investigate by:

1. Pull the audit log for the tenant — was there an unrelated
   delete in the last 5 minutes?
2. Check the alert volume — a single line is benign; a flood is
   probing.

## Cost spike alert

`provider_budget_exhausted` fires when `BudgetEnforcer` kills a
run. Pull `/api/v1/usage/summary?test_run_id=<run>` to see exactly
which agent / provider drove the spike. Common causes:

* Agent prompt regression (check the prompt version pin).
* Upstream provider raised prices (check the model column).
* Eval harness ran without the budget cap (check
  `policy.max_cost_usd_per_run`).

## Audit signature mismatch

SEV1. Open an incident immediately. The
`AuditQueryService.export_*` methods report `signature_status` per
row; export the affected window to CSV and compare against the
HMAC key rotation log. The runbook for this lives at
`docs/runbooks/audit-tampered.md`.

## When all else fails

* Check the [runbook index](../runbooks/index.md) for an alert that
  matches the symptom.
* Open a SEV2/3 incident if you need eyes from the build team.
* The [post-mortem template](../runbooks/postmortem-template.md) is
  your friend — fill it in as you go, not after.
