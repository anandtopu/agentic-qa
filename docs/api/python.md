# Python SDK

Reference impl ships at [`sdks/python/qaforge_sdk/`](../../sdks/python/qaforge_sdk).
PyPI publish (`qaforge-sdk`) is queued behind a real release cadence
— the source is usable today via a path install:

```bash
pip install -e sdks/python
```

## Hello, run

```python
from qaforge_sdk import QAForgeClient

client = QAForgeClient(
    base_url="https://api.qaforge.ai",
    token="eyJhbG...",
    tenant_id="aaaa-bbbb-cccc-dddd",
    role="engineer",
)

# Trigger a test run.
run = client.test_runs.create(
    workspace_id="ws-1",
    repository="my-org/my-app",
    pull_number=42,
    head_sha="0000000000000000000000000000000000000000",
)

# Poll until done.
final = client.test_runs.poll_until_terminal(run.id, timeout_seconds=300)
print(final.state, final.summary["risk_score"]["band"])
```

## Surface

The client mirrors the resource map from the
[API reference](index.md):

```python
client.workspaces.create(...)
client.workspaces.get(workspace_id)
client.workspaces.set_policy(workspace_id, policy_yaml=...)

client.test_runs.create(...)
client.test_runs.get(run_id)
client.test_runs.failures(run_id)

client.approvals.list(state="pending")
client.approvals.approve(request_id, comment=...)

client.usage.summary(workspace_id, since=..., until=...)
client.audit.list(...)
client.audit.export_csv(since=..., until=...)

client.evaluations.run(agent="planner", dataset_version="v1")
client.evaluations.set_baseline(scorecard_id)
```

## Built-in retries

The client uses `tenacity` with exponential backoff on:

* 429 (`Retry-After` honoured if present),
* 502 / 503 / 504,
* connection errors and read timeouts.

Mutating calls auto-attach `Idempotency-Key` UUIDs so retries don't
double-create.

## Async variant

```python
from qaforge_sdk import AsyncQAForgeClient

async with AsyncQAForgeClient(...) as client:
    run = await client.test_runs.create(...)
```

Both clients share the same surface — the async one wraps `httpx`
asynchronously, the sync one wraps `httpx.Client`.

## Errors

```python
from qaforge_sdk import (
    QAForgeError,
    AuthError,            # 401
    PermissionError_,     # 403
    NotFoundError,        # 404
    ConflictError,        # 409 (incl. IdempotencyConflict)
    RateLimitError,       # 429
    ValidationError,      # 422
)
```

Every error carries the original response body + the
`X-QAForge-Trace-Id` for cross-referencing in the audit log.

## Validation status

| Item | Status |
|---|---|
| Reference impl | ✅ Story 5.3 |
| PyPI publish | ⏳ deferred (needs a release cadence) |
| Generated from OpenAPI via openapi-python-client | ⏳ Phase 5 follow-up |
