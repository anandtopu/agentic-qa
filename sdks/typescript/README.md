# @aqao/sdk

TypeScript SDK for Agentic QA Orchestrator. Thin client over the REST surface
documented at [`apis/openapi.yaml`](../../apis/openapi.yaml).

## Install

```bash
pnpm add @aqao/sdk           # npm publish deferred; workspace-link today:
pnpm add file:../../sdks/typescript
```

## Usage

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
```

See [`docs/api/typescript.md`](../../docs/api/typescript.md) for the
full walk-through.

## Bundle target

Targets <30 kB minified+gzipped, no runtime deps beyond `fetch`
(polyfill required for Node 18-).
