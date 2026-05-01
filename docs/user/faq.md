# FAQ

## Q: How is this different from CI test orchestration tools?

We don't run your tests faster — we **generate** them, classify the
failures by category (`product_defect` vs `test_issue` vs
`flaky_test` vs `environment_issue`), and produce a release-risk
score from objective signals. The tests still run wherever you run
them today; Agentic QA Orchestrator sits **above** that layer.

## Q: Where do my secrets go?

Every text sink runs through `aqao_redaction.default_redactor()`
before it's written to logs, the audit table, the evidence report,
or a PR comment. The property-based tests under
`packages/redaction/tests/` are the contract.

## Q: How does the risk score get calibrated?

Phase 3 ships rule-based weights anchored to PRD §9.9 inputs. A
backtest against historical "shipped → incident" labels lands as a
follow-up once a labelled corpus exists; until then the weights are
calibrated to the bands (Low / Medium / High / Critical) by
construction.

## Q: My test is flagged `flaky_test` but I'm sure it's a real bug.

Check the test's 14-day flip-rate via
`/api/v1/workspaces/{id}/flakiness/{test_id}`. If the flip-rate is
< 0.30, the heuristic classifier won't downgrade a 5xx-driven
classification — open an issue with the failure id and we'll dig
in.

## Q: What about cost?

Every agent call records token + dollar cost into `usage_records`
(Story 2.5.1). The `BudgetEnforcer` mid-flight kill switch caps
runs at the workspace policy's `max_cost_usd_per_run` with 5%
slack. Pull `/api/v1/usage/summary` for a workspace-level rollup by
agent and provider.

## Q: How do I roll a prompt back?

Set the workspace's prompt pin to the older version. Story 3.4.1
exposes pins at the service layer; the REST surface to flip them is
in flight. The pin is audit-logged and shows up in the operator's
queue.

## Q: Can I A/B test a new prompt?

Yes — Story 3.4.2 ships the experiment framework. Define a
`PromptExperiment` with two variants and weights summing to 1.0;
the `ExperimentSelector` deterministically routes by
`(experiment_id, key)` hash so the same workspace always sees the
same variant during the experiment. Promotion of the winner sets
the pin via `prompt_pin.promote` for audit-log distinction.

## Q: How do I self-host?

See the [operator docs](../operator/install.md). Terraform modules
live under `infra/terraform/`; the hardened Helm chart is under
`infra/helm/aqao-api/`. Both are agreed Phase-3 deferred items
for the cloud apply itself; the artifacts are production-shaped.

## Q: What's the SLO?

API availability ≥ 99.9% over 30 days, PR analysis < 60s p95,
classification < 60s p95. Full list in
`apps/api/src/aqao_api/slo/defaults.py` (Epic 4.1).

## Q: How does Agentic QA Orchestrator handle a flood of webhook events?

Per-workspace bulkheads (Epic 4.3) cap concurrency on a shared
worker pool so one tenant's burst can't starve another. Excess
requests get HTTP 429 — the runner backs off + retries.

## Q: What happens if the LLM provider goes down?

The classifier falls back to the heuristic path (Epic 4.3 chaos
test verifies this). The platform stays operational in degraded
mode until the circuit breaker's recovery_timeout elapses; one
trial call then decides whether to close the breaker.

## Q: Can I run Agentic QA Orchestrator on-prem?

The Helm chart is provider-agnostic; the Terraform modules target
AWS today. GCP / Azure parity is on the Phase-5 backlog.

## Q: Where do I file a bug?

GitHub Issues against `aqao/aqao` with the `bug` label.
Include the test_run id and the relevant correlation id from the
PR comment.
