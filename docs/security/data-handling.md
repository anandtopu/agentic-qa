# Data Handling Policy

Baseline classification, retention, and encryption posture. Reviewed by
Security; updated when new data types or integrations land.

## Data classes

| Class | Examples | Encryption at rest | Encryption in transit | Notes |
|---|---|---|---|---|
| **Secrets** | API keys, JWT signing keys, GitHub app private keys, OAuth client secrets | KMS-wrapped | TLS ≥ 1.2 | Never persisted in app DB; vault-only. Surfaced to runtime via short-lived in-memory handles. Redactor (Story 0.4.3) prevents accidental log emission. |
| **PII** | User email, name, IDP subject | AES-256 (DB-level) | TLS ≥ 1.2 | Limited to `users` table. No PII in logs, evidence, or reports. |
| **Customer source code** | Cloned PR diffs, file contents during retrieval | AES-256 (object store) | TLS ≥ 1.2 | Held only in the Intelligence Plane retrieval cache; TTL ≤ 24 h. |
| **Test artifacts** | Screenshots, traces, network logs, request/response bodies | AES-256 (object store) | TLS ≥ 1.2 | Redactor applied before write. Default retention 90 days. |
| **Agent inputs/outputs** | Prompts, completions, tool args, tool results | AES-256 (DB / object store) | TLS ≥ 1.2 | Redacted on write. Required for audit, eval regression, and cost reporting. |
| **Operational telemetry** | Traces, metrics, structured logs | Per-vendor at rest | TLS ≥ 1.2 | Trace-id only; no PII; retention 30 days hot, 1 year cold. |

## Retention defaults

| Class | Retention | Override |
|---|---|---|
| Secrets | Until rotated; rotation cadence ≤ 90 days | Per-workspace policy |
| PII | Account lifetime + 30 days | DSAR / deletion request honoured ≤ 30 days |
| Source code cache | 24 h | Per-workspace |
| Test artifacts | 90 days | Per-workspace, max 365 days |
| Agent inputs/outputs | 90 days | Per-workspace, max 365 days |
| Audit events | 7 years | Compliance-locked; never shorter |
| Telemetry | 30 days hot / 365 days cold | Fixed |

## Residency

- Default region: `us-east-1` for the demo / portfolio deployment.
- Multi-region residency is an MVP-3+ concern. Until then, customers requiring EU residency are deferred.

## Encryption posture

- **At rest:** RDS storage encryption + S3/GCS bucket encryption with KMS-managed keys. Per-tenant CMKs deferred to MVP-3.
- **In transit:** TLS ≥ 1.2 enforced at the load balancer and on internal service-to-service calls. Webhook receivers verify HMAC signatures (PRD §14.2).

## Redaction guarantees

- Every sink that persists or surfaces text routes through `qaforge_redaction.redact` (Story 0.4.3).
- Property-based tests assert redaction is idempotent and never produces a residual pattern match.
- Workspace-injected secrets (e.g., a configured API key) are also exact-string scrubbed via `Redactor.with_extra(strings=…)`.

## Open questions

- Per-tenant KMS key rotation cadence — Q-001 in `docs/prd-questions.md`.
- DSAR tooling: do we build an admin endpoint or rely on manual SQL? Decide before MVP-3.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Security lead | | |
| Eng director | | |
