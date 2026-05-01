# Agentic QA Orchestrator — STRIDE Threat Model

**Story 4.4** — applies the STRIDE framework (Spoofing, Tampering,
Repudiation, Information disclosure, Denial of service, Elevation of
privilege) to the four planes from PRD §11.

This document is **the contract** for Phase-4 security work. CI
controls (Semgrep / Trivy / Cosign) implement the mitigations listed
here; a future external pen-test (deferred per agreed cuts)
validates them.

## Scope

In-scope assets:

* Control Plane (`apps/api`) — workspaces, users, policies,
  approvals, audit log.
* Execution Plane (`packages/tools`) — Playwright / Newman / pytest /
  SQL runners.
* Intelligence Plane (`packages/agents`) — LLM calls, classifiers,
  reporters.
* Evaluation Plane (`packages/eval`) — golden datasets + scorers.
* Storage: Postgres (RLS-enforced), S3 evidence (KMS-SSE), Secrets
  Manager.
* Trust boundaries: GitHub webhook ingress, LLM provider egress,
  Jira/GitHub issue creation egress, browser-rendered evidence
  reports.

Out-of-scope (deferred):

* Customer-managed-key BYOK.
* Air-gapped on-prem deployment.

## Trust boundaries

```
[ Internet ] -- HTTPS --> [ Ingress LB ] -- mTLS optional --> [ API pods ]
[ GitHub ]   -- webhook signed --> [ /api/v1/webhooks ]
[ API pods ] -- IRSA --> [ AWS Secrets Manager / S3 / RDS / ElastiCache ]
[ Agent runtime ] -- HTTPS --> [ LLM provider ]
[ API pods ] -- HTTPS + auth header --> [ Jira / GitHub Issues ]
```

Every arrow is a STRIDE candidate. The matrix below enumerates the
threats per arrow + the mitigation per threat.

## STRIDE matrix

### Spoofing

| Threat | Mitigation | Story |
|---|---|---|
| Forged GitHub webhook | HMAC-SHA256 signature verification on every ingress | 1.2.1 |
| Spoofed tenant via header | OIDC verification (Phase-3 deferred); for now `X-AQAO-Tenant-Id` header is the trust boundary, gated by a network ingress policy | 3.1.3 |
| Compromised LLM provider response | TLS pinning; sandboxed agent execution + structured output validation | 1.7 / 4.4 |
| Forged Jira/GitHub webhook | Per-provider HMAC signatures, verified before `process_*_event` | 3.2.2 |

### Tampering

| Threat | Mitigation | Story |
|---|---|---|
| Modified audit log row | HMAC-SHA256 signature on every write; `AuditQueryService` reports `signature_status=tampered` | 2.4.1 |
| Modified evidence artifact | S3 object versioning + KMS-SSE; bucket-owner-enforced ACLs | 3.6.1 |
| Tampered container image | Cosign signing in CI; admission controller verifies in cluster | 4.4 |
| Tampered TF state | S3 versioning + DynamoDB lock | 3.6.1 |

### Repudiation

| Threat | Mitigation | Story |
|---|---|---|
| User denies destructive SQL approval | Approval flow audit-logged with HMAC signature + decided_by user id | 2.1 / 2.4 |
| User denies pin promotion | `prompt_pin.set` / `prompt_pin.promote` audit actions | 3.4.1 |
| Issue auto-creation surprise | `external_issue.create` audit row with full draft body | 3.2.1 |

### Information disclosure

| Threat | Mitigation | Story |
|---|---|---|
| Cross-tenant data leak | Postgres RLS + `FORCE ROW LEVEL SECURITY` on every tenant-scoped table; 404 (not 403) on miss | 0.x / 3.1.1 |
| Secrets in logs | `aqao_redaction.default_redactor()` at every text sink; property-based tests | 0.x |
| Secrets in error messages | Same redactor + structured-log allow-list | 0.x |
| Eval dataset leak | Golden datasets are in-tree under MIT license; no PII | 2.6 |
| Evidence in PR comments | Body sanitized via the redactor before posting | 1.9 |

### Denial of service

| Threat | Mitigation | Story |
|---|---|---|
| Single tenant burst starves shared workers | Per-workspace bulkheads | 4.3 |
| LLM provider 5xx storm | Circuit breakers + heuristic fallback | 4.3 |
| Runaway eval / agent cost | `BudgetEnforcer` mid-flight kill-switch | 2.5 |
| Webhook flood | Rate-limit at ingress (Helm NetworkPolicy + ingress-controller) | 3.6.2 |
| Long-running query DoS | RDS `log_min_duration_statement=500ms` + per-tenant query timeout | 3.6.1 |

### Elevation of privilege

| Threat | Mitigation | Story |
|---|---|---|
| Engineer self-approves destructive SQL | RBAC matrix: `engineer` lacks `approval:decide` permission | 3.1.2 |
| Container escapes to node | PSS "restricted" defaults: `runAsNonRoot`, `readOnlyRootFilesystem`, drop ALL caps, seccomp Runtime Default | 3.6.2 |
| IRSA role over-broad | Tight IAM policies scoped to specific Secrets ARNs + evidence bucket only | 3.6.1 |
| API container reaches the public internet for arbitrary egress | NetworkPolicy egress allowlist (DNS + Postgres + Redis + LLM provider only) | 3.6.2 |

## CI controls (Story 4.4)

The mitigations above are codified in CI:

| Tool | What it catches | Where |
|---|---|---|
| **Semgrep** | SAST — common Python / TS bug patterns | `.github/workflows/security.yml` |
| **Trivy / Grype** | SCA — vulnerable dependencies + container CVEs | `.github/workflows/security.yml` |
| **OWASP ZAP** | DAST — runtime API surface scan against the dev environment | `.github/workflows/security.yml` (manual trigger; daily nightly) |
| **Syft → CycloneDX SBOM** | Inventory of every dep shipping in the container | `.github/workflows/release.yml` |
| **Cosign** | Image signature + attestation | `.github/workflows/release.yml` |

## Pen-test status

External pen-test is **deferred** per agreed Phase-4 cuts until a
real cluster (Story 3.6.1 apply) exists and a credentialled vendor
is engaged. The threat model + the CI controls are the surface this
review will audit; that audit will produce a follow-up document
documenting any findings + their fixes.
