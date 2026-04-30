# Security & audit design

QAForge ships **enterprise-grade auditability** as a non-negotiable
constraint (PRD §14.4). This page is the portfolio walkthrough; the
full STRIDE matrix is at
[`docs/security/threat-model.md`](../security/threat-model.md).

## Audit log — three guarantees

1. **Every state-changing call writes a row** — `AuditService` is
   the only insert path for `audit_events` (Story 1.1.1).
2. **Every row is HMAC-SHA256 signed** — Story 2.4.1. Signature is
   computed over the canonical JSON of the row + the configured
   workspace HMAC key, prefixed with `v1:` so future format changes
   are detectable.
3. **Every read can be verified** — `AuditQueryService.export_csv`
   / `export_json` (Story 2.4.2) report `signature_status` per row.
   `tampered` rows surface as a SEV1 incident
   (`AlertKind.AUDIT_TAMPERED`, Epic 4.2).

## Tenant isolation — three layers

1. **App layer**: `tenant_scoped_session` sets
   `app.current_tenant_id` for the lifetime of one request
   (`apps/api/src/qaforge_api/db/session.py`).
2. **DB layer**: every tenant-scoped table has Postgres RLS +
   `FORCE ROW LEVEL SECURITY` so even the table owner respects the
   policy.
3. **Alert layer**: every 404 on a tenant-scoped fetch emits a
   `tenant_isolation.resource_miss` log line (Story 3.1.1) so a
   security team can grep for cross-tenant probing.

## RBAC — five roles, 19 permissions

* **Roles** (Story 3.1.2): owner / admin / engineer / approver /
  viewer.
* **Permissions** (Story 3.1.2 enum): 19 actions across workspace,
  policy, users, test-plans, test-runs, approvals, audit, usage,
  eval surfaces.
* **Matrix invariants** (verified by `test_permissions.py`):
  * viewer never gains write access.
  * approver never gains workspace-edit power.
  * engineer cannot decide approvals (PRD §9.10 separation of
    duties).
  * `workspace:delete` and `user:role_change` are owner-only.
  * admin is a strict superset of engineer for non-destructive
    actions.

## Approval gates — six events, full lifecycle

Story 2.1 ships PRD §9.10's six gates:

1. `destructive_sql`
2. `production_test_execution`
3. `external_ticket_creation`
4. `release_readiness`
5. `ci_pipeline_modification`
6. `high_cost_eval_run`

Each request transitions `pending → approved | rejected | expired |
cancelled`; every transition is audit-logged. Approvers cannot
slip past expired requests — `ApprovalService.approve()`
auto-expires + raises if the TTL has passed.

## Secret hygiene

* **Redactor** (Story 0.x) runs at every text sink: logs, audit
  payloads, evidence reports, PR comments. Property-based tests in
  `packages/redaction/tests/` are the contract.
* **Secrets Manager** (Story 3.6.1) holds runtime secrets:
  `audit_hmac_key`, `github_webhook_secret`, `anthropic_api_key`,
  `db_password`. IRSA scopes API-pod access to specific ARNs only.

## Webhook signatures

* **GitHub** webhooks: HMAC-SHA256 verified via Story 1.2.1.
* **Jira** webhooks: HMAC-SHA256 via the Story 4.4 verifier
  (`X-Hub-Signature-256` header). Constant-time compare via
  `hmac.compare_digest`.
* Both fail closed on missing or unprefixed signatures.

## CI security controls (Story 4.4)

| Tool | Catches | Where |
|---|---|---|
| Semgrep | SAST patterns | `.github/workflows/security.yml` |
| Trivy | SCA / container CVEs | same |
| OWASP ZAP | DAST baseline | same (manual + nightly) |
| Syft → CycloneDX | SBOM inventory | `release.yml` |
| Cosign | Image signing + SBOM attestation | same |

Findings land in the GitHub Security tab as SARIF.

## Container security (Story 3.6.2)

The Helm chart defaults to **PSS "restricted"**:

* `runAsNonRoot=true`, `runAsUser=10001`
* `readOnlyRootFilesystem=true`
* `allowPrivilegeEscalation=false`
* drop ALL capabilities
* `seccompProfile=RuntimeDefault`
* NetworkPolicy with deny-by-default + explicit DNS / Postgres /
  Redis / LLM-provider allowlists.

## Pen-test status

External pen-test deferred per agreed Phase-4 cuts until a real
cluster exists. The threat model + the CI controls are the surface
the audit reviews; the audit produces a follow-up document with
findings + their fixes.
