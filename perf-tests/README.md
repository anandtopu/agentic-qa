# Performance load tests — Epic 4.5

[k6](https://k6.io) scripts targeting PRD §14.5 budgets at 10x
expected concurrency. Each script exports its samples to
`results/<scenario>.json` so the in-process
`aqao_api.perf.evaluate_perf_run` consumer can produce a
:class:`PerfBudgetReport`.

## Layout

```
perf-tests/
├── scenarios/
│   ├── pr_analysis.js       PR diff -> first run started
│   ├── test_plan_gen.js     Planner agent end-to-end
│   ├── api_smoke.js         API smoke run
│   ├── failure_classify.js  Classifier round-trip
│   └── evidence_report.js   Report rendering
├── lib/
│   └── checks.js            Shared k6 thresholds + utilities
└── README.md                ← you are here
```

## Acceptance criteria

> AC: All §14.5 targets met at 10× expected concurrency.

The k6 thresholds in each scenario fail the run if p95 exceeds the
PRD ceiling. CI runs the scenarios on a `aqao-perf` GitHub
environment with a deployed dev cluster — **deferred per agreed
Phase-4 cuts** until a dev cluster exists.

## Local invocation

```bash
# Single scenario.
k6 run perf-tests/scenarios/pr_analysis.js \
  -e AQAO_BASE_URL=https://dev.api.aqao.ai \
  -e AQAO_TOKEN=$AQAO_TOKEN \
  --summary-export results/pr_analysis.json

# Whole suite.
for f in perf-tests/scenarios/*.js; do
  k6 run "$f" -e AQAO_BASE_URL=$URL -e AQAO_TOKEN=$TOK \
    --summary-export "results/$(basename $f .js).json"
done
```

## Budget evaluation

After the k6 runs land, evaluate them with the in-process consumer:

```python
from aqao_api.perf import evaluate_perf_run

samples = {
    "pr_analysis": [11_500, 17_200, 22_800, 35_400, 42_100],
    "test_plan_generation": [8_700, 14_300, 21_900],
    # ...
}
report = evaluate_perf_run(samples)
assert not report.has_failures, report.to_dict()
```

A failing budget is a release-blocker; a warn budget is an issue to
investigate before the next sprint review.

## Concurrency profile

PRD §14.5 expected baseline is "10 concurrent PR analyses per
workspace, 100 active workspaces" — 1000 RPS at the analysis tier
and ~5x higher at the agent-task tier. The scripts ramp linearly
from 0 → 10× over 60s, hold for 5 minutes, then ramp down.

## Validation status

| Item | Status |
|---|---|
| Scenario scripts written | ✅ Story 4.5 |
| `evaluate_perf_run` consumer + budgets | ✅ Story 4.5 |
| Real `k6 run` against a dev cluster | ⏳ deferred — needs a deployed cluster |
| 10x concurrency budget verification | ⏳ deferred — same |
