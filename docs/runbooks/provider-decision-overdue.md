# Runbook — `provider_decision_overdue`

**Severity:** SEV4 — file a ticket, fix during normal work.

**Source:** Epic 6.2 (Model & Provider Lifecycle). The
`ModelLifecycleAlertService` cadence calls
`ModelLifecycleService.awaiting_decision(...)` and fires this alert
when one or more registered candidate models have sat without a
go/no-go decision for longer than the configured SLA (default 14
days).

## What this means

A new flagship model from Anthropic / OpenAI / Gemini was registered
in `model_registry`, but the engineering lead has not yet recorded
`go` or `no_go`. The PRD §6.2 acceptance criterion commits to a
decision within 14 days of release; missing that means we are
quietly drifting from "we keep up with the frontier" — the alert
makes the drift visible.

This is **not** an outage. The platform continues to serve traffic
on whatever model is currently pinned. The risk is purely process:
a missed evaluation cycle compounds into multiple missed cycles.

## What to do

1. **Read the alert detail.** It lists every breached
   `provider/model_id` pair and the age in days.
2. **Pick one.** Call `GET /api/v1/model-registry/awaiting-decision`
   for the full list, ordered oldest-first. Triage starts at the
   top.
3. **Run the eval.** `make eval` against the candidate model. If a
   scorecard already exists, attach it via
   `POST /api/v1/model-registry/{id}/scorecard`.
4. **Record the decision.** `POST /api/v1/model-registry/{id}/decision`
   with `go` (pin the model) or `no_go` (reject) plus a rationale.
   The rationale is free-form text; aim for one short paragraph
   capturing eval delta, cost delta, and any qualitative reason.
5. **Verify the alert clears.** Re-running the cadence after the
   decision should report `breach_count = 0` for the cleared row.

## When to escalate

- More than three candidates are breached at once. That signals the
  cadence itself is broken (no one has time, the eval harness is
  flaky, or the on-call rotation lost the ritual). Loop the
  engineering lead.
- A breached model has a known security advisory or deprecation
  notice from the provider. Escalate to the security lead — pinned
  state is now a live risk.

## Related

- `apps/api/src/qaforge_api/services/lifecycle_alerts.py` — bridge
  service that emits this alert.
- `apps/api/src/qaforge_api/services/model_lifecycle.py` — registry
  state machine and `awaiting_decision` query.
- [`docs/IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md) Epic
  6.2 — the acceptance criterion this alert defends.
