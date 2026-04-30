# 4. Approve, reject, replay

QAForge's six approval gates (PRD §9.10) pause a workflow on actions
that need a human. Same flow for all six: workflow pauses → reviewer
hits an endpoint → workflow resumes (approved) or fails (rejected).

## The six gates

* `destructive_sql` — DELETE/UPDATE/DROP/TRUNCATE/ALTER (Story 2.2.3).
* `production_test_execution` — running tests against prod env.
* `external_ticket_creation` — Jira/GitHub issue auto-creation
  (Epic 3.2; deduped within 24h).
* `release_readiness` — go/no-go.
* `ci_pipeline_modification` — changes to your `.github/workflows/`.
* `high_cost_eval_run` — eval runs > policy budget.

Configure which gates fire in your [policy](policy.md)'s
`require_approval_for` list.

## Inspect the queue

```bash
curl 'https://api.qaforge.ai/api/v1/approvals?state=pending' \
  -H "Authorization: Bearer $QAFORGE_TOKEN" \
  -H "X-QAForge-Tenant-Id: $QAFORGE_TENANT_ID" \
  -H "X-QAForge-Role: approver"
```

Filter by `workspace_id`, `event_type`, or limit; results are newest
first.

## Decide

```bash
curl -X POST \
  https://api.qaforge.ai/api/v1/approvals/$ID/approve \
  -H "Authorization: Bearer $QAFORGE_TOKEN" \
  -H "X-QAForge-Tenant-Id: $QAFORGE_TENANT_ID" \
  -H "X-QAForge-Role: approver" \
  -H "Content-Type: application/json" \
  -d '{"comment": "verified rollback path"}'
```

`/reject` and `/cancel` have the same shape. The decision is
audit-logged with HMAC-SHA256 (Story 2.4.1) so reviewer attribution
survives.

## Roles

The `approval:decide` permission belongs to `owner`, `admin`, and
`approver` (Story 3.1.2). `engineer` cannot self-approve a
destructive action — that separation of duties is intentional.

## Replay

A rejected workflow goes to `failed`. To retry after fixing the
underlying issue, kick a new run via the GitHub Action (push a new
commit) — there's no in-place "rerun rejected workflow" yet.

## Next

→ [5. Read your first run](reading-the-run.md)
