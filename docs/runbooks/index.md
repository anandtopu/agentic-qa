# Runbook Index

**Story 4.2** — every alert kind in
`qaforge_api.incident.AlertKind` maps to one runbook here. The
:data:`RUNBOOK_INDEX` constant in `qaforge_api.incident.alert` is the
machine-readable copy of this table; keep them in sync.

## Severity-driven response

| Severity | Response time | MTTR target | Postmortem? | Page channels |
|---|---|---|---|---|
| SEV1 | 5 min | 1 hr | yes | page + slack-incident + email |
| SEV2 | 15 min | 4 hr | yes | page + slack-incident |
| SEV3 | 1 hr | 1 day | no | slack-eng + email |
| SEV4 | 1 day | 5 days | no | ticket |

## Alert → runbook map

| Alert kind | Default severity | Runbook |
|---|---|---|
| `audit_tampered` | SEV1 | [audit-tampered.md](audit-tampered.md) |
| `slo_burn` (api_availability) | SEV1 | [slo-burn.md](slo-burn.md) |
| `slo_burn` (latency) | SEV2 | [slo-burn.md](slo-burn.md) |
| `llm_provider_down` | SEV2 | [llm-provider-down.md](llm-provider-down.md) |
| `provider_budget_exhausted` | SEV2 | [provider-budget-exhausted.md](provider-budget-exhausted.md) |
| `dlq_depth` | SEV2 / SEV3 | [dlq-depth.md](dlq-depth.md) |
| `eval_regression` | SEV3 | [eval-regression.md](eval-regression.md) |
| `approval_overdue` | SEV4 | [approval-overdue.md](approval-overdue.md) |
| `external_tracker_down` | SEV4 | [external-tracker-down.md](external-tracker-down.md) |

Per-runbook bodies fill in as the alerts prove out under real load —
the index is the contract; the procedure is iterative.

## When in doubt

- Check the [post-mortem template](postmortem-template.md) early —
  capturing the timeline as you go is ten times easier than
  reconstructing it after.
- The [disaster-recovery runbook](disaster-recovery.md) (Story
  3.6.3) covers data-restoration scenarios; this index covers
  service-availability incidents.
