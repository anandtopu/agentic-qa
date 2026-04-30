# Release risk dashboard

The risk score is **evidence-based, not vibes** (PRD §9.9). Story
2.3 ships the engine; Story 2.3.3 attaches the explanation.

## Inputs (PRD §9.9)

Ten signals, each normalised to 0..1, weighted, summed, and clamped
to 0..100:

| # | Signal | Weight | Source |
|---|---|---|---|
| 1 | `fail_rate` | 0.20 | failures / total tests |
| 2 | `critical_failures` | 0.15 | high/critical-severity test count |
| 3 | `uncovered_acceptance` | 0.10 | uncovered ACs / total ACs |
| 4 | `flakiness` | 0.05 | rolling 14-day flip-rate |
| 5 | `change_volume` | 0.10 | (added + removed) / 500 saturation |
| 6 | `historical_defect_density` | 0.10 | defects/kloc historical |
| 7 | `recent_incidents` | 0.10 | incidents in last 90d |
| 8 | `ownership_gap` | 0.05 | unowned / solo / team-owned |
| 9 | `security_sensitivity` | 0.10 | none / low / medium / high |
| 10 | `untested_high_risk_modules` | 0.05 | unowned + high-risk modules |

Weights sum to 1.0; the constructor validates this.

## Bands (PRD §9.9)

| Score | Band | Recommendation |
|---|---|---|
| 0–30 | low | go |
| 31–60 | medium | go_with_approval |
| 61–80 | high | no_go |
| 81–100 | critical | no_go |

## Worked example — the demo PR

Inputs from the [evidence report](evidence-reports.md):

| Signal | Raw | Normalized | Contribution |
|---|---|---|---|
| fail_rate | 2/13 = 0.154 | 0.154 | 0.031 |
| critical_failures | 1 | 0.20 | 0.030 |
| uncovered_acceptance | 0/4 | 0.00 | 0.000 |
| flakiness | 0.00 | 0.00 | 0.000 |
| change_volume | 287 lines | 0.574 | 0.057 |
| historical_defect_density | 1.2/kloc | 0.24 | 0.024 |
| recent_incidents | 1 | 0.20 | 0.020 |
| ownership_gap | team_owned | 0.00 | 0.000 |
| security_sensitivity | medium | 0.60 | 0.060 |
| untested_high_risk_modules | ['discount'] | 0.33 | 0.017 |
| **Sum (×100, rounded)** | — | — | **24** |

That's a "low" score — but the **gate also blocks** because of one
critical product defect; that's what Phase-3's recommendation logic
captures (Story 2.3.3 escalates a critical_failures > 0 to NO_GO
even when the band is below threshold).

> Sample numbers — the live demo lands somewhere different.

## Top drivers (the explanation)

The dashboard surfaces the **top three drivers by contribution**
(Story 2.3.3 AC: ≥ 3 drivers per score):

```text
1. security_sensitivity   (weight 0.10 × raw 0.60 = 0.060)
2. change_volume          (weight 0.10 × raw 0.574 = 0.057)
3. fail_rate              (weight 0.20 × raw 0.154 = 0.031)
```

This is the panel a release manager skims first.

## Untested high-risk modules

The scorer carries `untested_high_risk_modules` separately from the
score — it's the actionable list. For the demo PR, it's `['discount']`.
Reviewers can see "this module changed and the test plan didn't
cover it" without having to read the full report.

## Backtest target (deferred)

PRD AC: ≥ 0.7 ROC-AUC against a labelled "shipped → incident" set.
No labelled corpus exists yet; the rubric is calibrated to the
bands by construction. Backtest is a Phase-6 carry-forward.
