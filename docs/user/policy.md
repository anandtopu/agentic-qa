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
