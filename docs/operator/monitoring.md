# Monitoring

Agentic QA Orchestrator ships SLOs (Epic 4.1), structured logs (Story 0.4), audit
events (Epic 2.4), and per-agent cost (Epic 2.5). This page is the
operator's wiring guide — what to scrape, what to alert on, and
where the runbooks live.

## What to scrape

| Surface | Where | Notes |
|---|---|---|
| API metrics | `GET /metrics` (when ServiceMonitor enabled) | Prometheus format |
| Audit log | `GET /api/v1/audit?...` (paginated) | Sign-verifying export |
| Usage / cost | `GET /api/v1/usage/summary` | Per-agent + per-provider |
| Approvals | `GET /api/v1/approvals?state=pending` | Queue depth |
| Flakiness | `GET /api/v1/workspaces/{id}/flakiness/{test_id}` | Per-test |
| Eval trend | `.scorecards/history/<agent>/index.jsonl` | Filesystem; Story 3.5 |

## Default SLOs

From `aqao_api.slo.DEFAULT_SLOS`:

| SLO | Target | Window |
|---|---|---|
| API availability | 99.9% | 30d |
| PR analysis latency | 95% < 60s | 30d |
| Test plan generation | 95% < 90s | 30d |
| API smoke | 95% < 3min | 30d |
| UI smoke | 95% < 10min | 30d |
| Failure classification | 95% < 60s | 30d |
| Evidence report | 95% < 30s | 30d |
| Eval success rate | 95% | 7d |

The :class:`SloCalculator` consumes a sample stream and produces a
:class:`SloSnapshot` per SLO. Wire it as:

1. Per-request hook emits a `RequestSample` per-SLO into your
   metrics backend (Prometheus / CloudWatch).
2. A scheduled job replays the windowed samples through
   `SloCalculator.evaluate()` and writes the snapshot to a Grafana
   panel + the `FreezePolicy` decision channel.

## Default alerts

Tied to the [runbook index](../runbooks/index.md):

| Alert | Severity | Runbook |
|---|---|---|
| `audit_tampered` | SEV1 | audit-tampered.md |
| `slo_burn` (api_availability) | SEV1 | slo-burn.md |
| `slo_burn` (latency) | SEV2 | slo-burn.md |
| `llm_provider_down` | SEV2 | llm-provider-down.md |
| `provider_budget_exhausted` | SEV2 | provider-budget-exhausted.md |
| `dlq_depth >= 1000` | SEV2 | dlq-depth.md |
| `eval_regression` | SEV3 | eval-regression.md |
| `approval_overdue` | SEV4 | approval-overdue.md |
| `external_tracker_down` | SEV4 | external-tracker-down.md |

The :class:`IncidentRouter` (Epic 4.2) maps every alert to the
right severity + page channels. SEV1/SEV2 demand a post-mortem
within 5 business days per the
[postmortem template](../runbooks/postmortem-template.md).

## Cost dashboards

A weekly digest worth running:

```bash
curl 'https://api.aqao.ai/api/v1/usage/summary?since=$(date -v -7d +%Y-%m-%d)' \
  -H "Authorization: Bearer $AQAO_TOKEN" \
  -H "X-AQAO-Tenant-Id: $AQAO_TENANT_ID"
```

The `by_agent` breakdown is the leading indicator for prompt /
model regressions; `by_provider` is the leading indicator for
upstream price changes.

## Validation status

| Item | Status |
|---|---|
| SLO + alert types defined | ✅ Epic 4.1, 4.2 |
| Grafana dashboards | ⏳ deferred — needs a real cluster + Prom |
| PagerDuty / Slack incident wiring | ⏳ deferred per cuts |
