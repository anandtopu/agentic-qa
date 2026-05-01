# Troubleshooting

## My PR has no Agentic QA Orchestrator comment

1. Check the GitHub Action run — was the workflow even triggered?
   The default trigger list is `[opened, synchronize, reopened]`;
   draft-PR pushes won't fire unless you add `ready_for_review`.
2. Check the action logs for `start test_run failed: 401` — your
   `AQAO_TOKEN` secret is missing or expired.
3. Check for `start test_run failed: 404 workspace` — the
   `workspace-id` input doesn't match a workspace your token can
   read.

## The PR comment shows but the run is `paused_for_approval`

Someone needs to decide an approval gate. List pending approvals
(see [4. Approve, reject, replay](approvals.md)) and decide. The
workflow resumes automatically — push a new commit if you want to
force a fresh run.

## Run is `failed` but I don't see why

Pull the failure list:

```bash
curl https://api.aqao.ai/api/v1/test-runs/$RUN_ID/failures \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID"
```

Then the evidence report:

```bash
curl https://api.aqao.ai/api/v1/test-runs/$RUN_ID/report
```

If the run failed before the agents ran (e.g. ingestion error), the
audit log is the source of truth:

```bash
curl 'https://api.aqao.ai/api/v1/audit?resource_type=test_run&resource_id=$RUN_ID' \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID"
```

## Cost is higher than expected

Pull the per-agent breakdown:

```bash
curl 'https://api.aqao.ai/api/v1/usage/summary?workspace_id=$WS&since=2026-04-01' \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID"
```

If one agent dominates the spend, lower its prompt's MAX_TOKENS or
pin it to a cheaper model via the prompt registry (Story 3.4.1).

## A test is flapping between flaky_test and product_defect

The classifier's threshold is a 14-day flip-rate of 0.30. If the
test's flip rate hovers around the threshold, you'll see verdict
churn. Two fixes:

1. Quarantine the test until you've fixed the underlying race —
   add it to your `pytest.ini` skip list.
2. Override the threshold for the workspace via a custom
   `HeuristicClassifier(flakiness_threshold=0.40)` (deferred —
   workspace-level threshold customisation is on the Phase-5
   backlog).

## "Webhook delivery failed: 401"

GitHub HMAC signature mismatch. The webhook secret in your repo
settings doesn't match the one in Agentic QA Orchestrator. Re-issue via:

```bash
curl -X POST \
  https://api.aqao.ai/api/v1/repositories/$REPO_ID/webhook-secret \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID"
```

The response is the new secret; paste it into the GitHub repo
webhook config (`Settings → Webhooks → Edit`).

## Still stuck

* Check [FAQ](faq.md) for the 12 most common questions.
* Open an issue at <https://github.com/aqao/aqao/issues> with
  the `test_run_id` and the `correlation_id` from the PR comment.
