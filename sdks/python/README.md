# qaforge-sdk

Python SDK for QAForge AI. Thin client over the REST surface
documented at [`apis/openapi.yaml`](../../apis/openapi.yaml).

## Install

```bash
pip install qaforge-sdk    # PyPI publish deferred; use a path install today:
pip install -e sdks/python
```

## Usage

```python
from qaforge_sdk import QAForgeClient

client = QAForgeClient(
    base_url="https://api.qaforge.ai",
    token="...",
    tenant_id="...",
    role="engineer",
)

run = client.test_runs.create(
    workspace_id="ws-1",
    repository="my-org/my-app",
    pull_number=42,
    head_sha="0" * 40,
)
```

See [`docs/api/python.md`](../../docs/api/python.md) for the full
walk-through, error hierarchy, and async variant.
