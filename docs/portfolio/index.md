# Portfolio Deliverables

PRD §20 lists twelve artifacts that demonstrate the platform end to
end. Story 5.4 collects them here.

| # | Deliverable | Where |
|---|---|---|
| 1 | GitHub repository | <https://github.com/aqao/aqao> (this repo) |
| 2 | Architecture diagrams | [`architecture.md`](architecture.md) — four-planes + orchestration + PR-flow + approval + eval-gate + deployment + trust-boundary diagrams (mermaid) |
| 3 | Working demo video | [`demo-video.md`](demo-video.md) — script + storyboard (recording deferred) |
| 4 | Sample target application | [`sample-app.md`](sample-app.md) — `examples/checkout-demo/` |
| 5 | Generated test plans | [`generated-test-plans.md`](generated-test-plans.md) — three planner outputs |
| 6 | CI/CD run screenshots | [`ci-runs.md`](ci-runs.md) — annotated PR-action screenshots |
| 7 | Evidence reports | [`evidence-reports.md`](evidence-reports.md) — sample reports |
| 8 | Failure classification examples | [`classification-examples.md`](classification-examples.md) — the five categories with rationale |
| 9 | Release risk dashboard | [`risk-dashboard.md`](risk-dashboard.md) — how the score is built |
| 10 | Evaluation report | [`evaluation-report.md`](evaluation-report.md) — eval-harness baselines |
| 11 | Cost / latency benchmark | [`benchmarks.md`](benchmarks.md) — PRD §14.5 budgets vs measured |
| 12 | Security & audit design | [`security-audit.md`](security-audit.md) — STRIDE + audit-log walkthrough |

## Reading order

If you only have **5 minutes**, read the [demo storyboard](demo-video.md)
+ skim the [risk dashboard](risk-dashboard.md). If you have **30 minutes**,
add [architecture](architecture.md) + [evidence report](evidence-reports.md)
+ [classification examples](classification-examples.md). If you're
evaluating the platform's engineering depth, the [security &
audit design](security-audit.md) + [benchmarks](benchmarks.md) are
the two unique-on-the-market pieces.

## Status

| Item | Status |
|---|---|
| 11 written deliverables | ✅ Story 5.4 |
| Recorded demo video | ⏳ deferred (script lives at `demo-video.md`) — see [`tech-debt.md`](../tech-debt.md) TD-002 |
| Actual screenshot images | ⏳ deferred until a hosted run exists — TD-002 |
| README link table updated | ✅ — `README.md` cross-references this page |
| Phase-6 maintenance shipped on top | ✅ — model lifecycle, feedback loops, retention sweep, access review live; see [`PROGRESS.md`](../PROGRESS.md) |
