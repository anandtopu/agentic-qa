# CI/CD run screenshots

Screenshots will land here after the first hosted run lands. This
page is the **storyboard** + **caption track** so a future maintainer
knows what each screenshot is meant to show.

## Storyboard

| Image | Caption |
|---|---|
| `pr-comment.png` | The single Agentic QA Orchestrator PR comment. Shows risk band (medium 53/100), top-3 drivers, 5 failures classified, evidence-report link. |
| `actions-tab.png` | GitHub Actions run summary — `aqao-action@v1` job status + the structured outputs (`risk-score`, `risk-band`, `risk-recommendation`). |
| `gate-block.png` | A `max-risk-band: medium` workflow that **failed** because the run came back HIGH. The action's `Failed` summary surfaces the band + the score. |
| `approval-flow.png` | Reviewer hitting `POST /api/v1/approvals/{id}/approve` from the Phase-3 admin queue. Screenshot includes the pre/post audit-log entry with HMAC signature. |
| `evidence-report.png` | The Markdown evidence report rendered in GitHub: scope, coverage matrix, pass/fail summary, classification breakdown, screenshots, API evidence, DB validation, agent confidence, cost+latency, approvals, go/no-go. |
| `risk-explainer.png` | The release-risk score explainer panel: each driver with its weight, raw value, and contribution. Demonstrates "evidence-based, not vibes" (PRD §9.9). |
| `audit-export.png` | CSV export of the audit log via `GET /api/v1/audit/export.csv` — every row carries `signature_status: signed_ok`. |

## Capture conventions

* **Browser**: Chrome 124+, 1440×900, light theme, no extensions.
* **Annotations**: red rectangle on the focal area, 2px border. Use
  `cleanshot` or `flameshot`; export at 2× DPI as PNG.
* **Filenames**: `<slug>.png` — match the storyboard table above so
  cross-references survive.
* **Privacy**: redactor pipeline (Story 0.x) handles secrets but
  always double-check by hand; no real workspace ids visible.

## Status

| Item | Status |
|---|---|
| Storyboard documented | ✅ Story 5.4 |
| Actual screenshots checked in | ⏳ deferred until a hosted run exists |
| README link from `README.md` | ✅ via `docs/portfolio/index.md` |
