# QAForge AI — User Guide

QAForge AI is an agentic QA platform that turns a pull request into a
green test run with **evidence**, **risk score**, and **defect
recommendations** — without you scripting the tests.

## What you'll build

By the end of this guide you'll have:

1. A **workspace** linked to your GitHub repo.
2. A **policy** that controls cost, approval, and destructive-SQL
   behaviour.
3. A working **GitHub Action** that comments on every PR with a
   QAForge run, a release-risk band, and a go/no-go.

**Time budget: 30 minutes.** Story 5.1's AC says a first-run user
reaches a green run in ≤ 30 min using only this guide.

## Table of contents

| Step | Page | Time |
|---|---|---|
| 1 | [Get a workspace](getting-started.md) | 5 min |
| 2 | [Set a policy](policy.md) | 5 min |
| 3 | [Wire the GitHub Action](github-action.md) | 10 min |
| 4 | [Approve, reject, replay](approvals.md) | 5 min |
| 5 | [Read your first run](reading-the-run.md) | 5 min |
| — | [FAQ](faq.md) | — |
| — | [Troubleshooting](troubleshooting.md) | — |

## Concepts in 60 seconds

QAForge orchestrates **ten specialised agents** behind one API:

* **Planner** — turns a requirement + diff into a test plan.
* **API tester / UI tester / DB validator** — generate + run tests.
* **Failure classifier** — `product_defect` vs `test_issue` vs
  `flaky_test` vs `environment_issue`.
* **Release risk scorer** — 0..100 score with top drivers + go/no-go.
* **Reporter** — Markdown evidence report rendered into PR comments.
* **Policy guard** — cost / runtime / destructive-action budgets.

The full spec lives in `AgenticQA_PRD.md` if you want the deep
version.

## Prerequisites

* A GitHub repo you can install an Action on.
* A QAForge workspace token (request via the demo workspace
  signup — Phase-3 SSO deferred).
* `pnpm` 9+ if you want to run the demo locally.

If you only have 5 minutes today, skip to [Get a workspace](getting-started.md)
and bookmark the rest.
