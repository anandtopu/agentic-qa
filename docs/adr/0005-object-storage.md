# ADR-0005: Object storage — S3-compatible, MinIO local, S3 in cloud

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** SRE, Security
- **Informed:** All eng

## Context

PRD §11.2 + §14.3 require artifact storage in S3/GCS-compatible storage; PRD §16 already uses MinIO locally. Evidence artifacts (Playwright traces, screenshots, video, Newman bodies, SQL diff payloads, generated reports — see Story 1.8) must be:

- **Tamper-evident** (Story 1.6.3 acceptance criterion: SHA-256 content addressing).
- **Durable for ≥ 90 days** (Story 1.8.2).
- **Shared via signed URLs** with TTL.
- **Region-aware** (Story 0.1.3 data-handling baseline).

We need one storage interface that works across local dev, staging, and prod without #ifdef.

## Decision

Use the **S3 API as the single object-storage interface**, accessed via `boto3` (sync) and `aiobotocore` (async). Implementations:

- **Local / CI**: MinIO (already in `infra/docker/docker-compose.yml`).
- **AWS prod**: AWS S3.
- **GCP prod**: GCS via its S3-compatible interoperability mode, behind the same `boto3` config; alternatively the native GCS client behind the same internal `ObjectStore` interface if interop friction emerges.

Conventions:

- One bucket per environment, prefixed by tenant: `aqao-<env>` and keys `t/<tenant>/w/<workspace>/r/<run>/<sha256>/<filename>`.
- Content addressing: every artifact write computes SHA-256 client-side; the SHA is part of the key; we reject writes whose computed hash doesn't match the declared one.
- Sharing: pre-signed URLs with **15-minute TTL** by default, capped at 24h; access generates an `audit_events` row.
- Encryption: SSE-S3 (AES-256) for prod buckets; server-side; KMS-managed keys at Phase 3 hardening (ADR-0008).
- Lifecycle: artifacts move to Glacier after 90 days; deleted at 365 days unless held by legal hold.

A thin internal `ObjectStore` Python interface wraps these conventions; agents and tools never call `boto3` directly.

## Consequences

- **Positive:** single API across environments; well-trod operational surface; pre-signed URLs decouple sharing from auth plumbing; content addressing makes evidence tamper-evident for free.
- **Negative:** GCS-via-S3-interop has corner cases (multipart upload limits, ACL semantics) — production GCP deployments may need the native client; we accept the wrapper carries that branch.
- **Neutral:** MinIO local consumes ~200 MB extra in `docker-compose`.

## Alternatives considered

- **Filesystem in-pod** — fastest, zero-ops; loses durability the moment a pod restarts.
- **Postgres LOBs** — keeps everything in one store but Postgres is a poor fit for >10 MB binary objects (Playwright traces routinely exceed this).
- **Native GCS client only** — would force us to rewrite tests for AWS dev paths.
- **Cloudflare R2 / Backblaze B2** — both S3-compatible and cheaper egress; viable as a future Phase 6 cost-optimisation move, but the team has no operational experience with them.

## References

- PRD §11.2, §14.3, §16
- Story 0.1.3 (Data handling), Story 1.6.3 (Evidence store), Story 1.8.2 (Report storage)
- ADR-0008 (Secrets management — KMS)
