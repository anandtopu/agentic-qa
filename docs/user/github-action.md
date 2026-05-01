# 3. Wire the GitHub Action

The Agentic QA Orchestrator action ships from `infra/github-action/` and is published
as `aqao/aqao-action@v1`. Story 1.9.1's AC was a sample app
integrating in fewer than 10 lines of YAML — that's the spec your
workflow file should hit.

## The minimal workflow

`.github/workflows/aqao.yml`:

```yaml
name: Agentic QA Orchestrator
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  aqao:
    runs-on: ubuntu-latest
    steps:
      - uses: aqao/aqao-action@v1
        with:
          aqao-url: https://api.aqao.ai
          aqao-token: ${{ secrets.AQAO_TOKEN }}
          workspace-id: ${{ vars.AQAO_WORKSPACE_ID }}
          max-risk-band: medium
```

That's the whole thing. Store `AQAO_TOKEN` as a repo secret and
`AQAO_WORKSPACE_ID` as a repo variable.

## What the action does

1. Forwards the PR diff to Agentic QA Orchestrator's webhook endpoint (HMAC-signed).
2. Polls the resulting `test_run` until it reaches a terminal state
   (`done | failed | paused_for_approval`).
3. Pulls failure classifications + the **release-risk band**
   (Story 2.3.3).
4. Posts (or updates in place) a single PR comment summarising the
   run.
5. Exits non-zero if the band exceeds `max-risk-band` or the
   product-defect count exceeds `risk-threshold`.

The full input/output reference is in
[`infra/github-action/action.yml`](../../infra/github-action/action.yml).

## Tighten the gate

Two gates available on the action:

* `max-risk-band: low | medium | high | critical` — preferred.
  Reads the `risk_score` produced by the Release Risk Scoring agent.
* `risk-threshold: <int>` — legacy. Counts `product_defect`-classed
  failures.

If your release process is risk-band-driven, set
`max-risk-band: medium` and leave `risk-threshold` at its default of
0. The band gate fires first; the count gate is a fallback for
deployments that haven't yet wired the scorer into the orchestrator
graph.

## Verify

Open a PR and watch the Actions tab. Within ≤ 60s (Phase-4 SLO) you
should see a Agentic QA Orchestrator comment land with:

* score + band (`low/medium/high/critical`)
* top three drivers
* go/no-go recommendation
* link to the evidence report

## Next

→ [4. Approve, reject, replay](approvals.md)
