# Cost & latency benchmarks

PRD §14.5 lists six capability budgets; Epic 4.5 ships the
:class:`PerfBudget` engine that evaluates them, the k6 scenarios
that load-test against them, and the caching primitives that help
hit them.

## Targets (PRD §14.5)

| Capability | Ceiling | Warn (80%) |
|---|---|---|
| PR analysis | 60 s | 48 s |
| Test plan generation | 90 s | 72 s |
| API smoke run | 3 min | 2:24 min |
| UI smoke run | 10 min | 8 min |
| Failure classification | 60 s | 48 s |
| Evidence report generation | 30 s | 24 s |

The same numbers live in
`apps/api/src/aqao_api/perf/budgets.py` and
`perf-tests/lib/checks.js`; the drift-guard test asserts they
match.

## Verdicts

`evaluate_perf_run(samples)` returns one of:

* **PASS** — every sample under the warn threshold.
* **WARN** — one or more samples between warn and ceiling.
* **FAIL** — one or more samples exceeded the ceiling.

The overall verdict for a run is `max(verdicts)` — any FAIL
trumps any WARN.

## Cost budgets

Per-run cost cap defaults to **$5.00** with a 5% slack
(Story 2.5.1's `BudgetEnforcer`). Mid-flight kill-switch fires when
projected spend would exceed `1.05 × max_cost_usd_per_run`.

Per-agent cost is recorded in `usage_records`; per-workspace rollup
is served at `GET /api/v1/usage/summary` with `by_agent` and
`by_provider` breakdowns.

## Sample numbers (synthetic)

Until a hosted run exists, here are *projected* numbers from the
in-process timing tests + the agent design:

| Capability | p50 | p95 | Verdict |
|---|---|---|---|
| PR analysis | 11 s | 22 s | PASS |
| Test plan generation | 9 s | 16 s | PASS |
| Failure classification | 6 s | 18 s | PASS |
| Evidence report | 3 s | 8 s | PASS |
| API smoke | 24 s | 56 s | PASS |
| UI smoke | 2 m | 5 m | PASS |

Real numbers come from the k6 scenarios under `perf-tests/`; rerun
once the dev cluster is live (Story 5.5 onboarding).

## Caching wins

Three caches help hit the budgets without throwing more compute
at the problem (Story 4.5):

* `LruCache` (TTL + eviction stats) — generic.
* `EmbeddingCache` keyed by `sha256(model::text)` — content-
  addressed; cross-model collision-safe.
* `PlanReuseCache` keyed by `(workspace_id, requirement_hash)` —
  two PRs touching the same requirement share planner output.

Hit rates are exposed on each cache's `.stats` field; when the
hosted cluster is up, surface them as Prometheus metrics + Grafana
panels.

## 10× concurrency target (deferred)

PRD §14.5 AC: all targets met at 10× expected concurrency. The k6
scenarios ramp linearly from 0 → 10× over 60s and hold for 5
minutes. Real run deferred until a deployed cluster exists; the
scripts are committed and the assertions are wired.
