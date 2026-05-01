# `aqao/aqao-action@v1`

Run Agentic QA Orchestrator on every pull request. The action:

1. Starts a `test_run` against an existing `test_plan_id`.
2. Polls until the run reaches a terminal state (`done` / `failed` /
   `paused_for_approval`).
3. Renders a compact summary and posts/updates a PR comment in place
   (no spam — uses a hidden marker for idempotent updates).
4. Exits non-zero when the configured risk threshold is breached.

> **Phase 1 scope.** The action expects you to have a `test_plan_id` already
> (run the Planner via `POST /api/v1/test-plans` ahead of time). Phase 2
> wires automatic plan generation from the PR diff via the existing GitHub
> webhook (Story 1.2.1) so the action input drops to zero.

## Sample workflow (Story 1.9.1 AC: < 10 lines)

```yaml
name: aqao
on: { pull_request: { types: [opened, synchronize] } }
jobs:
  qa:
    runs-on: ubuntu-latest
    steps:
      - uses: aqao/aqao-action@v1
        with:
          aqao-url: https://api.aqao.ai
          aqao-token: ${{ secrets.AQAO_TOKEN }}
          workspace-id: ${{ vars.AQAO_WORKSPACE_ID }}
          test-plan-id: ${{ vars.AQAO_TEST_PLAN_ID }}
```

Eight non-comment lines. Story 1.9.1 AC met.

## Inputs

| Input | Required | Default | Notes |
|---|---|---|---|
| `aqao-url` | yes | — | Trailing slashes stripped automatically. |
| `aqao-token` | yes | — | Bearer token. Pass as a secret. |
| `workspace-id` | yes | — | UUID. Phase 1 reuses this as the tenant header. |
| `test-plan-id` | yes (Phase 1) | — | Phase 2 makes this optional. |
| `risk-threshold` | no | `0` | Maximum `product_defect` count before the gate fails. Phase 2 swaps to a 0–1 score. |
| `poll-interval-seconds` | no | `10` | |
| `poll-timeout-seconds` | no | `1800` | 30 min ceiling. |

The action reads `GITHUB_TOKEN` from the runner environment for PR
commenting. Grant `pull-requests: write` on the workflow:

```yaml
permissions:
  pull-requests: write
  contents: read
```

## Outputs

| Output | Notes |
|---|---|
| `test-run-id` | UUID of the started run. |
| `final-state` | `done` / `failed` / `paused_for_approval`. |
| `failure-count` | Total `failure_classifications` recorded. |
| `product-defect-count` | Subset gating the merge. |
| `pr-comment-url` | URL of the Agentic QA Orchestrator PR comment. |

## Quality gate (Story 1.9.3)

The action exits non-zero when:

- `final-state` is `failed`, **or**
- `product-defect-count > risk-threshold`.

`paused_for_approval` does **not** fail the gate — the PR comment surfaces
the gate; the workflow author can chain a manual job that resumes after
human approval (Phase 2 Approvals).

## Branch protection

The action's exit code drives a required check on the protected branch.
Bypass requires admin per GitHub's existing branch-protection model — no
Agentic QA Orchestrator-side setting affects this. Story 1.9.3 AC: gate respects branch
protection, bypass requires admin.

## Building locally

```bash
npm install
npm run typecheck
npm run lint
npm run build   # writes dist/index.js (committed alongside action.yml)
```

GitHub runs `dist/index.js` directly — bundling is required for every
release. CI in this repo lints and typechecks; the actual `dist/` build
step lands in Phase 4 hardening (cosign-signed releases).
