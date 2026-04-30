# @qaforge/sdk

TypeScript SDK for QAForge AI. Thin client over the REST surface
documented at [`apis/openapi.yaml`](../../apis/openapi.yaml).

## Install

```bash
pnpm add @qaforge/sdk           # npm publish deferred; workspace-link today:
pnpm add file:../../sdks/typescript
```

## Usage

```ts
import { QAForgeClient } from "@qaforge/sdk";

const client = new QAForgeClient({
  baseUrl: "https://api.qaforge.ai",
  token: process.env.QAFORGE_TOKEN!,
  tenantId: process.env.QAFORGE_TENANT_ID!,
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
