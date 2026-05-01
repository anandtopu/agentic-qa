# TypeScript SDK

Reference impl ships at
[`sdks/typescript/`](../../sdks/typescript). npm publish
(`@aqao/sdk`) deferred per Phase-5 cuts; usable via a workspace
link today.

## Install (workspace-linked)

```bash
pnpm add file:../../sdks/typescript
```

## Hello, run

```ts
import { AQAOClient } from "@aqao/sdk";

const client = new AQAOClient({
  baseUrl: "https://api.aqao.ai",
  token: process.env.AQAO_TOKEN!,
  tenantId: process.env.AQAO_TENANT_ID!,
  role: "engineer",
});

const run = await client.testRuns.create({
  workspaceId: "ws-1",
  repository: "my-org/my-app",
  pullNumber: 42,
  headSha: "0".repeat(40),
});

const final = await client.testRuns.pollUntilTerminal(run.id, {
  timeoutMs: 300_000,
});
console.log(final.state, final.summary?.risk_score?.band);
```

## Surface

```ts
client.workspaces.create(...)
client.workspaces.get(workspaceId)
client.workspaces.setPolicy(workspaceId, { sourceYaml: ... })

client.testRuns.create(...)
client.testRuns.get(runId)
client.testRuns.failures(runId)

client.approvals.list({ state: "pending" })
client.approvals.approve(requestId, { comment: "..." })

client.usage.summary({ workspaceId, since, until })
client.audit.list({ ... })
client.audit.exportCsv({ since, until })
```

## Errors

```ts
import {
  AQAOError,
  AuthError,           // 401
  ForbiddenError,      // 403
  NotFoundError,       // 404
  ConflictError,       // 409
  RateLimitError,      // 429
  ValidationError,     // 422
} from "@aqao/sdk";
```

Every error carries `cause` (the underlying `Response`),
`traceId`, and a structured `details` array for 4xx responses.

## Retries

Built on `fetch`; honours `Retry-After` on 429s and retries
idempotent verbs (`GET`, `HEAD`) by default. Mutating verbs only
retry when the server returns 502/503/504 + an idempotency key has
been sent.

## Bundle size

Targets <30 kB minified+gzipped. No runtime dependencies beyond
`fetch` (polyfill required for Node 18-).

## Validation status

| Item | Status |
|---|---|
| Reference impl | ✅ Story 5.3 |
| npm publish | ⏳ deferred (needs a release cadence) |
| OpenAPI codegen via openapi-typescript | ⏳ Phase 5 follow-up |
