# Journey — Release Manager

**Persona ref:** PRD §8.3
**Linked success metric:** Risk score with supporting evidence (PRD §9.9).

## Trigger

A release candidate is being assembled; the RM needs a go/no-go.

## Steps

1. Open the Release Risk dashboard for the workspace.
2. View the candidate's risk score (0–100) with top drivers.
3. Drill into drivers: failed critical tests, untested high-risk areas, flakiness, recent incidents.
4. Approve or reject the release; recorded in `audit_events` and `approval_requests`.

## Expected outputs

- Risk score, band (Low / Medium / High / Critical), and ≥ 3 drivers.
- A go/no-go recommendation with the human-required approvals listed.
- Linked evidence reports for every failed critical test.

## Success metric

- Median time-to-decision ≤ 5 minutes from dashboard open.
- Post-release incident rate on "Low" releases is materially below "High".
