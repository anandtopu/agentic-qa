# 2. Set a policy

The **policy** is the workspace's contract for cost, runtime, and
destructive-action behaviour. Policies are versioned (PRD §10.3) so
every change is auditable; the active version controls every run.

## The shape

```yaml
policy:
  allow_write_operations: false
  require_approval_for:
    - destructive_sql
    - production_test_execution
    - external_ticket_creation
  redact_secrets: true
  max_cost_usd_per_run: 5.00
  max_runtime_minutes: 30
  retention:          # optional — per-class overrides, in days
    test_runs: 180
    agent_feedback: 365
```

Each field is the **default**; raise or lower based on your team's
risk tolerance.

| Field | What it does | Where to find more |
|---|---|---|
| `allow_write_operations` | DB writes off by default | PRD §11.2 |
| `require_approval_for` | Lists the gates that need a human | PRD §9.10 |
| `redact_secrets` | Runs every text sink through the redactor | `aqao_redaction` |
| `max_cost_usd_per_run` | Mid-flight kill switch with 5% slack | Epic 2.5 |
| `max_runtime_minutes` | Wallclock budget per run | Epic 2.5 |
| `retention` | Per-data-class retention windows for this workspace | see below |

## Retention overrides

By default each data class is pruned on the platform schedule (test
runs after 90 days, feedback after 365, and so on). A workspace can
keep — or shed — its own data on a different cadence with the
`retention` map: keys are data-class names, values are the window in
**days**.

```yaml
policy:
  retention:
    test_runs: 180          # keep run history twice as long
    flakiness_observations: 30
```

Rules the validator enforces (a bad value gives a `422` with the
offending field):

- **Bounded to 365 days.** The data-handling policy commits to a
  365-day maximum; you cannot opt into "forever".
- **Overridable classes only:** `test_runs`,
  `flakiness_observations`, `agent_feedback`, `external_issues`,
  `usage_records`. Other classes inherit the platform default.
- **Audit events can't be overridden** — they are compliance-locked
  at 7 years.

Omit the `retention` key entirely to keep every default.

## Apply it

```bash
curl -X PUT \
  https://api.aqao.ai/api/v1/workspaces/$WORKSPACE_ID/policy \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID" \
  -H "Content-Type: application/yaml" \
  --data-binary @policy.yaml
```

The response gives you the new version number. Production traffic
moves to the new version atomically.

## Inspect history

```bash
curl https://api.aqao.ai/api/v1/workspaces/$WORKSPACE_ID/policy/history \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID"
```

Every change is audit-logged; you can roll back by activating an
older version with `POST .../policy/activate/{version}`.

## Next

→ [3. Wire the GitHub Action](github-action.md)
