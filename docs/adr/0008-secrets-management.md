# ADR-0008: Secrets management — cloud-native KMS + secret manager, Vault optional, `.env` for local

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** Security, SRE
- **Informed:** All eng

## Context

Agentic QA Orchestrator handles three classes of secrets:

1. **Platform secrets** — DB passwords, broker credentials, LLM provider API keys, GitHub App private key, SSO client secrets.
2. **Per-workspace secrets** — customer-supplied API tokens for systems-under-test (Postman auth, target API tokens, DB read-only credentials).
3. **Per-run ephemeral secrets** — short-lived tokens minted for a single test run.

PRD §14.2 requires secret redaction in logs/reports, encrypted evidence storage, and signed CI webhooks. Story 0.4.3 covers in-process redaction; this ADR is about how secrets enter the process and how they're stored at rest.

We must avoid: secrets in env files in prod; secrets in DB rows in plaintext; one global key that decrypts everything across tenants.

## Decision

Three layers, one interface:

- **Local / CI**: `.env` resolved by `pydantic-settings`; `.env.example` is the canonical list; pre-commit hook rejects new `.env` content with realistic-looking secrets via gitleaks.
- **Production platform secrets**: cloud-native secret manager — **AWS Secrets Manager** (primary target) or **GCP Secret Manager**; pods receive secrets via CSI Secret Store driver mounting them as files, never as env vars persisted in pod specs.
- **Per-workspace customer secrets**: stored in Postgres in the `secrets` table as **envelope-encrypted ciphertext**. The data key is per-workspace; the data key is wrapped by a tenant-scoped KMS CMK (AWS KMS / GCP KMS). Decryption requires the request to be in-tenant (RLS, ADR-0007) **and** the calling principal to hold the `secrets:read` permission.
- **Per-run ephemeral secrets**: minted at run start, kept only in worker memory, redacted at every log sink, and discarded when the run ends.

A single internal `SecretResolver` interface abstracts all three. Code never reads `os.environ` directly for a secret-looking value; it asks the resolver. **HashiCorp Vault** is supported as an alternate backend behind the same interface for self-hosted deployments — not a Phase 1 install target.

Operational rules:

- Rotation: platform secrets rotated quarterly via secret-manager rotation rules; workspace secrets rotated on customer command; any compromise triggers immediate rotation runbook.
- Never log a secret value, even truncated; redaction utility (Story 0.4.3) is the last line.
- KMS keys are CloudTrail/Audit-Log enabled; every decrypt is a `audit_events` row.

## Consequences

- **Positive:** managed services do the hard parts (rotation, audit, hardware-backed keys); per-tenant CMKs limit blast radius; a single resolver lets agents and tools stay agnostic.
- **Negative:** cloud-native managers add per-API-call latency (~10–30 ms) on cold path — we cache decrypted values for the duration of a request only. KMS pricing scales with calls, not data, so encrypt/decrypt patterns matter; we encrypt long-lived secrets once, decrypt on demand, and avoid loops over many small secrets.
- **Neutral:** requires IAM policy hygiene (`secretsmanager:GetSecretValue`, `kms:Decrypt`) per pod identity; this is a Helm/Terraform output rather than an application concern.

## Alternatives considered

- **HashiCorp Vault as primary** — most flexible, least vendor-locked, but standing up Vault HA is non-trivial ops; Phase 1 doesn't justify it. Available as a backend; not the default.
- **Sealed Secrets / SOPS in git** — fine for static config, doesn't fit per-workspace secrets that are written through the API.
- **Plaintext in DB + disk encryption only** — fails Story 3.1.1 isolation guarantees and PRD §14.2 in spirit even if disks are encrypted.
- **Single global encryption key for all workspace secrets** — one compromise = total loss; rejected.

## References

- PRD §14.2 (Security)
- Story 0.4.3 (Secret redaction utility)
- ADR-0005 (Object storage — encryption-at-rest)
- ADR-0007 (Multi-tenancy — RLS)
- `docs/security/data-handling.md`
