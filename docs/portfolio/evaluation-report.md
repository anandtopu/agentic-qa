# Evaluation report

Story 2.6 ships a custom Python eval harness (per ADR-0010 — no
LangSmith / Promptfoo dependency). Story 3.5 wraps it in a nightly
multi-agent runner with a trend store + alert pipeline.

## Harness shape

* :class:`EvalCase` (id + inputs + expected) loaded from
  `packages/eval/datasets/<agent>/<version>.jsonl`.
* :class:`EvalRunner` runs an agent_fn against the dataset's cases.
* Five built-in scorers:
  * `FieldExactMatchScorer`
  * `CategoricalAccuracyScorer`
  * `JsonSchemaValidScorer`
  * `LatencyBudgetScorer` (linear falloff to 0.0 at 2× budget)
  * `CostBudgetScorer` (same shape with Decimal handling)
* :class:`Scorecard` JSON output (`SCORECARD_VERSION = "1.0.0"`).
* :class:`BaselineGate` diffs scorecard vs pinned baseline; both
  `mean` and `pass_rate` per dimension; per-dimension tolerance.

## Sample baseline scorecard (`packages/eval/datasets/example/v1.jsonl`)

```json
{
  "agent_name": "example",
  "dataset_name": "example",
  "dataset_version": "v1",
  "total_cases": 3,
  "overall_pass_rate": 1.0,
  "dimensions": [
    {
      "dimension": "exact_match:answer",
      "cases": 3,
      "mean": 1.0,
      "p50": 1.0,
      "pass_rate": 1.0
    },
    {
      "dimension": "latency_budget",
      "cases": 3,
      "mean": 1.0,
      "p50": 1.0,
      "pass_rate": 1.0
    },
    {
      "dimension": "cost_budget",
      "cases": 3,
      "mean": 1.0,
      "p50": 1.0,
      "pass_rate": 1.0
    }
  ]
}
```

## Continuous regression suite (Story 3.5)

* :class:`NightlyRunner` enumerates every (agent, dataset_version)
  pinned in a config and produces a single :class:`NightlyReport`.
* :class:`FilesystemTrendStore` writes one JSON artifact per
  (agent, run_id) plus a flat `index.jsonl` for tail reads.
* :class:`RegressionAlertEmitter` fires:
  * `gate_regression` when the current run regressed past tolerance
    (any dimension's `mean` or `pass_rate` dropped).
  * `trend_decline` when overall pass-rate strictly dropped for
    `window` consecutive runs by more than `decline_threshold`.

## AC verification

> AC (Story 3.5): "Regression catches a planted prompt regression
> within one nightly cycle."

Demonstrated by `test_emitter_fires_gate_regression_alert`
(`packages/eval/tests/test_nightly_and_trend.py`): swap a clean
agent for a deliberately-degraded one after the baseline lands; the
emitter fires `gate_regression` in one cycle.

## Goldens (deferred)

The harness ships with one smoke dataset (3 cases). Curating ≥ 50
golden cases per agent is on the carry-forward list — needs real
prompts + ground truth; the harness mechanics are the deliverable
here.
