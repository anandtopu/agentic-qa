# 1. Get a workspace

A **workspace** is QAForge's tenancy unit — one workspace per
product/repo, isolated by Postgres RLS (ADR-0007).

## Create one

```bash
curl -X POST https://api.qaforge.ai/api/v1/workspaces \
  -H "Authorization: Bearer $QAFORGE_TOKEN" \
  -H "X-QAForge-Tenant-Id: $QAFORGE_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payments",
    "application_type": "web_api"
  }'
```

The response carries the workspace `id` — save it; you'll use it
in every subsequent call.

## Add yourself as the owner

The first user in a workspace must have the `owner` role
(Story 3.1.2 RBAC). Workspace creation gives you `owner` by default
when you use the bearer-token flow above; verify with:

```bash
curl https://api.qaforge.ai/api/v1/workspaces/$WORKSPACE_ID \
  -H "Authorization: Bearer $QAFORGE_TOKEN" \
  -H "X-QAForge-Tenant-Id: $QAFORGE_TENANT_ID"
```

You should see `"role": "owner"` in your user record.

## Link the GitHub repo

```bash
curl -X POST \
  https://api.qaforge.ai/api/v1/workspaces/$WORKSPACE_ID/repositories \
  -H "Authorization: Bearer $QAFORGE_TOKEN" \
  -H "X-QAForge-Tenant-Id: $QAFORGE_TENANT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "github",
    "owner": "your-org",
    "name": "your-repo",
    "default_branch": "main"
  }'
```

Phase 3 deferred the GitHub-App OAuth dance; for now the link is a
record + you'll wire a webhook secret in
[step 3 (GitHub Action)](github-action.md).

## Next

→ [2. Set a policy](policy.md)
