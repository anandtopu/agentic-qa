# Post-mortem template

**Story 4.2** AC: post-mortem published within 5 business days of a
SEV1 / SEV2 resolution. Copy this file into `docs/postmortems/<date>-<slug>.md`
and fill it out.

---

# {{ Title — what failed, in one sentence }}

**Severity:** SEV1 / SEV2
**Status:** open / in-review / closed
**Authors:** {{ name(s) }}
**Date opened:** YYYY-MM-DD
**Date resolved:** YYYY-MM-DD HH:MM UTC
**Date published:** YYYY-MM-DD

## Summary

One paragraph. What broke, who noticed, how long it lasted, what the
impact was. Skim-readable on a mobile.

## Impact

- **Users affected:** N tenants / M test runs blocked
- **Duration of customer impact:** start → end (UTC)
- **SLO budgets burned:** which SLOs and by how much
- **Data loss / integrity:** none / partial / scope

## Timeline

All times UTC. Lift directly from `audit_events` + Slack-incident
channel + on-call paging history.

| Time | Event |
|---|---|
| HH:MM | First symptom (e.g. SLO burn alert fired) |
| HH:MM | First responder acknowledged page |
| HH:MM | Mitigation deployed |
| HH:MM | Service restored |
| HH:MM | Incident channel closed |

## Root cause

What actually broke. Be technical and specific. Cite commit SHAs,
config diffs, log lines, runbook entries that did/didn't help.

## Detection

- How was the incident detected? (alert / customer report / on-call
  noticing)
- Time-to-detection from first symptom: N minutes
- What signal would have caught this earlier?

## Mitigation

What fixed the immediate symptom. Distinguish from the **fix** below.

## Fix

What permanent change has shipped (or will ship) so this can't
recur? Link the PR / change request.

## Action items

| # | Item | Owner | Due | Issue |
|---|---|---|---|---|
| 1 | ... | @who | YYYY-MM-DD | #... |
| 2 | ... | @who | YYYY-MM-DD | #... |

Every action item must have an owner + a due date. Tracking happens
in the linked issue, not in this doc.

## What went well

What we did right. Don't skip this — it's how good runbooks survive.

## What went poorly

What we'd change. Be honest; this is a learning artifact, not a
performance review.

## What surprised us

The thing we didn't expect. Often the most valuable section.

## Where we got lucky

What helped that we didn't earn. (e.g. "the alert fired before
customer traffic peaked.")

## Glossary / context

Optional — terms or systems an outsider needs to understand the
timeline.
