# Agentic QA Orchestrator — Operator Guide

For ops engineers responsible for installing, upgrading, monitoring,
and recovering an Agentic QA Orchestrator cluster. **Story 5.2's AC** is that an ops
engineer not on the build team can deploy and recover from these
docs alone.

## Table of contents

| # | Page | When to read |
|---|---|---|
| 1 | [Install (local)](install-local.md) | First time, or repro a bug locally |
| 2 | [Install (cloud) — chooser](install-cloud.md) | Production / staging — pick a provider |
| 2a | [Install on AWS](install-aws.md) | Step-by-step AWS deploy (Terraform + Helm) |
| 2b | [Install on GCP](install-gcp.md) | Step-by-step GCP deploy (`gcloud` + Helm) |
| 3 | [Upgrade](upgrade.md) | New release lands |
| 4 | [Backup & restore](backup-restore.md) | DR drill / data corruption |
| 5 | [Monitoring](monitoring.md) | Setting up Grafana / alerts |
| 6 | [Troubleshooting](troubleshooting.md) | Something is on fire |

## Existing runbooks (cross-reference)

* [Disaster recovery (Story 3.6.3)](../runbooks/disaster-recovery.md)
* [Runbook index (Story 4.2)](../runbooks/index.md)
* [Post-mortem template](../runbooks/postmortem-template.md)

## Architecture cheat-sheet

The platform has four planes (PRD §11). For ops, the relevant
deploy targets are:

* **Control Plane** — `apps/api` FastAPI; deploy via Helm.
* **Storage** — Postgres (RLS-enforced), Redis (Celery + locks),
  S3 (evidence), Secrets Manager.
* **Workers** — agents run in the same pod as the API by default
  (Phase 3); split-pod deploy is a Phase-5 toggle.

Trust boundaries are documented in
[`docs/security/threat-model.md`](../security/threat-model.md).

## Conventions in this guide

* Every command assumes you're at the repo root.
* `$WORKSPACE_ID` / `$TOKEN` are env vars you set yourself.
* Commands that mutate state are clearly marked **(mutates)**.
