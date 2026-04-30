# Demo video — script + storyboard

Recorded video deferred per the agreed Phase-5 cuts (no hosted
platform yet). This page is the **director's cut** — the script and
the shot list. Re-record after the cluster is live.

**Target length:** 90 seconds. Two minutes max if the demo gets
chatty.

## The narrative arc

The demo follows the PRD §21 e-commerce scenario: a PR changes
`checkout` discount logic. We watch QAForge classify the failure as
a real defect (not a flake), file a Jira ticket only after a human
approves, and produce a report a release manager actually wants to
read.

## Shot list

| # | Shot | Dwell | What's on screen |
|---|---|---|---|
| 1 | PR opens (GitHub UI) | 4s | "Reduce minimum cart for free shipping from $50 to $0." Red diff on `discount.ts`. |
| 2 | Action triggers (GitHub Actions tab) | 3s | `qaforge-action@v1` running. |
| 3 | API live tail (terminal) | 6s | `qaforge_api` JSON logs: ingest → plan → run → classify → report. |
| 4 | Plan-review (CLI or web stub) | 6s | Test plan: 2 API tests + 1 negative-discount UI test + 1 DB invariant. |
| 5 | Test execution | 8s | Runner output, two failures: (a) negative-discount accepted, (b) free-ship invariant violated. |
| 6 | Classifier overlay | 6s | Failure (a) → `product_defect` (0.86); failure (b) → `flaky_test` (0.32 flip-rate, 14d). |
| 7 | Risk score | 5s | Score 67 / High / NO_GO. Top drivers: critical_failures, fail_rate, ownership_gap. |
| 8 | Approval gate | 8s | Reviewer pages open; reviewer approves Jira-ticket creation gate; rejects production-test gate. |
| 9 | PR comment lands | 6s | Single QAForge comment with risk band, top drivers, evidence link. |
| 10 | Audit log + cost | 5s | `usage_summary`: $0.42 / $5.00; audit log with HMAC signature ✓ green. |

## Voice-over key lines

> "QAForge reads the PR, plans the right tests, runs them, and tells
> you whether to ship — with evidence."

> "It distinguishes a real defect from a flake by looking at the
> test's 14-day flip rate, not just the latest failure."

> "Destructive actions wait for a human. Approvals are
> audit-logged with HMAC signatures, so reviewer attribution
> survives."

> "The release-risk score is built from ten objective signals — fail
> rate, critical failures, change volume, recent incidents,
> ownership, security sensitivity, untested high-risk modules,
> historical defect density, flakiness, uncovered acceptance
> criteria."

> "All of that lands on the PR in under 60 seconds."

## Recording checklist

- [ ] Hosted dev cluster live with the seed workspace.
- [ ] Sample app forked + a precomputed PR with the right diff.
- [ ] Browser at 1440×900, code at 14pt, terminal at 16pt.
- [ ] Hide secrets; redactor should mask anything that slips.
- [ ] Watch wall clock: aim for end-to-end ≤ 90s.

## Post-record

Upload to Loom (unlisted) + cross-link from this page + the
top-level README.
