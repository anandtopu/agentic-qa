# Agentic QA Orchestrator — API & SDK Reference

The canonical contract is the OpenAPI document at
[`apis/openapi.yaml`](../../apis/openapi.yaml). This page is the
human-friendly walkthrough; the YAML is the source of truth for
clients.

## Authentication

Every request needs three headers:

| Header | Purpose | Example |
|---|---|---|
| `Authorization` | Bearer token | `Bearer eyJhbG...` |
| `X-AQAO-Tenant-Id` | Workspace tenant | `aaaa-bbbb-cccc-dddd` |
| `X-AQAO-Role` | Workspace RBAC role | `engineer` |
| `X-AQAO-Trace-Id` | Optional correlation id | `abc-123` |

The role header is a Phase-1 shim; Phase-3 SSO swaps it for verified
OIDC claims behind the same dependency (Story 3.1.3).

## Resource map (PRD §13)

```text
/api/v1/workspaces      Workspaces, repositories, environments, policies
/api/v1/requirements    Ingested requirements + parser output
/api/v1/test-plans      Generated plans + per-plan revisions
/api/v1/test-runs       Run lifecycle + per-run failures + reports
/api/v1/agents/tasks    Task graph for one run
/api/v1/failures/...    Classifier output
/api/v1/risk/release    Release-risk scores
/api/v1/approvals       Human approval gates
/api/v1/reports         Evidence reports
/api/v1/evaluations     Eval scorecards + baselines
/api/v1/audit           Audit log + exports
/api/v1/usage           Per-agent + per-provider cost rollups
/api/v1/webhooks        Inbound webhook receivers
```

## Status codes

| Code | When |
|---|---|
| 200 | Successful read |
| 201 | Successful create |
| 204 | Successful no-content (e.g. delete) |
| 400 | Validation error — see body for `errors[]` field-level details |
| 401 | Missing tenant / token |
| 403 | Authenticated but role lacks the permission |
| 404 | Resource doesn't exist (or the tenant can't see it — RLS-driven, see Story 3.1.1) |
| 409 | Conflict — e.g. approval already decided, idempotency-key body mismatch |
| 422 | Schema validation error on a typed body |
| 429 | Bulkhead saturated (Epic 4.3) |

## Idempotency

Every mutating endpoint accepts `Idempotency-Key: <uuid>`. Repeating
a request with the same key + body returns the cached response;
same key + different body returns 409 (Story 4.3).

## Pagination

List endpoints use cursor pagination: `?limit=100&cursor=<token>`.
Response carries `next_cursor` if more pages exist.

## Rate limits

Per-workspace concurrency is capped by the bulkhead registry
(Epic 4.3); excess requests get 429 immediately rather than
queueing. Tune `default_capacity` per environment in
`apps/api/src/aqao_api/config.py`.

## SDKs

| Language | Package | Status |
|---|---|---|
| Python | [`aqao-sdk`](python.md) | Reference impl in `sdks/python/` |
| TypeScript | [`@aqao/sdk`](typescript.md) | Reference impl in `sdks/typescript/` |

Both are thin wrappers around the OpenAPI surface — they handle
auth + retries + idempotency-key generation but don't add custom
types beyond what OpenAPI describes.

## Example notebooks

See [`docs/api/examples/`](examples/index.md) for runnable Jupyter
notebooks demonstrating the common workflows.

## Versioning

API path is `/api/v1/`; we'll bump to `/api/v2/` if we make
breaking changes. The OpenAPI document declares its version + a
changelog at the top.
