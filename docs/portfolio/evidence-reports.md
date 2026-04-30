# Evidence reports

The evidence report is the artifact a release manager actually wants
to read. PRD §9.11 names every section the report must include;
Story 1.8 ships the Jinja2 renderer that produces them.

## Sample report — `tr-2026-05-01-checkout-7f3a`

> *Excerpted; the live version is rendered to Markdown + uploaded to
> S3 + linked from the PR comment.*

### Release summary

* **Repository**: `qaforge-demo/checkout`
* **PR**: #142 — "Reduce free-ship threshold from $50 to $0"
* **Author**: @kim (engineer)
* **Run**: tr-2026-05-01-checkout-7f3a
* **Duration**: 3 min 12s
* **Cost**: $0.42 of $5.00 budget
* **Final state**: failed (release_readiness rejected)

### Scope tested

| Layer | Generated | Passed | Failed |
|---|---|---|---|
| API | 6 | 4 | 2 |
| UI | 3 | 3 | 0 |
| DB invariants | 4 | 4 | 0 |
| **Total** | **13** | **11** | **2** |

### Failure classification

| Test | Category | Confidence | Rationale |
|---|---|---|---|
| `test_negative_discount_rejected` | `product_defect` | 0.86 | Discount validator accepted `-10`; expected HTTP 422. |
| `test_freeship_invariant_holds` | `flaky_test` | 0.62 | 14-day flip-rate 0.42 — race on inventory decrement. |

### Risk score

* **Score**: 67 / 100 — **High**
* **Recommendation**: `no_go` (block release)
* **Top drivers**:
  1. `critical_failures` — 1 high-severity test failed (weight 0.15 × 0.5 = 0.075)
  2. `fail_rate` — 2/13 (15%) — (weight 0.20 × 0.15 = 0.030)
  3. `change_volume` — 287 lines added (weight 0.10 × 0.57 = 0.057)

### API evidence

For each failed API test, the report carries:

* The exact HTTP request/response, redacted via the redaction layer.
* The handler trace from the API logs (correlation-id matched).
* The DB diff between pre-run and post-run snapshots (Story 2.2.2).

### UI evidence

Screenshots + traces from Playwright (Story 1.5.2). Screenshots are
stored in S3 at `evidence/<run_id>/ui/<test_id>/screenshot.png`
behind a signed URL with audit-logged access (Story 1.8.2).

### DB validation evidence

Schema-constraint checks + orphan detection (Story 2.2.1). Two
findings: zero orphans, four NULLs in `audit_events.signature` from
pre-Story-2.4.1 rows (warning, not error).

### Agent confidence

| Agent | Latest version | Eval pass-rate (7d) |
|---|---|---|
| Planner | 1.0.0 | 96% |
| API tester | 1.0.0 | 91% |
| Failure classifier | 1.0.0 | 88% |
| Reporter | 1.0.0 | 100% |

### Cost & latency

| Stage | p50 | p95 | Cost |
|---|---|---|---|
| Plan | 18s | 32s | $0.08 |
| Execute | 92s | 124s | $0.05 |
| Classify | 7s | 14s | $0.21 |
| Report | 4s | 9s | $0.08 |
| **Total** | **3m12s** | — | **$0.42** |

### Human approvals

| Gate | Decision | By | Comment |
|---|---|---|---|
| `external_ticket_creation` | approved | @kim (admin) | "yes, file the Jira" |
| `release_readiness` | rejected | @kim (admin) | "fix discount validator first" |

### Go / no-go recommendation

> **Block release.** One critical product-defect failure + a band of
> High. Top driver is the negative-discount path; expected fix
> < 1 day. Rerun once `discount.py` is patched.

## How to read an actual report

1. Open the **PR comment** for the link.
2. Skim **Release summary** + **Risk score**.
3. If risk is High/Critical, jump straight to **Failure
   classification** — the top-confidence `product_defect` rows are
   your fix targets.
4. Use **API evidence** + **DB validation** to reproduce.

## Status

| Item | Status |
|---|---|
| Sample report shape | ✅ Story 5.4 (this page) |
| Live S3-stored sample | ⏳ deferred until a hosted run exists |
| Renderer implementation | ✅ Story 1.8 — `qaforge_agents.reporter.MarkdownRenderer` |
